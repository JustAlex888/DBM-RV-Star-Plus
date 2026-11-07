local addonName = ...
local frame = CreateFrame("Frame")

-- SavedVariables are authoritative only after ADDON_LOADED. Hooks capture this
-- local by reference, so rebinding also repairs callbacks installed earlier.
local DB
local seq = 0
local function initializeDB()
    DBMRVFreezeTraceDB = type(DBMRVFreezeTraceDB) == "table" and DBMRVFreezeTraceDB or {}
    DB = DBMRVFreezeTraceDB
    if DB.enabled == nil then DB.enabled = true end
    if DB.maxEvents == nil then DB.maxEvents = 2500 end
    DB.events = type(DB.events) == "table" and DB.events or {}
    DB.ring = type(DB.ring) == "table" and DB.ring or {}
    DB.counters = type(DB.counters) == "table" and DB.counters or {}
    DB.session = DB.session or "UNSET"
    -- Migrate the former noisy default once. Later explicit disk opt-in persists.
    if DB.transportPolicyVersion ~= 1 then
        DB.diskMode = "off"
        DB.transportPolicyVersion = 1
    end
    if DB.diskMode == nil then DB.diskMode = "off" end
    seq = tonumber(DB.seq) or 0
end
initializeDB()

local unpack = unpack
local tinsert = table.insert
local tremove = table.remove
local tostring = tostring
local type = type
local select = select
local GetTime = GetTime
local UnitName = UnitName
local UnitFullName = UnitFullName
local IsInRaid = IsInRaid
local IsInGroup = IsInGroup
local IsInInstance = IsInInstance
local GetInstanceInfo = GetInstanceInfo
local date = date
local debugstack = debugstack
local hooksecurefunc = hooksecurefunc

seq = tonumber(DB.seq) or 0
local activeEncounter, encounterStart = nil, nil
local traceActive = false
local traceModId = nil
local ownsChatLog = false
local ownsCombatLog = false
local installed = {}
local playerFullName
local currentInput, currentCallback = nil, nil
local inputSeq = 0
local smartDepth = 0
local smartContext = nil
local lowLevelHookInstalled = false
local addonIngressSeq = 0

local ENCOUNTERS = {
    [2063] = {boss="AGGRAMAR", modId=1984},
    [2092] = {boss="ARGUS", modId=2031},
}
local MODS = {
    [1984] = {boss="AGGRAMAR", encounter=2063, file="Aggramar.lua"},
    [2031] = {boss="ARGUS", encounter=2092, file="ArgustheUnmaker.lua"},
}

-- Stage 2B callback labels are keyed by the line containing self:Schedule in DBM_RV_0.6.11.
-- They are descriptive only; unknown callbacks are still proxied and counted.
local SCHEDULE_LABELS = {
    [1984] = {
        [142]="ProshlyapMurchalya1_repeat", [159]="ProshlyapMurchalya2_repeat",
        [171]="ProshlyapMurchalyaNormalAdds_repeat", [183]="ProshlyapMurchalya1_direct",
        [190]="ProshlyapMurchalya2_direct", [197]="ProshlyapMurchalyaNormalAdds_direct",
        [225]="ProshlyapMurchalya1_from_sendAnnounce", [229]="ProshlyapMurchalya2_from_sendAnnounce",
        [232]="startMurchalProshlyapation_from_sendAnnounce", [260]="sendAnnounce",
    },
    [2031] = {
        [338]="startRVReoriginationModule_direct", [358]="startProshlyapationOfMurchal1_from_sendAnnounce",
        [361]="startProshlyapationOfMurchal2_from_sendAnnounce", [383]="sendAnnounce",
    },
}

local TRACE_SPELLS = {
    -- Aggramar
    [244894]="AGG_CORRUPTED_AEGIS", [244688]="AGG_TAESHALACH_TECHNIQUE",
    -- Argus
    [255648]="ARG_PHASE2_TRIGGER", [256388]="ARG_REORIGINATION_INIT",
    [258029]="ARG_APOCALYPSE_INIT", [256544]="ARG_END_OF_ALL_THINGS",
    [258068]="ARG_SARGERAS_GAZE_EMOTE",
}

local function pack(...)
    return {n=select("#", ...), ...}
end

local function bytePrefix(s, limit)
    if #s <= limit then return s end
    while limit > 0 and s:byte(limit + 1) >= 128 and s:byte(limit + 1) < 192 do limit = limit - 1 end
    return s:sub(1, limit)
end

local function sanitize(v)
    local s = tostring(v == nil and "" or v)
    s = s:gsub("[\r\n\t|]", " ")
    if #s > 180 then s = bytePrefix(s, 177) .. "..." end
    return s
end

local function getPlayerFullName()
    if playerFullName then return playerFullName end
    local name, realm
    if UnitFullName then name, realm = UnitFullName("player") end
    if not name then name = UnitName("player") end
    if name and realm and realm ~= "" then playerFullName = name .. "-" .. realm else playerFullName = name end
    return playerFullName or "?"
end

local function getRole()
    local r = DBM and DBM.GetRaidRank and DBM:GetRaidRank() or 0
    if r >= 2 then return "leader", r end
    if r == 1 then return "assistant", r end
    return "member", r
end

local function getDifficulty()
    local name, instanceType, difficultyID, difficultyName, maxPlayers = GetInstanceInfo()
    return difficultyID or 0, difficultyName or "?", instanceType or "?", maxPlayers or 0, name or "?"
end

local function bossInfo(modId)
    local m = MODS[tonumber(modId or 0)]
    if m then return m.boss, m.encounter end
    local e = ENCOUNTERS[activeEncounter or 0]
    if e then return e.boss, activeEncounter end
    return "NONE", activeEncounter or 0
end

local function counterKey(kind, boss)
    return tostring(DB.session) .. ":" .. tostring(boss) .. ":" .. tostring(kind)
end

local function inc(kind, boss)
    local k = counterKey(kind, boss)
    DB.counters[k] = (DB.counters[k] or 0) + 1
    return DB.counters[k]
end

local KEY_DISK = {
    ENCOUNTER_START=true, ENCOUNTER_END=true, DBM_COMBAT_END=true, MARK=true, SESSION=true,
}

local function storeRing(line)
    DB.ring[#DB.ring + 1] = line
    if #DB.ring > 1000 then tremove(DB.ring, 1) end
    DB.lastLine = line
end

-- Diagnostic failures must never become boss-handler failures. No chat/error-handler
-- calls here: those can recurse through the same instrumentation.
local function diagnosticFailure(where, err)
    pcall(function()
        DB.diagnosticErrors = DB.diagnosticErrors or {}
        local errors = DB.diagnosticErrors
        errors[#errors + 1] = {where=where, message=tostring(err), t=GetTime()}
        while #errors > 20 do tremove(errors, 1) end
    end)
end

local diskFailed = false
local diskSent = 0
local nextDiskAt = 0
local inBreadcrumb = false
local function diskBreadcrumb(line, kind)
    if not traceActive or inBreadcrumb or diskFailed or DB.diskMode == "off" then return end
    if DB.diskMode == "key" and not KEY_DISK[kind] then return end
    local now = GetTime()
    if now < nextDiskAt or diskSent >= 20 then return end
    local target = getPlayerFullName()
    if target and SendChatMessage then
        -- Optional crash breadcrumbs are bounded even in explicit full mode.
        nextDiskAt = now + 2
        diskSent = diskSent + 1
        -- Keep the complete canonical line in SavedVariables. Chat transport uses
        -- plain delimiters and a bounded UTF-8 prefix (the client limit is bytes).
        local wire = line:gsub("|", ";"):gsub("[\r\n\t]", " ")
        if #wire > 240 then
            wire = bytePrefix(wire, 237) .. "..."
        end
        inBreadcrumb = true
        local ok, err = pcall(SendChatMessage, wire, "WHISPER", nil, target)
        inBreadcrumb = false
        if not ok then
            diskFailed = true -- no error storm; retry at the next target encounter
            diagnosticFailure("diskBreadcrumb", err)
        end
    end
end

local function recordUnsafe(kind, fields, breadcrumb)
    if not DB.enabled or not traceActive then return nil end
    fields = fields or {}
    seq = seq + 1
    DB.seq = seq
    local now = GetTime()
    local role, rank = getRole()
    local diffId, diffName, instanceType, maxPlayers, zone = getDifficulty()
    local modId = fields.mod_id or (currentInput and currentInput.mod_id) or (currentCallback and currentCallback.mod_id) or 0
    local boss, encounter = bossInfo(modId)
    local count = inc(kind, boss)
    local r = {
        seq=seq, kind=kind, t=now, wall=(date and date("%Y-%m-%d %H:%M:%S") or ""),
        elapsed=(encounterStart and now - encounterStart or 0), session=DB.session,
        boss=boss, encounter=encounter, mod_id=modId, player=getPlayerFullName(), role=role, raid_rank=rank,
        difficulty=diffId, difficulty_name=diffName, instance_type=instanceType, group_size=maxPlayers, zone=zone,
        count=count,
    }
    for k,v in pairs(fields) do r[k] = v end
    DB.events[#DB.events + 1] = r
    while #DB.events > (DB.maxEvents or 2500) do tremove(DB.events, 1) end

    local parts = {"[RVTRACE3", tostring(seq), string.format("%.3f", now) .. "]", kind,
        "session="..sanitize(DB.session), "boss="..sanitize(boss), "role="..sanitize(role)}
    local compactKeys = {"input_id","method","spell_id","prepare_index","antispam_result","sync_event","sync_payload",
        "transport_sender","channel","callback","delay","pending","requested_channel","actual_channel","election_action","note"}
    for _,k in ipairs(compactKeys) do
        if r[k] ~= nil and r[k] ~= "" then parts[#parts+1] = k .. "=" .. sanitize(r[k]) end
    end
    local line = table.concat(parts, "|")
    storeRing(line)
    if breadcrumb ~= false then diskBreadcrumb(line, kind) end
    return r
end

local function record(kind, fields, breadcrumb)
    local ok, result = pcall(recordUnsafe, kind, fields, breadcrumb)
    if ok then return result end
    diagnosticFailure("record:" .. tostring(kind), result)
end

_G.DBMRVFreezeTraceCheckpoint = function(msg)
    record("MARK", {note="CP " .. tostring(msg)}, true)
end

local function statusMsg(msg)
    if DEFAULT_CHAT_FRAME then DEFAULT_CHAT_FRAME:AddMessage("|cff33ff99DBM-RV FreezeTrace Stage2B:|r " .. tostring(msg)) end
end

local function getLoggingState(fn)
    if type(fn) ~= "function" then return nil end
    local ok, state = pcall(fn)
    if ok then return state and true or false end
    return nil
end

local function ensureLogging()
    local chatBefore = getLoggingState(LoggingChat)
    local combatBefore = getLoggingState(LoggingCombat)
    ownsChatLog = false
    ownsCombatLog = false
    if type(LoggingChat) == "function" and chatBefore == false then
        local ok = pcall(LoggingChat, true)
        ownsChatLog = ok and true or false
    end
    if type(LoggingCombat) == "function" and combatBefore == false then
        local ok = pcall(LoggingCombat, true)
        ownsCombatLog = ok and true or false
    end
    record("LOGGING", {chat_before=tostring(chatBefore), combat_before=tostring(combatBefore),
        owns_chat=tostring(ownsChatLog), owns_combat=tostring(ownsCombatLog)}, false)
end

local function stopOwnedLogging()
    if ownsCombatLog and type(LoggingCombat) == "function" then pcall(LoggingCombat, false) end
    if ownsChatLog and type(LoggingChat) == "function" then pcall(LoggingChat, false) end
    ownsChatLog = false
    ownsCombatLog = false
end

local function activateTraceForMod(modId, source)
    modId = tonumber(modId or 0) or 0
    local meta = MODS[modId]
    if not DB.enabled or not meta then return false end
    if not DBM or not DBM.GetModByName or not DBM:GetModByName(modId) then return false end
    if traceActive then return traceModId == modId end
    diskFailed = false
    diskSent, nextDiskAt = 0, 0
    traceActive = true
    traceModId = modId
    activeEncounter = meta.encounter
    encounterStart = GetTime()
    ensureLogging()
    record("ENCOUNTER_START", {mod_id=modId, encounter_name=meta.boss, note=source or "AUTO"}, true)
    return true
end

local function deactivateTrace(encounterID, success, source)
    if not traceActive then return end
    if encounterID and activeEncounter and tonumber(encounterID) ~= tonumber(activeEncounter) then return end
    local modId = traceModId or (ENCOUNTERS[activeEncounter or 0] and ENCOUNTERS[activeEncounter].modId) or 0
    record("ENCOUNTER_END", {mod_id=modId, success=success or 0, note=source or "AUTO"}, true)
    stopOwnedLogging()
    traceActive = false
    traceModId = nil
    activeEncounter = nil
    encounterStart = nil
    currentInput, currentCallback = nil, nil
end

local function callerLineForFile(fileName)
    if not debugstack then return nil, nil end
    local stack = debugstack(2, 10, 0) or ""
    for line in stack:gmatch("[^\n]+") do
        if line:find(fileName, 1, true) then
            local n = line:match(":" .. "(%d+)" .. ":") or line:match(":" .. "(%d+)" .. " in")
            if n then return tonumber(n), line end
        end
    end
    return nil, stack
end

local function spellFromArgs(method, ...)
    if method == "UNIT_SPELLCAST_SUCCEEDED" then
        local _, _, bfaSpellId, _, legacySpellId = ...
        return legacySpellId or bfaSpellId
    end
    if method == "CHAT_MSG_RAID_BOSS_EMOTE" then
        local msg = ...
        if type(msg) == "string" and msg:find("spell:258068", 1, true) then return 258068 end
        return nil
    end
    local a = ...
    if type(a) == "table" then
        if method == "SPELL_INTERRUPT" then return a.extraSpellId or a.spellId end
        return a.spellId or a.extraSpellId
    end
    return nil
end

local function shouldTraceInput(modId, method, ...)
    if method == "OnCombatStart" or method == "OnCombatEnd" then return true, nil end
    local sid = spellFromArgs(method, ...)
    if modId == 1984 then
        return (sid == 244894 or sid == 244688), sid
    elseif modId == 2031 then
        return (sid == 255648 or sid == 256388 or sid == 258029 or sid == 256544 or sid == 258068), sid
    end
    return false, sid
end

local function wrapInputMethod(mod, methodName)
    local key = tostring(mod.id) .. ":input:" .. methodName
    if installed[key] then return end
    local old = mod[methodName]
    if type(old) ~= "function" then return end
    mod[methodName] = function(self, ...)
        local thisModId = tonumber(self.id)
        if methodName == "OnCombatStart" then
            local ok, err = pcall(activateTraceForMod, thisModId, "DBM_OnCombatStart")
            if not ok then diagnosticFailure("activateTraceForMod", err) end
        end
        if not traceActive or traceModId ~= thisModId then return old(self, ...) end
        local ok, yes, sid = pcall(shouldTraceInput, thisModId, methodName, ...)
        if not ok then
            diagnosticFailure("shouldTraceInput", yes)
            return old(self, ...)
        end
        if not yes then return old(self, ...) end
        inputSeq = inputSeq + 1
        local prev = currentInput
        currentInput = {id=inputSeq, mod_id=tonumber(self.id), method=methodName, spell_id=sid, prepare_index=0}
        record("INPUT", {mod_id=tonumber(self.id), input_id=inputSeq, method=methodName, spell_id=sid or "",
            mechanic=TRACE_SPELLS[sid] or methodName, phase=(self.vb and self.vb.phase or "")}, true)
        local ret = pack(old(self, ...))
        record("INPUT_END", {mod_id=tonumber(self.id), input_id=inputSeq, method=methodName, spell_id=sid or ""}, false)
        if methodName == "OnCombatEnd" then
            record("DBM_COMBAT_END", {mod_id=tonumber(self.id), input_id=inputSeq, method=methodName, note="waiting for ENCOUNTER_END"}, true)
        end
        currentInput = prev
        return unpack(ret, 1, ret.n)
    end
    installed[key] = true
end

local function wrapAntiSpam(mod)
    local key = tostring(mod.id) .. ":AntiSpam"
    if installed[key] then return end
    local old = mod.AntiSpam
    if type(old) ~= "function" then return end
    mod.AntiSpam = function(self, interval, id)
        local result = old(self, interval, id)
        if id == "prepareMessage" and traceActive and traceModId == tonumber(self.id) then
            if currentInput then currentInput.prepare_index = (currentInput.prepare_index or 0) + 1 end
            record("PREPARE_MESSAGE", {mod_id=tonumber(self.id), input_id=currentInput and currentInput.id or "",
                method=currentInput and currentInput.method or "", spell_id=currentInput and currentInput.spell_id or "",
                prepare_index=currentInput and currentInput.prepare_index or 0, antispam_interval=interval,
                antispam_key=id, antispam_result=tostring(result)}, true)
        end
        return result
    end
    installed[key] = true
end

local function isPremsg(event)
    return type(event) == "string" and event:find("premsg_", 1, true) == 1
end

local function wrapSync(mod)
    local id = tonumber(mod.id)
    local key = tostring(id) .. ":sync"
    if installed[key] then return end

    local oldSend = mod.SendSync
    if type(oldSend) == "function" then
        mod.SendSync = function(self, event, ...)
            if isPremsg(event) and traceActive and traceModId == id then
                local payload = select(1, ...)
                local group = "SOLO"
                if IsInGroup(LE_PARTY_CATEGORY_INSTANCE) and IsInInstance() then group = "INSTANCE_CHAT"
                elseif IsInRaid() then group = "RAID"
                elseif IsInGroup(LE_PARTY_CATEGORY_HOME) then group = "PARTY" end
                record("SEND_SYNC", {mod_id=id, input_id=currentInput and currentInput.id or "", sync_event=event,
                    sync_payload=payload or "", expected_group_channel=group, expected_group_send=(group ~= "SOLO") and 1 or 0,
                    expected_self_whisper_send=1}, true)
            end
            return oldSend(self, event, ...)
        end
    end

    local oldReceive = mod.ReceiveSync
    if type(oldReceive) == "function" then
        mod.ReceiveSync = function(self, event, sender, revision, ...)
            if isPremsg(event) and traceActive and traceModId == id then
                record("RECEIVE_SYNC", {mod_id=id, sync_event=event, sync_payload=select(1, ...) or "",
                    transport_sender=sender or "LOCAL_NIL", revision=revision or "", receive_origin=sender and "NETWORK" or "LOCAL_SENDSYNC"}, true)
            end
            return oldReceive(self, event, sender, revision, ...)
        end
    end

    local oldOn = mod.OnSync
    if type(oldOn) == "function" then
        mod.OnSync = function(self, event, ...)
            if isPremsg(event) and traceActive and traceModId == id then
                local electionName = select(1, ...)
                local transportSender = select(2, ...)
                local me = UnitName("player") or ""
                local action = "UNKNOWN"
                if type(electionName) == "string" and me ~= "" then
                    if electionName < me then action = "CLEAR_LOCAL_FLAG" else action = "KEEP_LOCAL_FLAG" end
                end
                record("ON_SYNC", {mod_id=id, sync_event=event, sync_payload=electionName or "",
                    election_name=electionName or "", transport_sender=transportSender or "LOCAL_NIL", election_action=action}, true)
            end
            return oldOn(self, event, ...)
        end
    end
    installed[key] = true
end

local function makeSchedulerHooks(mod)
    local id = tonumber(mod.id)
    local key = tostring(id) .. ":scheduler"
    if installed[key] then return end
    local oldSchedule, oldUnschedule = mod.Schedule, mod.Unschedule
    if type(oldSchedule) ~= "function" or type(oldUnschedule) ~= "function" then return end

    local byOriginal = {}
    local callbackSeq = 0

    local function pendingTotal()
        local n = 0
        for _,m in pairs(byOriginal) do n = n + (m.pending or 0) end
        return n
    end

    local function metaFor(func, callerLine, callerStack)
        local m = byOriginal[func]
        if m then return m end
        callbackSeq = callbackSeq + 1
        local label = callerLine and SCHEDULE_LABELS[id] and SCHEDULE_LABELS[id][callerLine] or nil
        m = {id=(MODS[id].boss .. "_CB" .. callbackSeq), label=label or ("callback_" .. callbackSeq), pending=0, exec=0, cancelled=0,
            original=func, first_line=callerLine, first_stack=callerStack}
        m.proxy = function(...)
            if m.pending > 0 then m.pending = m.pending - 1 end
            m.exec = m.exec + 1
            local prev = currentCallback
            currentCallback = {id=m.id, label=m.label, mod_id=id}
            record("CALLBACK_EXEC", {mod_id=id, callback=m.label, callback_id=m.id, callback_exec_count=m.exec,
                pending=m.pending, reentry_depth=(prev and 2 or 1), scheduled_from_line=m.first_line or ""}, true)
            local ret = pack(m.original(...))
            currentCallback = prev
            return unpack(ret, 1, ret.n)
        end
        byOriginal[func] = m
        return m
    end

    mod.Schedule = function(self, delay, func, ...)
        if not traceActive or traceModId ~= id then return oldSchedule(self, delay, func, ...) end
        if type(func) ~= "function" then return oldSchedule(self, delay, func, ...) end
        local line, stack = callerLineForFile(MODS[id].file)
        local m = metaFor(func, line, stack)
        m.pending = m.pending + 1
        record("SCHEDULE", {mod_id=id, input_id=currentInput and currentInput.id or "", callback=m.label, callback_id=m.id,
            delay=delay or 0, pending=m.pending, scheduled_from_line=line or "", parent_callback=currentCallback and currentCallback.label or ""}, true)
        return oldSchedule(self, delay, m.proxy, ...)
    end

    mod.Unschedule = function(self, func, ...)
        if func == nil then
            local before = pendingTotal()
            for _,m in pairs(byOriginal) do
                m.cancelled = m.cancelled + (m.pending or 0)
                m.pending = 0
            end
            record("UNSCHEDULE", {mod_id=id, callback="ALL", cancelled=before, pending=0, note="module-wide"}, true)
            return oldUnschedule(self, nil, ...)
        end
        local m = byOriginal[func]
        if m then
            local before = m.pending or 0
            m.cancelled = m.cancelled + before
            m.pending = 0
            record("UNSCHEDULE", {mod_id=id, callback=m.label, callback_id=m.id, cancelled=before, pending=0}, true)
            return oldUnschedule(self, m.proxy, ...)
        end
        return oldUnschedule(self, func, ...)
    end

    local oldStop = mod.Stop
    if type(oldStop) == "function" then
        mod.Stop = function(self, ...)
            local before = pendingTotal()
            if traceActive and traceModId == id then
                record("STOP", {mod_id=id, pending=before, note="Core Stop() will Unschedule all module callbacks"}, true)
            end
            local ret = pack(oldStop(self, ...))
            for _,m in pairs(byOriginal) do m.pending = 0 end
            return unpack(ret, 1, ret.n)
        end
    end

    installed[key] = true
end

local function wrapSmartChat()
    if installed.smartChat or type(_G.smartChat) ~= "function" then return end
    local old = _G.smartChat
    _G.smartChat = function(msg, arg, target)
        local modId = currentCallback and currentCallback.mod_id or (currentInput and currentInput.mod_id) or 0
        if not traceActive or traceModId ~= modId then return old(msg, arg, target) end
        smartDepth = smartDepth + 1
        local prev = smartContext
        smartContext = {requested=arg or "nil", target=target, sent=false, actual="NONE", depth=smartDepth}
        record("SMARTCHAT", {mod_id=modId, callback=currentCallback and currentCallback.label or "", requested_channel=arg or "nil",
            reentry_depth=smartDepth, note=sanitize(msg)}, true)
        local ret = pack(old(msg, arg, target))
        if smartContext and not smartContext.sent then
            record("CHAT_OUT", {mod_id=modId, callback=currentCallback and currentCallback.label or "", requested_channel=arg or "nil",
                actual_channel="NONE", raid_warning_count=0, fallback_chat_count=0, note="smartChat produced no SendChatMessage"}, true)
        end
        smartContext = prev
        smartDepth = smartDepth - 1
        return unpack(ret, 1, ret.n)
    end
    installed.smartChat = true
end

local function installChatHooks()
    if installed.chatHooks then return end
    if hooksecurefunc and type(SendChatMessage) == "function" then
        local ok = pcall(hooksecurefunc, "SendChatMessage", function(msg, chatType, language, target)
            if inBreadcrumb then return end
            if smartDepth > 0 and smartContext then
                smartContext.sent = true
                smartContext.actual = chatType or "?"
                local modId = currentCallback and currentCallback.mod_id or (currentInput and currentInput.mod_id) or 0
                local isRW = chatType == "RAID_WARNING"
                record("CHAT_OUT", {mod_id=modId, callback=currentCallback and currentCallback.label or "",
                    requested_channel=smartContext.requested or "", actual_channel=chatType or "?", target=target or "",
                    raid_warning_count=isRW and 1 or 0, fallback_chat_count=isRW and 0 or 1, reentry_depth=smartDepth,
                    note=sanitize(msg)}, true)
            end
        end)
        if not ok then record("HOOK_WARNING", {note="SendChatMessage secure hook unavailable"}, false) end
    end

    -- Best-effort secure hook. DBM Core localizes SendAddonMessage during load, so whether
    -- this hook observes that localized call is itself a runtime fact. CHAT_MSG_ADDON ingress
    -- remains the authoritative observation of what comes back into this client.
    if hooksecurefunc and type(SendAddonMessage) == "function" then
        local ok = pcall(hooksecurefunc, "SendAddonMessage", function(prefix, message, channel, target)
            if prefix == "D4" and type(message) == "string" and message:find("premsg_", 1, true) and message:find("M\t", 1, true) == 1 then
                local modId = tonumber(message:match("^M\t(%d+)")) or 0
                if MODS[modId] and traceActive and traceModId == modId then
                    lowLevelHookInstalled = true
                    record("LOWLEVEL_ADDON_EGRESS", {mod_id=modId, channel=channel or "?", receiver=target or "",
                        group_send_count=(channel == "RAID" or channel == "PARTY" or channel == "INSTANCE_CHAT") and 1 or 0,
                        self_whisper_send_count=(channel == "WHISPER") and 1 or 0, note=sanitize(message)}, true)
                end
            end
        end)
        if not ok then record("HOOK_WARNING", {note="SendAddonMessage secure hook unavailable"}, false) end
    end
    installed.chatHooks = true
end

local function installHooks()
    if not DBM or not DBM.GetModByName then return end
    wrapSmartChat()
    installChatHooks()
    for modId, meta in pairs(MODS) do
        local mod = DBM:GetModByName(modId)
        if mod then
            wrapAntiSpam(mod)
            wrapSync(mod)
            makeSchedulerHooks(mod)
            wrapInputMethod(mod, "OnCombatStart")
            wrapInputMethod(mod, "OnCombatEnd")
            if modId == 1984 then
                wrapInputMethod(mod, "SPELL_AURA_APPLIED")
                wrapInputMethod(mod, "SPELL_AURA_REMOVED")
                wrapInputMethod(mod, "UNIT_SPELLCAST_SUCCEEDED")
            elseif modId == 2031 then
                wrapInputMethod(mod, "SPELL_CAST_START")
                wrapInputMethod(mod, "SPELL_AURA_APPLIED")
                wrapInputMethod(mod, "SPELL_INTERRUPT")
                wrapInputMethod(mod, "CHAT_MSG_RAID_BOSS_EMOTE")
            end
        end
    end
    record("HOOKS", {note="Stage2B hooks installed; lowLevelSecureHookSeen="..tostring(lowLevelHookInstalled)}, false)
end

local function parseAddonMessage(prefix, message, channel, sender)
    if not traceActive then return end
    if prefix ~= "D4" or type(message) ~= "string" then return end
    if message:find("premsg_", 1, true) == nil then return end
    local pfx, modId, revision, event, payload = message:match("^([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\t?(.*)$")
    if pfx ~= "M" then return end
    modId = tonumber(modId or "") or 0
    if not MODS[modId] or traceModId ~= modId then return end
    addonIngressSeq = addonIngressSeq + 1
    record("DBM_ADDON_INGRESS", {mod_id=modId, sync_event=event or "", sync_payload=payload or "", revision=revision or "",
        channel=channel or "?", transport_sender=sender or "?", receiver=getPlayerFullName(), addon_ingress_id=addonIngressSeq,
        group_send_count=(channel == "RAID" or channel == "PARTY" or channel == "INSTANCE_CHAT") and 1 or 0,
        self_whisper_send_count=(channel == "WHISPER") and 1 or 0}, true)
end

frame:RegisterEvent("PLAYER_LOGIN")
frame:RegisterEvent("PLAYER_ENTERING_WORLD")
frame:RegisterEvent("ADDON_LOADED")
frame:RegisterEvent("ENCOUNTER_START")
frame:RegisterEvent("ENCOUNTER_END")
frame:RegisterEvent("CHAT_MSG_ADDON")
frame:RegisterEvent("PLAYER_LOGOUT")

frame:SetScript("OnEvent", function(self, event, ...)
    if event == "PLAYER_LOGIN" then
        initializeDB()
        -- Silent arming only. No logging and no trace output outside target encounters.
        installHooks()
    elseif event == "PLAYER_ENTERING_WORLD" then
        -- Retry hook installation silently after zone/load transitions.
        if C_Timer and C_Timer.After then C_Timer.After(2, installHooks) else installHooks() end
    elseif event == "ADDON_LOADED" then
        local loaded = ...
        if loaded == addonName then initializeDB() end
        if loaded == "DBM-AntorusBurningThrone" then
            if C_Timer and C_Timer.After then C_Timer.After(0.5, installHooks) else installHooks() end
        end
    elseif event == "ENCOUNTER_START" then
        local encounterID, encounterName, difficultyID, groupSize = ...
        local meta = ENCOUNTERS[encounterID]
        if meta then
            -- Fallback/confirmation path. Normally DBM OnCombatStart arms trace first.
            installHooks()
            if activateTraceForMod(meta.modId, "WOW_ENCOUNTER_START") then
                activeEncounter = encounterID
                record("MARK", {mod_id=meta.modId, note="encounter="..tostring(encounterName or meta.boss).." diff="..tostring(difficultyID or 0).." size="..tostring(groupSize or 0)}, false)
            end
        end
    elseif event == "ENCOUNTER_END" then
        local encounterID, encounterName, difficultyID, groupSize, success = ...
        if traceActive and ENCOUNTERS[encounterID] then
            deactivateTrace(encounterID, success or 0, "WOW_ENCOUNTER_END " .. tostring(encounterName or ""))
        end
    elseif event == "CHAT_MSG_ADDON" then
        if traceActive then parseAddonMessage(...) end
    elseif event == "PLAYER_LOGOUT" then
        if traceActive then
            record("MARK", {mod_id=traceModId or 0, note="PLAYER_LOGOUT during active trace"}, true)
            stopOwnedLogging()
            traceActive = false
            traceModId = nil
        end
    end
end)

SLASH_DBMRVFREEZETRACE1 = "/rvtrace"
SlashCmdList["DBMRVFREEZETRACE"] = function(msg)
    msg = msg or ""
    local cmd, rest = msg:match("^(%S*)%s*(.-)$")
    cmd = (cmd or ""):lower()
    if cmd == "on" then
        DB.enabled = true
        statusMsg("взведён; автозапуск только на Агграмаре и Аргусе")
    elseif cmd == "off" then
        if traceActive then
            record("MARK", {mod_id=traceModId or 0, note="TRACE DISABLED MANUALLY"}, true)
            stopOwnedLogging()
            traceActive = false
            traceModId = nil
            activeEncounter = nil
            encounterStart = nil
        end
        DB.enabled = false
        statusMsg("выключен")
    elseif cmd == "session" then
        if rest == "" then
            statusMsg("session=" .. tostring(DB.session))
        else
            DB.session = rest
            if traceActive then record("SESSION", {note=rest}, true) end
            statusMsg("session=" .. rest)
        end
    elseif cmd == "mark" then
        if rest == "" then rest = "manual marker" end
        if traceActive then
            record("MARK", {mod_id=traceModId or 0, note=rest}, true)
            statusMsg("маркер записан: " .. rest)
        else
            statusMsg("маркер не записан: целевой бой сейчас не активен")
        end
    elseif cmd == "disk" then
        rest = (rest or ""):lower()
        if rest == "off" or rest == "key" or rest == "full" then
            DB.diskMode = rest
            statusMsg("disk breadcrumbs=" .. rest)
        else
            statusMsg("disk mode: " .. tostring(DB.diskMode) .. " (off|key|full)")
        end
    elseif cmd == "hooks" then
        installHooks()
        statusMsg("hooks переустановлены")
    elseif cmd == "clear" then
        DB.events, DB.ring, DB.counters = {}, {}, {}
        DB.seq, seq = 0, 0
        statusMsg("trace buffers очищены")
    elseif cmd == "summary" then
        statusMsg("events=" .. tostring(#DB.events) .. ", ring=" .. tostring(#DB.ring) .. ", session=" .. tostring(DB.session))
        local boss = ENCOUNTERS[activeEncounter or 0] and ENCOUNTERS[activeEncounter].boss or "NONE"
        for _,kind in ipairs({"INPUT","PREPARE_MESSAGE","SEND_SYNC","RECEIVE_SYNC","ON_SYNC","DBM_ADDON_INGRESS","SCHEDULE","CALLBACK_EXEC","UNSCHEDULE","SMARTCHAT","CHAT_OUT"}) do
            local k = counterKey(kind, boss)
            if DB.counters[k] then statusMsg(kind .. "=" .. tostring(DB.counters[k])) end
        end
    elseif cmd == "status" or cmd == "" then
        local role, rank = getRole()
        local diffId, diffName = getDifficulty()
        statusMsg("version=0.3.4-TEST build=FTRACE-20261107-01 enabled=" .. tostring(DB.enabled) .. " active=" .. tostring(traceActive) .. " session=" .. tostring(DB.session))
        statusMsg("target=Aggramar/Argus encounter=" .. tostring(activeEncounter or "none") .. " role=" .. role .. " rank=" .. tostring(rank) .. " diff=" .. tostring(diffId) .. "/" .. tostring(diffName))
        statusMsg("events=" .. tostring(#DB.events) .. " disk=" .. tostring(DB.diskMode) .. " lowLevelSecureHookSeen=" .. tostring(lowLevelHookInstalled) .. " diskFailed=" .. tostring(diskFailed) .. " diagnosticErrors=" .. tostring(type(DB.diagnosticErrors) == "table" and #DB.diagnosticErrors or 0))
        statusMsg("/rvtrace session ID | mark TEXT | summary | disk key|full|off | hooks | clear | on | off | status")
    else
        statusMsg("неизвестная команда; /rvtrace status")
    end
end

import re
def adapt(text, path):
    changes = []

    def sub(pattern, repl, label, flags=0):
        nonlocal text
        text, n = re.subn(pattern, repl, text, flags=flags)
        if n:
            changes.append({'adaptation': label, 'occurrences': n})
    sub('DBM_COMMON_L\\.([A-Z_]+_ICON|BREAK_LOS)', lambda m: 'DBM_CORE_' + m[1], 'legacy localized constants')
    sub('DBM_CORE_BLEED_ICON', 'DBM_CORE_DAMAGE_ICON', 'bleed marker uses existing damage icon; warning semantics retained')
    sub('DBM_CORE_L\\.(INFOFRAME_POWER|AUTO_YELL_CUSTOM_FADE)', lambda m: 'DBM_CORE_' + m[1], 'legacy Core labels')
    sub('DBM_CORE_L\\.AUTO_ANNOUNCE_TEXTS', 'DBM_CORE_AUTO_ANNOUNCE_TEXTS', 'legacy automatic announce templates')
    sub('DBM_COMMON_L\\.ORB', '(GetLocale() == "ruRU" and "сфера" or "orb")', 'localized orb destination without modern common table')
    sub('mod:AddTimerLine\\(DBM:EJ_GetSectionInfo\\((\\d+)\\)\\)', '-- RVCOMPLETE: optional EJ header \\1 unavailable in Legion; combat logic below retained.', 'omit cosmetic EJ headers only')
    sub('function mod:(UNIT_SPELLCAST_\\w+)\\(([^\\n]*)spellId\\)', lambda m: 'function mod:' + m[1] + '(' + m[2] + 'spellId, legacyRank, legacySpellId)\n\tspellId = legacySpellId or spellId', 'Legion five-argument and newer three-argument unit spell payload')
    sub('local _, _, _, _, _, (expireTime|expires) = DBM:UnitDebuff', 'local _, _, _, _, _, _, \\1 = DBM:UnitDebuff', 'Legion aura expiration field seven')
    sub('self:SetStage\\(0\\)', 'self.vb.phase = (self.vb.phase or 0) + 1', 'increment stage in existing legacy vb.phase')
    sub('self:SetStage\\((\\d+)\\)', 'self.vb.phase = \\1', 'set stage in existing legacy vb.phase')
    sub('self:GetStage\\(3, 1\\)', '(self.vb.phase < 3)', 'ViqGoth only: below final platform')
    sub('self:GetStage\\(2, 2\\)', '(self.vb.phase > 2)', 'greater-than phase predicate, verified official BossMod API')
    sub('self:GetStage\\((\\d+)\\)', '(self.vb.phase == \\1)', 'phase equality predicate')
    sub('self:IsMythicPlus\\(\\)', 'self:IsDifficulty("challenge5")', 'old-Core challenge5 difficulty predicate')
    sub(':NewCDNPTimer\\(', ':NewCDTimer(', 'retain cooldown/GUID lifecycle using supported normal bars (not nameplate placement)')
    sub(':NewSpecialWarningKeepMove\\(', ':NewSpecialWarningDontStand(', 'continuous movement warning via legacy dontstand constructor')
    sub('\\b(warnPallidGlare|warnHorrificVisage)\\(\\)', '\\1:Show()', 'fix active donor announce-object called as function')
    sub('timerWaveofDecayCD:Start\\(args.destGUID\\)', 'timerWaveofDecayCD:Stop(args.destGUID)', 'UNIT_DIED: stop dead NPC cooldown instead of donor restart typo')
    sub('mod:SetRevision\\("@file-date-integer@"\\)', 'mod:SetRevision(20261015000000)', 'explicit internal integration revision; no install version assigned')
    if path.endswith('AtalDazarTrash.lua'):
        text += '\nmod.SPELL_AURA_APPLIED_DOSE = mod.SPELL_AURA_APPLIED -- RVCOMPLETE: registered stacking aura uses same warning.\n'
        changes.append({'adaptation': 'wire registered Rending Maul stack event to existing aura handler', 'occurrences': 1})
    if ':HardStop(' in text:
        text = re.sub('(\\w+):HardStop\\(([^)]*)\\)', 'RVStopGuidTimers(\\1, \\2)', text)
        helper = '-- RVCOMPLETE: stop all count variants for one NPC, retaining other NPC bars.\nlocal function RVStopGuidTimers(timer, guid)\n if not guid then timer:Cancel(); return end\n local ids = {}\n for _, id in ipairs(timer.startedTimers) do ids[#ids+1] = id end\n for _, id in ipairs(ids) do\n  if id:sub(-#guid-1) == "\\t"..guid then\n   local args = {}\n   for value in id:sub(#timer.id+2):gmatch("[^\\t]+") do args[#args+1] = value end\n   timer:Stop(unpack(args))\n  end\n end\nend\n'
        text = helper + text
        changes.append({'adaptation': 'GUID hard-stop includes all count suffixes', 'occurrences': 1})
    if path.endswith('AvatarofSethraliss.lua'):
        text = text.replace('mod.noBossDeathKill = true', 'mod:DisableOnMobKillDetection() -- RVCOMPLETE: supported old-Core safeguard')
        text = re.sub('mod.onlyHighest = true[^\\n]*', '-- RVCOMPLETE: module-local highest-ever healing progress, no global Core hook.\nlocal rvHighestHP = 0\nfunction mod:UNIT_HEALTH(unit)\n if self:GetUnitCreatureId(unit) == 133392 then\n  local maximum = UnitHealthMax(unit)\n  local hp = maximum and maximum > 0 and UnitHealth(unit) / maximum * 100\n  if hp and hp > rvHighestHP then rvHighestHP = hp end\n end\nend\nfunction mod:GetLowestBossHealth()\n local hp = self:GetBossHP(133392)\n if hp and hp > rvHighestHP then rvHighestHP = hp end\n return rvHighestHP > 0 and rvHighestHP or nil\nend', text)
        text = text.replace('function mod:OnCombatStart(delay)', 'function mod:OnCombatStart(delay)\n\trvHighestHP = 0')
        text = text.replace('function mod:OnCombatEnd()', 'function mod:OnCombatEnd()\n\trvHighestHP = 0')
        text = text.replace('mod:RegisterEventsInCombat(', 'mod:RegisterEventsInCombat(\n\t"UNIT_HEALTH boss1",', 1)
        from source_spans import move_aura_branch
        text = move_aura_branch(text,268008)
        changes.append({'adaptation': 'unreachable donor Snake Charm dispel branch joined with first aura branch', 'occurrences': 1})
        changes.append({'adaptation': 'Avatar module-local highest-ever HP and real no-mob-kill flag', 'occurrences': 1})
    if not re.search('^mod:SetZone\\(', text, re.M):
        text = text.replace('mod:RegisterCombat(', 'mod:SetZone() -- RVCOMPLETE: pinned Core needs explicit addon map IDs\n\nmod:RegisterCombat(', 1)
        changes.append({'adaptation': 'restore old-Core explicit zone registration', 'occurrences': 1})
    return (text, changes)

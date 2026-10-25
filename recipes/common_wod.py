"""Named Legion API compatibility operations; no target or old-pack runtime input."""
from pathlib import Path
import re,json
from inputs_only import S,T,N,sha
from source_spans import function_text,format_function
B=Path(__file__).parent;assert not T
out=B/'common_research_only';rows=[]
def apply_smbg_pulse(src):
    src = src.replace('mod:SetRevision("20231026112110")', 'mod:SetRevision("20261025000501")\n-- SMBGPULSE 0.0.5 TEST / SBGPULSE-20261025-05; overlay for DBM RV*+ 0.1.15.')
    src = src.replace('"UNIT_DIED"', '"UNIT_DIED",\n "RANGE_DAMAGE", "SPELL_DAMAGE",\n "PLAYER_REGEN_ENABLED", "PLAYER_ENTERING_WORLD", "ZONE_CHANGED_NEW_AREA"', 1)
    src = src.replace('local warnVoidPulse', 'local warnVoidPulse', 1)
    src = src.replace('local warnVoidPulse\t\t\t\t\t\t\t= mod:NewSpellAnnounce(152964, 3)', 'local warnVoidEruptions = mod:NewSpellAnnounce(394512, 3)')
    src = src.replace('local specWarnVoidEruptions\t\t\t\t\t= mod:NewSpecialWarningDodge(394512, nil, nil, nil, 2, 2)', '')
    logic = '\n-- Predictions are experimental: first contact ~3.4s; subsequent casts are\n-- corrected by each source\'s observed Pulse/Eruption. Never share source state.\nlocal pulseLocalization = DBM:GetModLocalization("SMBGTrash")\nlocal ru = GetLocale() == "ruRU"\npulseLocalization:SetWarningLocalization({SpecWarnVoidPulseCover = ru and "В укрытие!" or "Take cover!"})\npulseLocalization:SetOptionLocalization({SpecWarnVoidPulseCover = ru and "Спецпредупреждение \\"В укрытие!\\" при начале $spell:152964" or "Special warning: take cover when $spell:152964 starts"})\nlocal specWarnVoidPulseCover = mod:NewSpecialWarningDodge(152964, true, "SpecWarnVoidPulseCover", nil, 4)\nspecWarnVoidPulseCover.text = ru and "В укрытие!" or "Take cover!"\nmod:SetOptionCategory("SpecWarnVoidPulseCover", "announcepersonal")\nlocal fleeSound = "Sound\\\\Creature\\\\LadyMalande\\\\BLCKTMPLE_LadyMal_Aggro01.ogg"\nmod.DefaultOptions.SpecWarnVoidPulseCoverSWSound = {value = fleeSound}\nmod.Options.SpecWarnVoidPulseCoverSWSound = fleeSound\nlocal previousInitialize = mod.OnInitialize\nfunction mod:OnInitialize(...)\n if previousInitialize then previousInitialize(self, ...) end\n -- Only repair the invalid boolean produced by001-003. Keep valid choices.\n if type(self.Options.SpecWarnVoidPulseCoverSWSound) == "boolean" then\n  self.Options.SpecWarnVoidPulseCoverSWSound = fleeSound\n end\nend\nlocal timerVoidPulseCD = mod:NewCDSourceTimer(8.5, 152964, nil, nil, nil, 3)\nlocal countdownVoidPulse = mod:NewCountdown(3, 152964, true, nil, 3, true)\nlocal pulseSources, activeVoice, tickRunning = {}, nil, false\nlocal pulseTick\nlocal function inNecropolis()\n return select(8, GetInstanceInfo()) == 1176\nend\nlocal function pulseSource(guid)\n return type(guid) == "string" and mod:GetCIDFromGUID(guid) == 75652\nend\nlocal function pulseReset()\n mod:Unschedule(pulseTick)\n countdownVoidPulse:Cancel()\n for guid, state in pairs(pulseSources) do\n  timerVoidPulseCD:Stop(state.name, guid)\n end\n pulseSources, activeVoice, tickRunning = {}, nil, false\nend\nlocal function setPulseDeadline(guid, state, duration)\n state.due, state.warned = GetTime() + duration, false\n timerVoidPulseCD:Start(duration, state.name, guid)\nend\nlocal function ensurePulseTick()\n if not tickRunning then\n  tickRunning = true\n  mod:Schedule(0.01, pulseTick)\n end\nend\nlocal function contactPulse(guid, name)\n if not mod.Options.Enabled or not inNecropolis() or not pulseSource(guid) or pulseSources[guid] then return end\n local state = {name = name or (ru and "Дитя Бездны" or "Void Spawn"), count = 0, anchored = true}\n pulseSources[guid] = state\n setPulseDeadline(guid, state, 3.4)\n ensurePulseTick()\nend\npulseTick = function()\n if not mod.Options.Enabled or not inNecropolis() then pulseReset() return end\n local now, earliest = GetTime(), nil\n if activeVoice and now >= activeVoice.due then\n  countdownVoidPulse:Cancel()\n  activeVoice = nil\n end\n for guid, state in pairs(pulseSources) do\n  if state.due and not state.warned and (not earliest or state.due < earliest.due) then\n   earliest = {guid = guid, due = state.due, state = state}\n  end\n end\n if earliest and not activeVoice and earliest.due - now <= 3.35 then\n  -- One voice stream, anchored to the earliest source. Do not restart it\n  -- when the second mob enters combat. Nearby deadlines share this warning.\n  activeVoice = {due = earliest.due, members = {}}\n  for guid, state in pairs(pulseSources) do\n   if state.due and not state.warned and math.abs(state.due - earliest.due) <= 1 then\n    state.warned = true\n    activeVoice.members[guid] = true\n   end\n  end\n  local remaining = earliest.due - now\n  -- Legacy DBM interprets Start(<2) as its default duration; never use that.\n  if remaining >= 2 and mod.Options.SpecWarnVoidPulseCover then\n   countdownVoidPulse:Start(remaining, 3)\n  end\n elseif earliest and activeVoice and math.abs(earliest.due - activeVoice.due) <= 1 then\n  earliest.state.warned = true\n  activeVoice.members[earliest.guid] = true\n end\n if next(pulseSources) then\n  mod:Schedule(0.05, pulseTick)\n else\n  countdownVoidPulse:Cancel()\n  activeVoice, tickRunning = nil, false\n end\nend\nlocal function observedPulse(args)\n if not pulseSource(args.sourceGUID) or not inNecropolis() or not mod.Options.Enabled then return end\n local state = pulseSources[args.sourceGUID]\n if not state then\n  state = {name = args.sourceName, count = 0, anchored = false}\n  pulseSources[args.sourceGUID] = state\n end\n if mod:AntiSpam(1, 71) then specWarnVoidPulseCover:Show() end\n state.count = state.count + 1\n local interval = state.anchored and (state.count == 1 and 15.7 or state.count % 2 == 0 and 8.5 or 10.8) or 8.5\n setPulseDeadline(args.sourceGUID, state, interval)\n ensurePulseTick()\nend\nlocal function observedEruption(args)\n if not pulseSource(args.sourceGUID) or not inNecropolis() or not mod.Options.Enabled then return end\n local state = pulseSources[args.sourceGUID]\n if not state then state = {name = args.sourceName, count = 1, anchored = true} pulseSources[args.sourceGUID] = state end\n -- Eruption delays Pulse. Re-anchor instead of blindly repeating one CD.\n state.anchored, state.count = true, 1\n setPulseDeadline(args.sourceGUID, state, 7.2)\n ensurePulseTick()\nend\nfunction mod:SWING_DAMAGE(sourceGUID, sourceName, sourceFlags, sourceRaidFlags, destGUID, destName)\n if pulseSource(sourceGUID) then contactPulse(sourceGUID, sourceName)\n elseif pulseSource(destGUID) then contactPulse(destGUID, destName) end\nend\nmod.SWING_MISSED = mod.SWING_DAMAGE\nmod.RANGE_DAMAGE = mod.SWING_DAMAGE\nmod.SPELL_DAMAGE = mod.SWING_DAMAGE\n-- This Legion Core\'s RegisterEvents does not route SWING_* as CLEU.\n-- Observe only those two subevents locally; never change the shared Core.\nlocal pulseContactFrame = CreateFrame("Frame")\npulseContactFrame:RegisterEvent("COMBAT_LOG_EVENT_UNFILTERED")\npulseContactFrame:SetScript("OnEvent", function(_, _, timestamp, event, hideCaster, sourceGUID, sourceName, sourceFlags, sourceRaidFlags, destGUID, destName)\n if event == "SWING_DAMAGE" or event == "SWING_MISSED" then\n  mod:SWING_DAMAGE(sourceGUID, sourceName, sourceFlags, sourceRaidFlags, destGUID, destName)\n end\nend)\nfunction mod:PLAYER_REGEN_ENABLED() pulseReset() end\nfunction mod:PLAYER_ENTERING_WORLD() pulseReset() end\nfunction mod:ZONE_CHANGED_NEW_AREA() pulseReset() end\nlocal previousStop = mod.Stop\nfunction mod:Stop(...)\n pulseReset()\n return previousStop(self, ...)\nend\n'
    src = src.replace('function mod:SPELL_CAST_START(args)', logic + '\nfunction mod:SPELL_CAST_START(args)', 1)
    src = src.replace('elseif spellId == 152964 and self:AntiSpam(3, 4) then\n\t\twarnVoidPulse:Show()', 'elseif spellId == 152964 then\n        observedPulse(args)')
    src = src.replace('elseif spellId == 394512 then\n\t\ttimerVoidEruptionsCD:Start(nil, args.sourceName, args.sourceGUID)', 'elseif spellId == 394512 then\n        observedEruption(args)\n\t\ttimerVoidEruptionsCD:Start(nil, args.sourceName, args.sourceGUID)')
    src = src.replace('specWarnVoidEruptions:Show()\n\t\tspecWarnVoidEruptions:Play("watchstep")', 'warnVoidEruptions:Show()')
    src = src.replace('elseif cid == 75652 then--Void Spawn\n\t\ttimerVoidEruptionsCD:Stop(args.destName, args.destGUID)', 'elseif cid == 75652 then--Void Spawn\n        timerVoidPulseCD:Stop(args.destName, args.destGUID)\n        pulseSources[args.destGUID] = nil\n        if activeVoice and activeVoice.members[args.destGUID] then\n         activeVoice.members[args.destGUID] = nil\n         if not next(activeVoice.members) then countdownVoidPulse:Cancel() activeVoice = nil end\n        end\n\t\ttimerVoidEruptionsCD:Stop(args.destName, args.destGUID)')
    assert 'warnVoidPulse:Show' not in src and 'specWarnVoidEruptions:' not in src
    assert 'NewSpellAnnounce(394512, 3)' in src and 'observedPulse(args)' in src
    return src

for p,b in sorted(S['S01'].items()):
 if not p.startswith('DBM-Party-WoD/')or not p.endswith('.lua'):continue
 s=N(b).decode('utf-8-sig')
 s=s.replace('DBM_CORE_L.AUTO_ANNOUNCE_TEXTS','DBM_CORE_AUTO_ANNOUNCE_TEXTS').replace('DBM_CORE_L.AUTO_SPEC_WARN_TEXTS','DBM_CORE_AUTO_SPEC_WARN_TEXTS')
 if b'NewMod'in b:
  s=s.replace(':GetSpellName(',':GetSpellInfo(')
  s=re.sub(r'self:SetStage\((\d+)\)',r'self.vb.phase = \1',s)
  s=re.sub(r'self:GetStage\((\d+)\)',r'self.vb.phase == \1',s)
  if p.endswith(('Azzakel.lua','Terongor.lua','Oshir.lua','Kyrak.lua','Ragewing.lua','Tharbek.lua','UBRSTrash.lua','Zaela.lua')):
   s=re.sub(r'function mod:(UNIT_SPELLCAST_\w+)\(([^\n]*)spellId\)',lambda m:'function mod:'+m[1]+'('+m[2]+'bfaSpellId, _, legacySpellId)\n\tlocal spellId = legacySpellId or bfaSpellId',s)
  if '/EverBloom/'in p:
   if p.endswith(('AncientProtectors.lua','ArchmageSol.lua','Yalnu.lua')):
    s=s.replace('local wowToc = DBM:GetTOC()','local wowToc = DBM:GetTOC()\nlocal useReworkedEverbloom = (wowToc >= 100200 or wowToc == 70300)')
    s=s.replace('(wowToc >= 100200)','useReworkedEverbloom')
   s=s.replace('if (DBM:GetTOC() < 100200) then return end','')
   s=re.sub(r'DBM_COMMON_L\.([A-Z_]+_ICON)',r'DBM_CORE_\1',s)
  elif p.endswith(('Nerzhul.lua','SMBGTrash.lua')):s=re.sub(r'DBM_COMMON_L\.([A-Z_]+_ICON)',r'DBM_CORE_\1',s)
  else:s=re.sub(r'DBM_COMMON_L\.([A-Z_]+_ICON)',r'(DBM_COMMON_L and DBM_COMMON_L.\1)',s)
  if p.endswith('Rukhran.lua'):s=s.replace('DBM_COMMON_L.BREAK_LOS','((DBM_COMMON_L and DBM_COMMON_L.BREAK_LOS) or DBM_CORE_BREAK_LOS or "Break line of sight")')
  if p.endswith(('AuchTrash.lua','GRDTrash.lua','SkyreachTrash.lua','UBRSTrash.lua')):
   s=s.replace(' or self:IsTrivial()','').replace(' and not self:IsTrivial()','')
  if p.endswith(('UBRSTrash.lua',)):s=s.replace(':NewCDNPTimer(',':NewCDTimer(')
  if p.endswith(('EverBloomTrash.lua','SMBGTrash.lua','Yalnu.lua')):
   s=s.replace(':NewCDNPTimer(',':NewCDSourceTimer(')
   s=re.sub(r'(timer\w+:Start\(nil,)\s*args.sourceGUID',r'\1 args.sourceName, args.sourceGUID',s)
   if not p.endswith('Yalnu.lua'):
    s=re.sub(r'(timer\w+:(?:Stop|HardStop)\()args.destGUID',r'\1args.destName, args.destGUID',s)
   if p.endswith('EverBloomTrash.lua'):s=s.replace(':Stop(destGUID)',':Stop(args.destName, args.destGUID)').replace(':Start(nil, args.destGUID)',':Start(nil, args.destName, args.destGUID)')
  if p.endswith(('Witherbark.lua','SadanaBloodfury.lua')):
   s=re.sub(r'(timer\w+):Restart\(',r'\1:Stop()\n\t\t\1:Start(',s)
  if p.endswith('Witherbark.lua'):
   # Old trivial-content gate hides server M+ abilities; remove only its startup wrapper.
   s=re.sub(r'\tif not self:IsTrivial\(\) then\n(.*?)\n\tend',lambda m:m[1],s,count=1,flags=re.S)
  if p.endswith('Nhallish.lua'):s=s.replace(':Cancel(destName)',':Cancel(args.destName)').replace('and IsPlayer()','and args:IsPlayer()').replace('elseif spellId == 153033 and','elseif args.spellId == 153033 and')
  if p.endswith('AncientProtectors.lua'):s=re.sub(r':HardStop\([^)]*\)',':Stop()',s)
  if p.endswith('Xeritac.lua'):s=s.replace('function mod:OnCombatStart(delay)','mod.vb.phase = 1\n\nfunction mod:OnCombatStart(delay)',1)
  if p.endswith('Nokgar.lua'):s=s.replace('elseif self.vb.phase == 1 then','elseif (self.vb.phase == 1) then').replace('Start(self.vb.phase == 1 and','Start((self.vb.phase == 1) and')
  if p.endswith('BlackrockAssaultCommander.lua'):
   s=s.replace('"UNIT_TARGETABLE_CHANGED"','"UNIT_TARGETABLE_CHANGED",\n "UNIT_DIED"',1)
   s=s.replace('function mod:SupressiveFireTarget','mod.vb.phase = 1\n\nfunction mod:SupressiveFireTarget',1)
   start=s.index('function mod:UNIT_TARGETABLE_CHANGED')
   s=s[:start]+'''function mod:UNIT_TARGETABLE_CHANGED()
 if self.vb.phase == 1 then
  self.vb.phase = 2
  warnPhase2:Show()
  warnPhase2:Play("ptwo")
 end
end
function mod:UNIT_DIED(args)
 local cid = self:GetCIDFromGUID(args.destGUID)
 if cid == 79548 and self.vb.phase == 2 then
  self.vb.phase = 3
  warnPhase3:Show()
  warnPhase3:Play("pthree")
 end
end
'''
  if p.endswith('AncientProtectors.lua'):
   at=s.index('\n\tmod.vb.revitalizeCount')
   s=s[:at]+'''
 local revitalizeName = DBM:GetSpellInfo(168082)
 if wowToc == 70300 and (not revitalizeName or revitalizeName == "") then
  revitalizeName = L.RevitalizingWaters or "Revitalizing Waters"
  specWarnRevitalize.spellName = revitalizeName
  specWarnRevitalize.text = DBM_CORE_AUTO_SPEC_WARN_TEXTS.interruptcount:format(revitalizeName)
  specWarnRevitalizeDispel.spellName = revitalizeName
  specWarnRevitalizeDispel.text = DBM_CORE_AUTO_SPEC_WARN_TEXTS.dispel:format(revitalizeName)
  timerRevitalizeCD.name = revitalizeName
 end
 local function showInterruptCountCompat(warning, sourceName, count)
  if warning.text and warning.text:find("%s", 1, true) then warning:Show(sourceName, count)
  else warning:Show(count, count) end
 end
''' +s[at:]
   s=s.replace('specWarnRevitalize:Show(','showInterruptCountCompat(specWarnRevitalize, ').replace('specWarnToxicBloom:Show(','showInterruptCountCompat(specWarnToxicBloom, ')
  if p.endswith('Nerzhul.lua'):
   s=s.replace('"SPELL_CAST_START 154442"','"SPELL_CAST_START 154442 154559",\n "SPELL_CAST_SUCCESS 154559 206150",\n "SPELL_SUMMON 154350"',1)
   donor_cast = format_function(function_text(s,'SPELL_CAST_START'))
   donor_cast = donor_cast[:donor_cast.rfind('\n end')]
   at=s.index('function mod:SPELL_CAST_START')
   s=s[:at]+('local function triggerOmenOfDeath(self)\n if not self:AntiSpam(3, 1) then return end\n self:BossTargetScanner(76407, "OmenOfDeathTarget", 0.04, 15)\n timerOmenOfDeathCD:Start()\nend\nlocal function triggerRitualOfBones(self)\n if not self:AntiSpam(8, 2) then return end\n specWarnRitualOfBones:Show()\n specWarnRitualOfBones:Play("specialsoon")\n timerRitualOfBonesCD:Start()\nend\nfunction mod:SPELL_SUMMON(args)\n if args.spellId == 154350 then triggerOmenOfDeath(self) end\nend\n' + donor_cast + '\n elseif args.spellId == 154559 and self:GetCIDFromGUID(args.sourceGUID) == 76518 then triggerRitualOfBones(self) end\nend\n' + 'function mod:SPELL_CAST_SUCCESS(args)\n if (args.spellId == 154559 or args.spellId == 206150) and self:GetCIDFromGUID(args.sourceGUID) == 76518 then triggerRitualOfBones(self) end\nend\nfunction mod:UNIT_SPELLCAST_SUCCEEDED(uId, _, spellId)\n if spellId == 154671 then triggerRitualOfBones(self)\n elseif spellId == 177691 then triggerOmenOfDeath(self) end\nend\n')
 if p.endswith(('localization.en.lua','localization.ru.lua')):
  label='Живительная вода'if p.endswith('localization.ru.lua')else'Revitalizing Waters'
  # Insert immediately before the Sol selector, inside the previous Gola/Telu localization.
  marker=re.search(r'L\s*=\s*DBM:GetModLocalization\(1208\)',s)
  if marker:s=s[:marker.start()]+'L:SetMiscLocalization({ RevitalizingWaters = "'+label+'" })\n'+s[marker.start():]
 if p == 'DBM-Party-WoD/SMBurialGrounds/SMBGTrash.lua':s=apply_smbg_pulse(s)
 q=out/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(s,encoding='utf8');rows.append({'path':p,'source':'S01','source_sha256':sha(b),'output_sha256':sha(s.encode())})
(B/'reports/WOD_NAMED_ADAPTER_OUTPUTS.json').write_text(json.dumps(rows,indent=2),encoding='utf8');print('WoD adapter files',len(rows))

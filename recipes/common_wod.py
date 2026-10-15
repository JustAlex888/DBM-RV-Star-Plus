"""Named Legion API compatibility operations; no target or old-pack runtime input."""
from pathlib import Path
import re,json
from inputs_only import S,T,N,sha
from source_spans import function_text,format_function
B=Path(__file__).parent;assert not T
out=B/'common_research_only';rows=[]
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
 q=out/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(s,encoding='utf8');rows.append({'path':p,'source':'S01','source_sha256':sha(b),'output_sha256':sha(s.encode())})
(B/'reports/WOD_NAMED_ADAPTER_OUTPUTS.json').write_text(json.dumps(rows,indent=2),encoding='utf8');print('WoD adapter files',len(rows))

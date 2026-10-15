"""Named project bug/timing rules. Donor game bodies remain in the donor.
No target, old update pack, or token dictionaries are read.
"""
from pathlib import Path
import re
from inputs_only import S,N
B=Path(__file__).parent
def get(p):return N(S['S01'][p]).decode('utf-8-sig')
def put(p,s):
 q=B/'common_research_only'/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(s,encoding='utf8',newline='\n')
def change(s,old,new,count=1):
 assert s.count(old)==count,(old,s.count(old),count);return s.replace(old,new)
def repair(p,edits):
 s=get(p)
 for old,new,count in edits:s=change(s,old,new,count)
 put(p,s)
root='DBM-Party-Legion/'
repair('DBM-AntorusBurningThrone/AntorusWarCouncil.lua',[('amount == 10 or amount == 15 then','amount == 10 or amount == 15 or amount >= 19 then',1)])
repair('DBM-Nighthold/Skorpyron.lua',[('local extend = 11 - blastTotal','local extend = blastElapsed + 11 - blastTotal',1)])
for p,obj,count in [('DBM-AntorusBurningThrone/Kingaroth.lua','specWarnDecimation',1),(root+'CathedralofEternalNight/Thrashbite.lua','specWarnScornfulGaze3',1)]:
 s=get(p);s=re.sub(r'^(\s*)'+obj+r':Cancel\(\)',lambda m:m[0]+'\n'+m[1]+f'self:Unschedule({obj}.Play, {obj})',s,count=count,flags=re.M);put(p,s)
p=root+'ReturnToKarazhan/Vizaduum.lua';s=get(p)
for obj,n in [('specWarnChaoticShadows2',1),('specWarnStabilizeRift',2)]:
 pattern=r'^(\s*)'+obj+r':Cancel\(\)';assert len(re.findall(pattern,s,re.M))==n
 s=re.sub(pattern,lambda m:m[0]+'\n'+m[1]+f'self:Unschedule({obj}.Play, {obj})',s,flags=re.M)
put(p,s)
repair(root+'CathedralofEternalNight/Mephistroth.lua',[('table.wipe(addsTable)','table.wipe(addsTable)\n\ttable.wipe(demonicUpheavalTable)',1)])
for p in [root+'CourtofStars/CoSTrash.lua','DBM-Ulduar/XT002.lua']:
 s=get(p);at=s.index('\n',s.index('local L'))+1;s=s[:at]+'local DbmRV = "[DBM RV] "\n'+s[at:];put(p,s)
repair(root+'DarkheartThicket/Oakheart.lua',[('NewCDTimer(36, 212786','NewCDTimer(30, 212786',1),('timerUprootCD:Start(36.5-delay)','timerUprootCD:Start(30-delay)',2)])
repair(root+'HallsOfValor/HoVTrash.lua',[('timerRoleplay:Start(33.5)','timerRoleplay:Start(40.0)',1),('countdownRoleplay:Start(33.5)','countdownRoleplay:Start(40.0)',1)])
p=root+'HallsOfValor/Odyn.lua';s=get(p)
for obj,direction in [(2,'backright'),(3,'backleft'),(4,'frontleft'),(5,'frontcenter')]:s=change(s,'specWarnRunicBrand:Play("'+direction+'")',f'specWarnRunicBrand{obj}:Play("{direction}")')
put(p,s)
repair(root+'NeltharionsLair/Naraxas.lua',[('timerSpikedTongueCD:Start(55-delay)','timerSpikedTongueCD:Start(50.5-delay)',1),('countdownSpikedTongue:Start(55-delay)','countdownSpikedTongue:Start(50.5-delay)',1)])
repair(root+'NeltharionsLair/Rokmora.lua',[(obj+':'+method+'('+str(old)+'-delay)',obj+':'+method+'('+str(new)+'-delay)',1)for obj,method,old,new in [('warnShatter2','Schedule',18,15),('timerShatterCD','Start',23,20),('countdownShatter','Start',23,20),('timerRazorShardsCD','Start',28,25),('warnRazorShards2','Schedule',25,22)]])
repair(root+'ReturnToKarazhan/RTKTrash.lua',[('"SPELL_AURA_REMOVED 229489 230083 228280 230087 230297"','"SPELL_AURA_REMOVED 229489 230083 228280 230087 230297 228610"',1)])
repair(root+'SeatofTriumvirate/ViceroyNezhar.lua',[('timerEntropicForceCD:Start(33-delay)','timerEntropicForceCD:Start(32-delay)',1),('timerEntropicForceCD:Start(35)','timerEntropicForceCD:Start(33)',1)])
repair(root+'TheArcway/Corstilax.lua',[('timerDestabilizedOrbCD:Start(8.5-delay)','timerDestabilizedOrbCD:Start(13.0-delay)',1)])
p=root+'TheArcway/Vandros.lua';s=get(p);s=change(s,'timerForceBombD:Start(28-delay)','timerForceBombD:Start(25.5-delay)');s=change(s,'timerForceBombD:Start(45)','timerForceBombD:Start(42.5)')
s=change(s,'function mod:SPELL_CAST_START(args)','''function mod:SPELL_AURA_REMOVED(args)
 if args.spellId~=220871 then return end
 timerUnstableMana:Cancel(args.destName)
 if args:IsPlayer() then
  yellUnstableMana2:Cancel()
  self:Unschedule(specWarnUnstableMana.Play,specWarnUnstableMana)
 end
 if self.Options.SetIconOnUnstableMana then self:RemoveIcon(args.destName) end
end

function mod:SPELL_CAST_START(args)''');put(p,s)
p=root+'VaultOfWarden/Tormentorum.lua';s=get(p);s=change(s,'self.vb.phase = 1','self.vb.phase = 1\n warned_preP1, warned_preP2, warned_preP3, warned_preP4 = false, false, false, false');put(p,s)
p=root+'NeltharionsLair/Dargrul.lua';s=get(p);at=s.index('local timerMoltenCrashCD');s=s[:at]+'''if GetLocale() == "ruRU" then
 specWarnBurningHatred.text = "Раскаленный углежкур на тебе! - веди его в Кристальные шипы"
else
 specWarnBurningHatred.text = "Molten Chars is chasing you! - lead it into Crystal Spikes"
end
'''+s[at:];put(p,s)
# Separate normal adds reminder: existing Alex helper is the template, not another donor.
for lang in ['en','ru']:
 p='DBM-AntorusBurningThrone/localization.'+lang+'.lua';s=get(p)
 old,new,normal,under,module=('%s CONTROL MOBS','%s CONTROL SMALL ADDS!','%s KILL SMALL ADDS!','%s GET UNDER THE BOSS!','%s MODULE IN 5 SEC!')if lang=='en'else('%s КОНТРОЛИМ МОБОВ!','%s КОНТРОЛЬ МЕЛКИХ АДДОВ!','%s МЕЛКИХ АДДОВ УБИВАЕМ!',None,'%s МОДУЛЬ ЧЕРЕЗ 5 СЕК!')
 s=change(s,'"'+old+'"','"'+new+'",\n ProshlyapMurchalNormalAdds = "'+normal+'"')
 if under:s=change(s,'"%s THEY RAN UNDER THE BOSS"','"'+under+'"')
 at=re.search(r'L\s*=\s*DBM:GetModLocalization\(2031\)',s).start()
 before,after=s[:at],s[at:];after=re.sub(r'(^\s*ProshlyapMurchal\s*=\s*"[^"\n]*")',lambda m:m[0]+',\n RVReoriginationModule = "'+module+'"',after,count=1,flags=re.M);put(p,before+after)
p='DBM-Party-WoD/DBM-Party-WoD.toc';s=get(p);s=change(s,'## Interface: 70300','## Interface: 70300\n## Version: 0.1.14 TEST\n## X-DBM-RV-WoDRestore-Scope: all-eight-dungeons')
lines=s.splitlines(True);ever=[x for x in lines if x.startswith('EverBloom\\')];lines=[x for x in lines if not x.startswith(('EverBloom\\','SMBurialGrounds\\SMBGTrash.lua'))]
at=next(i for i,x in enumerate(lines)if x.startswith('SMBurialGrounds\\Sadana'));lines[at:at]=['SMBurialGrounds\\SMBGTrash.lua\n']
at=next(i for i,x in enumerate(lines)if x.startswith('Skyreach\\'));order=['EverBloomTrash','Witherbark','AncientProtectors','Xeritac','ArchmageSol','Yalnu'];lines[at:at]=[next(x for x in ever if x.startswith('EverBloom\\'+name+'.lua'))for name in order];put(p,''.join(lines))
print('Named small repairs emitted')
p=root+'ReturnToKarazhan/Curator.lua';s=get(p);s+='\n]] -- Close the disabled source handler block.\n';put(p,s)

"""Research recipe. Runtime input is the pinned official2018 ZIP only.
Never reads C13/I03, old pack payloads, target diffs or historical S02.
The generated five BASE bodies still need the common approved S08 supplements.
"""
from pathlib import Path
import zipfile,hashlib,re,json
from lua_lex import lex
B=Path(__file__).parent;W=B.parent
from inputs_only import inputs
ZIP=inputs['S18'][0]
PIN='b40aedcc31fc723b6cc10936447b624fbad36030efc94a8b7f30e0479153be22'
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(ZIP.read_bytes())==PIN
with zipfile.ZipFile(ZIP)as z:
 assert z.testzip()is None
 source={n.split('/',1)[1]:z.read(n).decode('utf-8-sig').replace('\r\n','\n')for n in z.namelist()if n.endswith('.lua')}
log=[]
def one(s,a,b):
 assert s.count(a)==1,(a,s.count(a))
 log.append({'operation':'SEMANTIC_REPLACE','anchor_sha256':sha(a.encode()),'reason':current_reason})
 return s.replace(a,b,1)
def function_span(s,name):
 pat='function mod:'+name+'(';start=s.index(pat)
 ts=[t for t in lex(s[start:].encode())if t[0]not in ('SPACE','COMMENT')];stack=[]
 for k,a,b,v in ts:
  if v==b'function':stack.append([v,False])
  elif v in (b'if',b'repeat'):stack.append([v,False])
  elif v in (b'for',b'while'):stack.append([v,True])
  elif v==b'do':
   if stack and stack[-1][0]in(b'for',b'while')and stack[-1][1]:stack[-1][1]=False
   else:stack.append([v,False])
  elif v==b'until':stack.pop()
  elif v==b'end':
   stack.pop()
   if not stack:return start,start+b
 raise AssertionError(name)
def edit_function(s,name,fn):
 a,z=function_span(s,name);return s[:a]+fn(s[a:z])+s[z:]
def remove_function(s,name):return edit_function(s,name,lambda body:'-- research: source method intentionally not used in preserved base')
def drop_decl(s,var):
 s,n=re.subn(r'^local\s+'+var+r'\s*=[^\n]*\n','',s,flags=re.M);assert n==1,var;return s
def variable_call(s,var,constructor=None,first=None):
 pat=r'^(local\s+'+var+r'\s*=\s*mod:)(\w+)(\()([^,\n]+)'
 def change(m):return m[1]+(constructor or m[2])+m[3]+(str(first)if first is not None else m[4])
 s,n=re.subn(pat,change,s,flags=re.M);assert n==1,var;return s
def seed(s,var,value):return re.sub(r'('+var+r':Start\()[0-9.]+(-delay\))',lambda m:m[1]+str(value)+m[2],s)
paths=['Freehold/CounciloCaptains.lua','Freehold/HarlanSweete.lua','Freehold/RingofBooty.lua','TheUnderrot/ElderLeaxa.lua','TheUnderrot/Unbound.lua']
manifest=[]
for rel in paths:
 p='DBM-Party-BfA/'+rel;s=source[p];start_log=len(log);current_reason=rel
 # Revisions are engineering metadata; use a usable explicit number, not SVN expansion.
 s=re.sub(r'mod:SetRevision\([^\n]+\)','mod:SetRevision(20261015000000)',s,count=1)
 if rel.endswith('CounciloCaptains.lua'):
  current_reason='UWoW aura258875 owns target/voice/icon; original cast continues to own its CD'
  s=one(s,'mod:RegisterCombat(','mod:SetUsedIcons(8)\nmod:RegisterCombat(')
  s=one(s,'"SPELL_CAST_START 258338 256589 257117 267522 272884 267533 272902 265088 264608 265168"','"SPELL_AURA_APPLIED 258875",\n "SPELL_AURA_REMOVED 258875",\n "SPELL_CAST_START 258338 256589 257117 281329 267522 272884 267533 272902"')
  s=re.sub(r',\s*"UNIT_DIED"','',s,count=1);s=remove_function(s,'UNIT_DIED')
  for var in ['warnConfidenceBrew','warnInvigoratingBrew','warnCausticBrew','timerTendingBarCD']:s=drop_decl(s,var)
  s=variable_call(s,'warnLuckySevens',first=281329)
  s=variable_call(s,'specWarnBlackoutBarrel',first=258875)
  at=s.index('function mod:OnCombatStart')
  s=s[:at]+'''-- Research server adapter: player aura is the authoritative target event.
function mod:SPELL_AURA_APPLIED(args)
 local spellId = args.spellId
 if spellId == 258875 then
 warnBlackoutBarrelTarget:Show(args.destName)
 if args:IsPlayer() then
  specWarnBlackoutBarrelYou:Show()
  specWarnBlackoutBarrelYou:Play("targetyou")
 else
  specWarnBlackoutBarrel:Show()
  specWarnBlackoutBarrel:Play("changetarget")
 end
 if self.Options.SetIconOnBlackoutBarrelTarget then self:SetIcon(args.destName, 8) end
 end
end
function mod:SPELL_AURA_REMOVED(args)
 local spellId = args.spellId
 if spellId == 258875 and self.Options.SetIconOnBlackoutBarrelTarget then self:RemoveIcon(args.destName) end
end
''' +s[at:]
  # Stable declaration/UI order and original handler placement; this is a named
  # ability adapter, not a target-text/AST dictionary reconstruction.
  s=re.sub(r'^(local\s+warnLuckySevens[^\n]*\n)',r'\1local warnBlackoutBarrelTarget = mod:NewTargetNoFilterAnnounce(258875, 4)\n',s,flags=re.M)
  s=re.sub(r'^(local\s+specWarnBlackoutBarrel[^\n]*\n)',r'\1local specWarnBlackoutBarrelYou = mod:NewSpecialWarningYou(258875, nil, nil, nil, 1, 2)\n',s,flags=re.M)
  s=one(s,'mod:AddRangeFrameOption(5, 267522)','mod:AddRangeFrameOption(5, 267522)\nmod:AddSetIconOption("SetIconOnBlackoutBarrelTarget", 258875, true)')
  moved=[]
  for name in ['SPELL_AURA_APPLIED','SPELL_AURA_REMOVED']:
   a,z=function_span(s,name);moved.append(s[a:z]);s=s[:a]+s[z:]
  at=s.index('function mod:SPELL_CAST_START');s=s[:at]+'\n'.join(moved)+'\n'+s[at:]
  s=variable_call(s,'timerBlackoutBarrelCD',first=46.5)
  s=variable_call(s,'timerLuckySevensCD',first=26.8)
  s=one(s,'26.8, 257117','26.8, 281329')
  s=seed(s,'timerBlackoutBarrelCD',17.3);s=seed(s,'timerLuckySevensCD',2.2)
  s=edit_function(s,'OnCombatStart',lambda body:re.sub(r'\n\tif not self:IsNormal\(\) then\s*timerTendingBarCD:Start\(8-delay\)\s*end','',body))
  def casts(body):
   body=re.sub(r'\n\t\tspecWarnBlackoutBarrel:Show\(\)\s*\n\t\tspecWarnBlackoutBarrel:Play\("changetarget"\)','',body)
   body=body.replace('elseif spellId == 257117 then','elseif spellId == 257117 or spellId == 281329 then')
   a=body.index('\n\telseif spellId == 265088');return body[:a]+'\n\tend\nend'
  s=edit_function(s,'SPELL_CAST_START',casts)
 elif rel.endswith('HarlanSweete.lua'):
  current_reason='UWoW Saber aliases413145/413147 and aura257314 retained'
  s=one(s,'"SPELL_CAST_SUCCESS 257316 257278"','"SPELL_CAST_SUCCESS 257316 257278 413145 413147"')
  s=variable_call(s,'specWarnSwiftwindSaber',first=413145)
  s=one(s,'NewCDTimer(8.9, 257316','NewCDTimer(8.9, 413145') if 'NewCDTimer(8.9, 257316'in s else s
  # Identify the timer by its variable, not another occurrence of the same ability.
  s,n=re.subn(r'(local\s+timerSwiftwindSaberCD[^\n]*?,\s*)257316',r'\g<1>413145',s);assert n==1
  s=s.replace('spellId == 194966','spellId == 257314')
  s=one(s,'elseif spellId == 257278 then','elseif spellId == 257278 or spellId == 413145 or spellId == 413147 then')
 elif rel.endswith('RingofBooty.lua'):
  current_reason='Preserved server Sharknado repeat/initial and existing RP seed values'
  s=variable_call(s,'timerSharknadoCD',first=26.8);s=seed(s,'timerSharknadoCD',23.0)
  s=one(s,'timerRP:Start(25)','timerRP:Start(25.5)');s=one(s,'timerRP:Start(35)','timerRP:Start(35.5)')
 elif rel.endswith('ElderLeaxa.lua'):
  current_reason='Preserve original AI minimum-learning timer contract rather than source hard CDs'
  for v in ['timerBloodBoltCD','timerSanguineFeastCD','timerCreepingRotCD','timerBloodMirrorCD']:s=variable_call(s,v,constructor='NewAITimer',first=13)
  for v in ['timerSanguineFeastCD','timerBloodMirrorCD','timerCreepingRotCD']:s=seed(s,v,1)
  s=one(s,'function mod:OnCombatStart(delay)','function mod:OnCombatStart(delay)\n timerBloodBoltCD:Start(1-delay)')
  s=one(s,'elseif spellId == 264603 then','elseif spellId == 264603 then\n timerBloodMirrorCD:Start()')
 elif rel.endswith('Unbound.lua'):
  current_reason='Preserve AI timers and old damage throttle; S08 BloodVisage supplement stays separate'
  s=s.replace('"SPELL_PERIODIC_DAMAGE 269838"','"SPELL_PERIODIC_DAMAGE"').replace('"SPELL_PERIODIC_MISSED 269838"','"SPELL_PERIODIC_MISSED"')
  s,n=re.subn(r',\s*"UNIT_SPELLCAST_SUCCEEDED boss1 boss2 boss3"','',s);assert n==1
  for v in ['specWarnBloodVisage','timerBloodVisageCD']:s=drop_decl(s,v)
  s=remove_function(s,'UNIT_SPELLCAST_SUCCEEDED')
  for v in ['timerVileExpulsionCD','timerCleansingLightCD']:s=variable_call(s,v,constructor='NewAITimer',first=13);s=seed(s,v,1)
  s=re.sub(r'\n\s*timerBloodVisageCD:Start\([^\n]*\)','',s)
  s=s.replace('countdownVileExpulsion:Start(6)','countdownVileExpulsion:Start(10)')
  s=s.replace('timerVileExpulsionCD:Start(6)','timerVileExpulsionCD:Start(10)')
  s=one(s,'spellId, spellName)','spellId)');s=s.replace('self:AntiSpam(2, 2)','self:AntiSpam(2, 4)').replace('specWarnGTFO:Show(spellName)','specWarnGTFO:Show()')
  s=s.replace('remainingAdds = 6','remainingAdds = 10')
 out=B/'output_research_only'/p;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(s,encoding='utf8')
 manifest.append({'path':p,'source_archive_sha256':PIN,'source_normalized_sha256':sha(source[p].encode()),'result_sha256':sha(s.encode()),'status':'RESEARCH_BASE_RECIPE_PENDING_COMPARISON','operations':log[start_log:]})
(B/'reports/RECIPE_FIVE_HISTORICAL_BASES.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
print('Generated',len(manifest),'historical bases without target/old-pack runtime reads')

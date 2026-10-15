"""Build tested active BfA bases from official2018, then add S08 reserves.
Only named server event/timing changes. No C13/I03 runtime inputs.
"""
from pathlib import Path
import re,ast,types,json
from inputs_only import S,T,N,sha
B=Path(__file__).parent;W=B.parent;assert not T
ns={'__file__':str(B/'historical_recipe.py')};exec((B/'historical_recipe.py').read_text().split('\npaths=')[0],ns);span=ns['function_span']
import merge_active as merge
from owned_adapter import adapt
from source_spans import function_text,first_branch_calls
adapt_ns=ns={'adapt':adapt}
def edit(s,old,new,count=1):assert s.count(old)==count,(old,s.count(old));return s.replace(old,new)
def decl(s,var,constructor=None,value=None):
 pattern=r'^(local\s+'+var+r'\s*=\s*mod:)(\w+)(\()([^,\n]+)'
 s,n=re.subn(pattern,lambda m:m[1]+(constructor or m[2])+m[3]+(str(value)if value is not None else m[4]),s,flags=re.M);assert n==1,var;return s
def emit(p,s,folder='active_research_only'):
 q=B/folder/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(s,encoding='utf8',newline='\n')

def donor_startup(text):
 body=function_text(text,'OnCombatStart')
 result=[body.splitlines()[0]]
 for var in ['timerFesteringHarvestCD','timerBoundlessRotCD','timerShockwaveCD','timerUpheavalCD','timerVolatilePodsCD']:
  call=re.search(re.escape(var)+r':Start\([^\n)]*\)',body)
  assert call,var
  call=re.sub(r'\([^)]*\)','(1-delay)',call[0])
  if var=='timerVolatilePodsCD':
   condition=next(x.strip()for x in body.splitlines()if x.strip().startswith('if '))
   result.append(' '+condition+' '+call+' end')
  else:result.append(' '+call)
 return '\n'.join(result)+'\nend'

def donor_success(text):
 original=function_text(text,'SPELL_CAST_SUCCESS').splitlines()
 actions=first_branch_calls(text,'UNIT_SPELLCAST_SUCCEEDED')
 assert len(actions)==3
 boundless=[x.replace('specWarnVolatilePods','specWarnBoundlessRot').replace('timerVolatilePodsCD','timerBoundlessRotCD')for x in actions]
 result=[original[0],' '+original[1].strip(),' if spellId == 259830 and self:AntiSpam(1, 2) then']
 result+=['  '+x for x in boundless]
 result+=[' elseif spellId == 273271 then']+['  '+x for x in actions]
 result+=[' elseif spellId == 259718 and self:AntiSpam(2, 1) then timerUpheavalCD:Start() end','end']
 return '\n'.join(result)

paths=['Freehold/FreeholdTrash.lua','Freehold/SkycapnKragg.lua','TheUnderrot/InfestedCrawg.lua','TheUnderrot/SporecallerZancha.lua','TheUnderrot/UnderrotTrash.lua'];rows=[]
for rel in paths:
 p='DBM-Party-BfA/'+rel;s=N(S['S18'][p]).decode('utf-8-sig');s=re.sub(r'mod:SetRevision\([^\n]*\)','mod:SetRevision(20261015000000)',s,count=1)
 if rel.endswith('SkycapnKragg.lua'):
  for var,new in [('timerPowderShotCD',10.9),('timerVilebombardmentCD','17.0'),('timerBrewCD',20.7)]:s=decl(s,var,value=new)
  for old,new in [('timerVilebombardmentCD:Start(6.2)','timerVilebombardmentCD:Start(2.0)'),('timerPowderShotCD:Start(7.3)','timerPowderShotCD:Start(5.5)'),('timerBrewCD:Start(20.6)','timerBrewCD:Start(22.2)'),('timerDiveBombCD:Start(17.7)','timerDiveBombCD:Start(13.3)')]:s=edit(s,old,new)
 elif rel.endswith('FreeholdTrash.lua'):
  s=edit(s,'274383 258199"','274383 274400 258199 272402 257870 257436 258672 258181 274507 257908"')
  s=edit(s,'"SPELL_AURA_APPLIED 257274 257476 258323 257739 257908"','"SPELL_AURA_APPLIED 257274 257476 258323 257739 257908 257397 257775 274507",\n "SPELL_CAST_SUCCESS 257747 258777 257272 257908",\n "SPELL_AURA_APPLIED_DOSE 274555",\n "UNIT_DIED",\n "UNIT_SPELLCAST_START_UNFILTERED",\n "ENCOUNTER_START"')
 elif rel.endswith('InfestedCrawg.lua'):
  s=edit(s,'"UNIT_SPELLCAST_SUCCEEDED boss1"','"SPELL_CAST_SUCCESS 260333"')
  for var in ['timerIndigestionCD','timerChargeCD','timerTantrumCD']:s=decl(s,var,constructor='NewAITimer',value=13)
  s=edit(s,'timerIndigestionCD:Start(8.3-delay)','timerIndigestionCD:Start(1-delay)');s=edit(s,'timerChargeCD:Start(20.5-delay)','timerChargeCD:Start(1-delay)')
  s=edit(s,'--if not self:IsNormal() then','if not self:IsNormal() then');s=edit(s,'--timerTantrumCD:Start(1-delay)','timerTantrumCD:Start(1-delay)');s=edit(s,'--end','end')
  s=edit(s,'elseif spellId == 260333 then','elseif spellId == 260333 and self:AntiSpam(1, 1) then');s=edit(s,'--timerTantrumCD:Start()','timerTantrumCD:Start()')
  # This modern unit-spell path must remain inactive: the server emits cast success.
  a,z=span(s,'UNIT_SPELLCAST_SUCCEEDED');s=s[:a]+s[z:]
  s+='''
function mod:SPELL_CAST_SUCCESS(args)
 if args.spellId == 260333 and self:AntiSpam(1, 1) then
  specWarnTantrum:Show()
  specWarnTantrum:Play("aesoon")
  timerTantrumCD:Start()
 end
end
'''
 elif rel.endswith('SporecallerZancha.lua'):
  s=edit(s,'"SPELL_AURA_APPLIED 259718"','"SPELL_AURA_APPLIED 259718 259830"');s=edit(s,'"SPELL_CAST_SUCCESS 259830 259718 259732"','"SPELL_CAST_SUCCESS 259830 273271 259718 259732"')
  at=s.index('local specWarnVolatilePods');s=s[:at]+'local specWarnBoundlessRot = mod:NewSpecialWarningDodge(259830, nil, nil, nil, 2, 2)\n'+s[at:]
  s=edit(s,'--local timerBoundlessRotCD','local timerBoundlessRotCD')
  for var in ['timerFesteringHarvestCD','timerBoundlessRotCD','timerVolatilePodsCD','timerShockwaveCD','timerUpheavalCD']:s=decl(s,var,constructor='NewAITimer',value=13)
  a,z=span(s,'OnCombatStart');s=s[:a]+donor_startup(s)+s[z:]
  a,z=span(s,'SPELL_AURA_APPLIED');body=s[a:z];last=body.rfind('\n\tend');body=body[:last]+'''
  if self:AntiSpam(2, 1) then timerUpheavalCD:Start() end
 elseif spellId == 259830 and self:AntiSpam(1, 2) then
  specWarnBoundlessRot:Show()
  specWarnBoundlessRot:Play("watchstep")
  timerBoundlessRotCD:Start()
'''+body[last:];s=s[:a]+body+s[z:]
  s=re.sub(r'\t\tif DBM.Options.DebugMode then\n.*?\n\t\tend','',s,count=1,flags=re.S)
  a,z=span(s,'SPELL_CAST_SUCCESS');s=s[:a]+donor_success(s)+s[z:]
  a,z=span(s,'UNIT_SPELLCAST_SUCCEEDED');s=s[:a]+s[z:]
 elif rel.endswith('UnderrotTrash.lua'):
  s=edit(s,'278961 265523"','278961 265523 266209 266201 265487 265668 278755 272592 265081 272180 413044"');s=edit(s,'"SPELL_AURA_APPLIED 265568 266107"','"SPELL_AURA_APPLIED 265568 266107 266209 265091 278789 278961 266201"');s=edit(s,'"SPELL_CAST_SUCCESS 265523"','"SPELL_CAST_SUCCESS 265523 265016 266201 266265 265668",\n "UNIT_DIED"')
  at=s.index('function mod:SPELL_CAST_START');specs=[('WickedFrenzy','Interrupt',266209,'"HasInterrupt"',1),('BoneShield','Dispel',266201,'"MagicDispeller"',1),('ShadowBoltVolley','Interrupt',265487,'"HasInterrupt"',1),('DecayingWave','Dodge',265668,'nil',2)]
  s=s[:at]+''.join(f'local specWarn{name} = mod:NewSpecialWarning{kind}({spell}, {role}, nil, nil, {level}, 2)\n'for name,kind,spell,role,level in specs)+s[at:]
  s=edit(s,'spellId == 265091 and self:CheckInterruptFilter(args.sourceGUID, false, true)','spellId == 265091')
  a,z=span(s,'SPELL_CAST_START');body=s[a:z];at=body.rfind('\n\tend');extra=''
  for name,kind,spell,role,level in specs:
   condition=' and self:CheckInterruptFilter(args.sourceGUID, false, true)'if kind=='Interrupt'else' and self:AntiSpam(2.5, 2)'if kind=='Dodge'else''
   arg=''if kind=='Dodge'else'args.sourceName';voice='kickcast'if kind=='Interrupt'else'dispelboss'if kind=='Dispel'else'watchstep'
   extra+=f'\n elseif spellId == {spell}{condition} then\n  specWarn{name}:Show({arg})\n  specWarn{name}:Play("{voice}")'
  body=body[:at]+extra+body[at:];s=s[:a]+body+s[z:]
 emit(p,s,'active_bases_research_only')
 if rel.endswith(('FreeholdTrash.lua','SporecallerZancha.lua','UnderrotTrash.lua')):s,detail=merge.merge(s,N(S['S08'][p]).decode('utf-8-sig'),p,adapt_ns['adapt'])
 else:detail={'policy':'KEEP_SERVER_TESTED_BASE'}
 emit(p,s);rows.append({'path':p,'base_donor':'S18','supplement_donor':'S08'if 'policy'not in detail else None,'result_sha256':sha(s.encode()),'detail':detail})
(B/'reports/ACTIVE_BFA_SOURCE_BUILD.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
print('Active BfA source recipes',len(rows))

"""Extend active modules without replacing their existing handlers/constructors.
Supplemental source handlers emit only missing objects; original outputs and timing remain authoritative.
This is private integration, not a distributable patch payload.
"""
from pathlib import Path
import types,re,json,sys
B=Path(__file__).parent;
from inputs_only import S,T,N,sha
import module_parser as parser

def rename_identifiers(text,mapping):
 b=text.encode('utf8'); edits=[]
 for t in parser.tokens(b):
  if t[0]=='IDENT' and t[3].decode()in mapping:edits.append((t[1],t[2],mapping[t[3].decode()].encode()))
 for a,z,new in reversed(edits):b=b[:a]+new+b[z:]
 return b.decode('utf8')

def registration_union(target,donor):
 original=parser.inventory('target',target.encode());src=parser.inventory('source',donor.encode())
 bymethod={}
 for r in original['event_registrations']+src['event_registrations']:
  key=(r['registration_method'],r['event']);bymethod.setdefault(key,[])
  for arg in r['filter']:
   if arg not in bymethod[key]:bymethod[key].append(arg)
 ts=parser.tokens(target.encode());edits=[];handled=set()
 for i in range(len(ts)-3):
  if ts[i][3]==b'mod'and ts[i+1][3]==b':'and ts[i+2][3].decode()in {k[0]for k in bymethod}and ts[i+3][3]==b'(':
   method=ts[i+2][3].decode();_,end=parser.args_at(ts,i+3)
   if method not in handled:
    lines=[json.dumps(ev+(' '+' '.join(f)if f else''))for(m,ev),f in bymethod.items()if m==method]
    new='mod:'+method+'(\n\t'+',\n\t'.join(lines)+'\n)';handled.add(method)
   else:new='-- RVCOMPLETE: consolidated above'
   edits.append((ts[i][1],ts[end][2],new.encode()))
 b=target.encode()
 for a,z,new in reversed(edits):b=b[:a]+new+b[z:]
 for method in {k[0]for k in bymethod}-handled:
  vals=[json.dumps(ev+(' '+' '.join(f)if f else''))for(m,ev),f in bymethod.items()if m==method]
  b+=('\nmod:'+method+'('+', '.join(vals)+')\n').encode()
 return b.decode()

def merge(target,source,path,adapt):
 srcinv=parser.inventory(path,source.encode());curinv=parser.inventory(path,target.encode())
 sourcefeatures=srcinv['features'];current={f.get('variable'):f for f in curinv['features']}
 # I03 semantic alias: UWoW already assigns Trade Winds to the old Lucky Sevens object.
 aliases={'timerTradeWindsVigorCD':'timerLuckySevensCD'} if path.endswith('CounciloCaptains.lua') else {}
 for alias,existing in aliases.items():current[alias]=current[existing]
 missing=[f for f in sourcefeatures if f.get('variable')not in current]
 # Same name but different underlying ability must remain a distinct new object.
 # Known server ID swaps / output-kind adaptations are deliberately preserved rather than duplicated.
 distinct=[]
 for f in sourcefeatures:
  var=f.get('variable');old=current.get(var)
  if old and parser.identity_key(old['identity'])!=parser.identity_key(f['identity']):
   if var=='specWarnGTFO'and path.endswith('UnderrotTrash.lua'):distinct.append(f)
 missing+=distinct;newvars={f['variable']for f in missing}
 originalsource=source
 first=min(f['offset']for f in sourcefeatures)
 line_start=source.rfind('\n',0,first)+1
 source=source[line_start:]
 # Remove duplicate constructors, keep actual original object for non-emitting queries.
 for f in sourcefeatures:
  var=f.get('variable')
  if var not in newvars:
   source=re.sub(r'^local\s+'+re.escape(var)+r'\s*=.*$', 'local '+var+' = '+var+' -- RVCOMPLETE: original object retained; duplicate output calls suppressed below',source,flags=re.M)
 # Remove duplicate action calls as expressions with balanced arguments; queries still use original object.
 ts=parser.tokens(source.encode());edits=[]
 actions={'Show','CombinedShow','PreciseShow','Start','Stop','Cancel','Schedule','Unschedule','Play','ScheduleVoice','CancelVoice','DelayedPlay','Yell','ShortYell','Countdown','RepeatYell','DelayedStart','StartPaused','SetTimer','Update','AddTime'}
 for i in range(len(ts)-3):
  if ts[i][0]=='IDENT'and ts[i][3].decode()in current and ts[i][3].decode()not in newvars and ts[i+1][3]==b':'and ts[i+2][3].decode()in actions and ts[i+3][3]==b'(':
   _,end=parser.args_at(ts,i+3);edits.append((ts[i][1],ts[end][2],b'do end --[[ RVCOMPLETE: original handler owns this output ]]'))
 b=source.encode()
 for a,z,new in reversed(edits):b=b[:a]+new+b[z:]
 source=b.decode()
 # Current active module owns combat identity and existing shared UI surfaces.
 source=re.sub(r'^\s*self:SetCreatureID\([^\n]+\)[^\n]*$', '-- RVCOMPLETE: original combat identity retained',source,flags=re.M)
 source,adapts=adapt(source,path)
 # Namespace additional state and helper methods so donor phase/counter updates cannot overwrite current state.
 source=re.sub(r'\b(mod|self)\.vb\.([A-Za-z_0-9]+)',r'\1.vb.rvComplete_\2',source)
 methods=list(srcinv['handlers'])
 mapping={f['variable']:'rvComplete_'+f['variable']for f in sourcefeatures if f.get('variable')}
 mapping.update({m:'RVComplete_'+m for m in methods})
 # Aliases are identifiers too; rename only tokens, never localization string keys.
 source=rename_identifiers(source,mapping)
 # The retained original objects must reference outer locals, not self-reference a new nil local.
 for var in current:
  source=source.replace('local rvComplete_'+var+' = rvComplete_'+var+' -- RVCOMPLETE:', 'local rvComplete_'+var+' = '+aliases.get(var,var)+' -- RVCOMPLETE:')
 for m in methods:
  source=source.replace('"'+m+'"','"RVComplete_'+m+'"')
 source=source.replace('self:AntiSpam(', 'self:AntiSpam(') # calls below get independent keys
 source=re.sub(r'self:AntiSpam\(([^,()]+),\s*([^()]+)\)',r'self:AntiSpam(\1, "RVComplete:"..tostring(\2))',source)
 # Only new explicit options should be added; never overwrite defaults of existing options.
 oldoptionkeys={o['args'][0]for o in curinv['options']if o['args']and isinstance(o['args'][0],str)}
 source=re.sub(r'^mod:(Add\w+Option)\("([^"]+)"[^\n]*$',lambda m:'-- RVCOMPLETE: original option kept' if m[2]in oldoptionkeys else m[0],source,flags=re.M)
 # Event handlers are dispatched by the existing method plus new supplemental method; aliases included.
 wrappers=[]
 for name in methods:
  if name.startswith(('SPELL_','UNIT_','CHAT_MSG_','RAID_BOSS_','INSTANCE_','ENCOUNTER_','OnCombat','OnTimerRecovery','OnInitialize','OnSync','OnTranscriptorSync')):
   wrappers.append('''local original_{n} = mod.{n}
function mod:{n}(...)
 if original_{n} then original_{n}(self, ...) end
 return self.RVComplete_{n}(self, ...)
end'''.format(n=name))
 # I03: baseline owns Rearm 256489; retain the donor's additional 256494 path.
 if path.endswith('RingofBooty.lua'):
  needle='rvComplete_warnRearm:Show()'
  assert source.count(needle)==1
  source=source.replace(needle,'if spellId == 256494 then '+needle+' end -- I03: no extra message for baseline 256489')
 output=registration_union(target,originalsource)+'\n\n-- RVCOMPLETE BEGIN: donor additions, original outputs remain authoritative\ndo\n'+source+'\n'+'\n'.join(wrappers)+'\nend\n-- RVCOMPLETE END\n'
 return output,{'new_objects':[{'variable':f['variable'],'kind':f['family'],'id':f['identity']}for f in missing],'preserved_original_feature_variables':list(current),'supplemental_methods':methods,'adaptations':adapts,'policy':'ORIGINAL_HANDLERS_FIRST; ONLY_MISSING_OBJECTS_EMIT_IN_SUPPLEMENT; SOURCE_STATE_NAMESPACED'}

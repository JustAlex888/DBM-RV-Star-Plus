"""Read-only source capability inventory. Never writes an addon/candidate tree."""
from pathlib import Path
import sys,json,re,collections,csv,hashlib
BASE=Path(__file__).parent;R=BASE/'reports';R.mkdir(parents=True,exist_ok=True)

from inputs_only import S,T,P,N,sha
from lua_lex import lex

def tokens(b):
 b=N(b);return [t for t in lex(b,False) if t[0] not in ('SPACE','COMMENT')]
def txt(ts):return b' '.join(t[3] for t in ts).decode('utf8',errors='replace')
def atom(ts):
 if not ts:return None
 if len(ts)==1:
  k,a,z,v=ts[0]
  if k=='NUMBER':
   try:return int(v,16) if v.lower().startswith(b'0x') else int(v)
   except ValueError:return float(v)
  if k=='STRING':
   if v[:1] in (b'"',b"'"):return v[1:-1].decode('utf8',errors='replace')
   m=re.match(rb'\[(=*)\[',v)
   if m:return v[len(m[0]):-len(m[0])].decode('utf8',errors='replace')
 if len(ts)==2 and ts[0][3]==b'-' and ts[1][0]=='NUMBER':return -atom([ts[1]])
 return 'EXPR:'+txt(ts)

def args_at(ts,i):
 assert ts[i][3]==b'('
 stack=[b')'];args=[];start=i+1;j=i+1
 while j<len(ts):
  v=ts[j][3]
  if v in (b'(',b'[',b'{'):stack.append({b'(':b')',b'[':b']',b'{':b'}'}[v])
  elif v==stack[-1]:
   stack.pop()
   if not stack:
    if j>start:args.append(ts[start:j])
    return args,j
  elif v==b',' and len(stack)==1:args.append(ts[start:j]);start=j+1
  j+=1
 raise ValueError(('unclosed call',i,txt(ts[i:i+8])))

def function_end(ts,start):
 stack=[]
 for j in range(start,len(ts)):
  v=ts[j][3]
  if v==b'function':stack.append([v,False])
  elif v in (b'for',b'while'):stack.append([v,True])
  elif v in (b'if',b'repeat'):stack.append([v,False])
  elif v==b'do':
   if stack and stack[-1][0] in (b'for',b'while') and stack[-1][1]:stack[-1][1]=False
   else:stack.append([v,False])
  elif v==b'until':
   if stack and stack[-1][0]==b'repeat':stack.pop()
  elif v==b'end':
   if stack:stack.pop()
   if not stack:return j
 return len(ts)-1

def family(method):
 if not method.startswith('New') or method=='NewMod':return None
 if method.endswith('Timer'):return 'TIMER'
 if method.startswith('NewSpecialWarning'):return 'SPECIAL_WARNING'
 if 'Announce' in method:return 'ANNOUNCE'
 if 'Countdown' in method or 'Countout' in method:return 'COUNTDOWN'
 if 'Yell' in method or 'Say' in method:return 'YELL'
 if method=='NewVoice':return 'VOICE'
 return 'OTHER_CONSTRUCTOR'

def identity_key(value):
 if isinstance(value,int) and value<0:return 'EJ:'+str(-value)
 if isinstance(value,str) and re.fullmatch(r'ej\d+',value):return 'EJ:'+value[2:]
 return str(value)

def inventory(path,b):
 raw=N(b);ts=tokens(raw);calls=[];features=[];regs=[];mods=[];options=[];handlers={};aliases={};warnings=[]
 for i in range(len(ts)-3):
  # Colon/dot calls, excluding method declarations.
  if ts[i][0]=='IDENT' and ts[i+1][3] in (b':',b'.') and ts[i+2][0]=='IDENT' and ts[i+3][3]==b'(' and not(i and ts[i-1][3]==b'function'):
   recv=ts[i][3].decode();name=ts[i+2][3].decode()
   aa,end=args_at(ts,i+3);av=[atom(a) for a in aa]
   row={'receiver':recv,'method':name,'args':av,'args_text':[txt(a) for a in aa],'line':raw[:ts[i][1]].count(b'\n')+1,'offset':ts[i][1]}
   if i>=2 and ts[i-1][3]==b'=' and ts[i-2][0]=='IDENT':row['variable']=ts[i-2][3].decode()
   elif i>=2 and ts[i-2][3]==b'local' and ts[i-1][0]=='IDENT':row['unassigned_local']=ts[i-1][3].decode()
   calls.append(row)
   if recv=='DBM' and name=='NewMod':mods.append(row)
   if recv=='mod' and (fam:=family(name)):
    idpos=1 if (fam=='TIMER' and name!='NewBerserkTimer') or fam=='COUNTDOWN' else 0
    ident=av[idpos] if len(av)>idpos else None
    features.append({**row,'family':fam,'identity':ident,'key':fam+'|'+identity_key(ident)})
   if recv in ('mod','self') and name.startswith('Register') and 'Event' in name:
    for a in aa:
     val=atom(a)
     if not isinstance(val,str) or val.startswith('EXPR:'):continue
     parts=val.split()
     if not parts:continue
     regs.append({'event':parts[0],'filter':parts[1:],'line':row['line'],'registration_method':name})
   if recv=='mod' and name.startswith(('Add','SetUsedIcons')):options.append(row)
  if ts[i][3]==b'function' and ts[i+1][3] in (b'mod',b'self') and ts[i+2][3] in (b':',b'.') and ts[i+3][0]=='IDENT':
   name=ts[i+3][3].decode();end=function_end(ts,i);body=ts[i:end+1]
   ids=[]
   for j in range(len(body)-2):
    if body[j][3] in (b'spellId',b'spellid') and body[j+1][3] in (b'==',b'~=') and body[j+2][0]=='NUMBER':ids.append(int(body[j+2][3]))
    if body[j][3] in (b'IsSpellID',b'IsSpellId') and body[j+1][3]==b'(':
     args,_=args_at(body,j+1);ids.extend(x for x in (atom(a) for a in args) if isinstance(x,int))
   handlers[name]={'line':raw[:ts[i][1]].count(b'\n')+1,'end_line':raw[:ts[end][2]].count(b'\n')+1,'spell_conditions':sorted(set(ids)),'body_token_sha256':sha(b' '.join(t[3] for t in body)),'tokens':len(body)}
  if i+6<len(ts) and ts[i][3]==b'mod' and ts[i+1][3]==b'.' and ts[i+2][0]=='IDENT' and ts[i+3][3]==b'=' and ts[i+4][3]==b'mod' and ts[i+5][3]==b'.' and ts[i+6][0]=='IDENT':aliases[ts[i+2][3].decode()]=ts[i+6][3].decode()
 for name,original in aliases.items():
  if original in handlers and name not in handlers:handlers[name]={**handlers[original],'alias_of':original}
 for f in features:
  var=f.get('variable') or f.get('unassigned_local')
  uses=[c for c in calls if var and c['receiver']==var]
  f['uses']=[{k:c[k] for k in ('method','args','args_text','line')} for c in uses]
  f['identifier_occurrences']=sum(t[0]=='IDENT' and t[3]==var.encode() for t in ts) if var else None
  f['passed_as_function_argument']=bool(var and any(ts[j][3]==var.encode() and j and ts[j-1][3] in (b'(',b',') and j+1<len(ts) and ts[j+1][3] in (b',',b')') for j in range(len(ts))))
 return {'path':path,'sha256':sha(b),'bytes':len(b),'module_definitions':mods,'feature_counts':dict(collections.Counter(f['family'] for f in features)),'features':features,'event_registrations':regs,'handlers':handlers,'options':options,'stub_marker':b'Dungeon-specific server mechanics and cooldowns intentionally NOT PORTED' in raw,'disabled_module':any(c['receiver']=='mod' and c['method']=='Disable' for c in calls),'all_numeric_tokens':sorted({int(t[3]) for t in ts if t[0]=='NUMBER' and re.fullmatch(rb'\d+',t[3])}),'unassigned_constructor_locals':[{'name':f['unassigned_local'],'method':f['method'],'line':f['line']} for f in features if 'unassigned_local' in f]}

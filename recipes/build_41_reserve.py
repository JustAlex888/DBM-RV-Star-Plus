"""Rebuild selected reserves from S08+owned API adapter+explicit creatureID data.
No target Lua/C13 ZIP/old pack is read by this process.
"""
from pathlib import Path
import ast,re,json
from inputs_only import S,T,N,sha
B=Path(__file__).parent;W=B.parent;assert not T
from owned_adapter import adapt
ns={'adapt':adapt}
config=json.loads((B/'reserve_config.json').read_text())
rows=[]
for c in config:
 raw=S['S08'][c['source_path']];text,detail=ns['adapt'](N(raw).decode('utf-8-sig'),c['path'])
 if c['server_creature_ids']:
  new='mod:SetCreatureID('+', '.join(c['server_creature_ids'])+')'
  text,n=re.subn(r'mod:SetCreatureID\([^)]*\)',new,text,count=1);assert n==1
 out=B/'reserve_research_only'/c['path'];out.parent.mkdir(parents=True,exist_ok=True);out.write_text(text,encoding='utf8')
 rows.append({'path':c['path'],'source':'S08','source_sha256':sha(raw),'result_sha256':sha(text.encode()),'adapter':detail})
assert len(rows)==41
(B/'reports/SOURCE_ONLY_41_RESERVES.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
print('Rebuilt41reserves from S08+API adapter+explicit CreatureID data')

"""Source-only research process, using generated bases and existing owned adapter code."""
from pathlib import Path
import ast,types,json,sys,re
B=Path(__file__).parent;W=B.parent
from inputs_only import S,T,N,sha
assert not T
# Existing integration routines are engineering code, not reconstructed gameplay payload.
import merge_active as merge
from owned_adapter import adapt
adapt_ns=ns={'adapt':adapt}
out=B/'supplemented_research_only';rows=[]
for p in sorted((B/'output_research_only').rglob('*.lua')):
 rel=p.relative_to(B/'output_research_only').as_posix();old=p.read_text(encoding='utf8')
 if rel.endswith('ElderLeaxa.lua'):result=old;detail={'policy':'KEEP_AI_BASE'}
 else:result,detail=merge.merge(old,N(S['S08'][rel]).decode('utf-8-sig'),rel,ns['adapt'])
 q=out/rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(result,encoding='utf8')
 rows.append({'path':rel,'base_sha256':sha(old.encode()),'S08_sha256':sha(S['S08'][rel]),'result_sha256':sha(result.encode()),'detail':detail})
(B/'reports/SOURCE_ONLY_SUPPLEMENTED_FIVE.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
print('Five source-derived modules supplemented. C13/I03 unavailable to this process.')

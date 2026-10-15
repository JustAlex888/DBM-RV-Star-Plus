from pathlib import Path
import sys,json,hashlib,traceback
B=Path(__file__).resolve().parent;sys.path.insert(0,str(B/'source/R12'))
from engine.pack_v2 import VerifiedPack
from engine.recipe_runtime import build
pack=VerifiedPack(next((B/'source/R12/UpdatePacks').glob('*.zip')))
sources={'S01':B.parent/'patcher_three_source_20261015/S01_PUBLIC_COMMIT.zip','S08':B.parent/'three_source_i03_ii_c_20261015/build_inputs_only/S08.zip','S18':B.parent/'three_source_i03_ii_c_20261015/build_inputs_only/S18.zip'}
build(pack,sources,B/'source_recipe_work',B/'source_output')
out=Path('\\\\?\\'+str(B/'source_output'));bad=[]
for p,v in pack.files.items():
 data=(out/p).read_bytes()
 if hashlib.sha256(data).hexdigest()!=v['sha256']:bad.append(p)
assert not bad,bad
(B/'reports/SOURCE_EQUIVALENCE.json').write_text(json.dumps({'status':'PASS','files':len(pack.files),'content_tree_sha256':pack.target['tree_digest_sha256'],'pack_sha256':pack.sha256,'compared_against':'unchanged 0.1.14 pack target.json','new_donor_count':0,'inputs':{sid:hashlib.sha256(p.read_bytes()).hexdigest()for sid,p in sources.items()}},indent=2),encoding='utf8')
print('EXACT SOURCE EQUIVALENCE PASS',len(pack.files))

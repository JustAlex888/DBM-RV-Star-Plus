"""Run only the recipe implementation shipped with the executable.
Update packs supply validated data, never Python or other host executables.
"""
from pathlib import Path
import sys,os,json,runpy,shutil,threading,contextlib,io
from engine import dbm_rv_phase8_engine as core
from engine.dbm_rv_installer import long_path

LOCK=threading.Lock()
SCRIPTS=('historical_recipe.py','build_supplemented_five.py','build_41_reserve.py','build_locales.py','common_wod.py','common_gui.py','common_small_repairs.py','build_owned_history.py','post_history_repairs.py','active_bfa.py','antorus_source_rules.py','bfa_load_graph.py')
IMPORTS=('inputs_only','lua_lex','module_parser','merge_active','owned_adapter','source_spans')

def code_root():
 return Path(sys._MEIPASS)/'recipe_code' if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]/'recipes'

def build(pack,selections,work,output):
 """Build inside a new session directory; restore process imports/environment."""
 with LOCK:
  work=long_path(work);output=long_path(output);work.mkdir(exist_ok=False)
  root=code_root();index=json.loads((root/'CODE_SHA256.json').read_text(encoding='utf8'))
  for name,h in index.items():
   assert '/'not in name and name.endswith('.py')
   data=(root/name).read_bytes()
   if core.sha256_bytes(data)!=h:raise core.StagingFailure('RECIPE_CODE_HASH_MISMATCH',name)
   (work/name).write_bytes(data)
  pack.materialize(work)
  inputs=work/'inputs';inputs.mkdir();(work/'reports').mkdir()
  for sid,path in selections.items():shutil.copyfile(path,inputs/(sid+'.zip'))
  oldpath=list(sys.path);oldenv=os.environ.get('DBM_SOURCE_DIR');oldmods={k:sys.modules.pop(k,None)for k in IMPORTS}
  text=io.StringIO()
  try:
   sys.path.insert(0,str(work));os.environ['DBM_SOURCE_DIR']=str(inputs)
   with contextlib.redirect_stdout(text):
    for row in pack.data_json('own_addons_manifest.json'):
     p=row['path'];data=pack.data_bytes('own_addons/'+p)
     if core.sha256_bytes(data)!=row['result_sha256']:raise core.StagingFailure('OWN_ADDON_SHA_MISMATCH',p)
     q=work/'common_research_only'/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(data)
    for script in SCRIPTS:runpy.run_path(str(work/script),run_name='__main__')
   from inputs_only import S
   import zipfile
   with zipfile.ZipFile(work/'APPROVED_AUDIO.zip')as audio:
    for row in pack.plan:
     p=row['path']
     if row['mode']=='GENERATED':data=(work/row['folder']/p).read_bytes()
     elif row['mode']=='DONOR':data=S[row['donor']][row['source_path']]
     else:data=audio.read(row['bundle_path'])
     wanted=pack.files[p]
     if core.sha256_bytes(data)!=wanted['sha256']or len(data)!=wanted['size']:raise core.StagingFailure('RECIPE_RESULT_MISMATCH',p)
     q=Path(output)/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(data)
   core.write_json(work/'reports/RECIPE_BUILD.json',{'scripts':list(SCRIPTS),'files':len(pack.files),'donor_ids':sorted(S),'implementation':'FROZEN_OWN_CODE_ONLY','external_pack_host_code_executed':False,'log':text.getvalue()})
  finally:
   sys.path[:]=oldpath
   if oldenv is None:os.environ.pop('DBM_SOURCE_DIR',None)
   else:os.environ['DBM_SOURCE_DIR']=oldenv
   for k,v in oldmods.items():
    sys.modules.pop(k,None)
    if v is not None:sys.modules[k]=v

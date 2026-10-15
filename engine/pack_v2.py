"""Data-only source-preserving pack. Host implementation belongs to the EXE."""
from pathlib import Path
import json,zipfile,stat
from engine import dbm_rv_phase8_engine as core
from engine.pack_v1 import require,relpath,dbm_path,hash64

SCHEMA='dbm-rv-star-plus/source-pack-v2'
FOLDERS={'common_research_only','owned_history_research_only','active_research_only','antorus_research_only','locale_research_only','supplemented_research_only','reserve_research_only'}
DATA_FIXED={'build_plan.json','reserve_config.json','own_addons_manifest.json','APPROVED_AUDIO.zip','owned_project_rules/project_repairs.json','owned_project_rules/antorus_rvfix.json'}
OWN_PATHS={'DBM-RV-Sounds/DBM-RV-Sounds.lua','DBM-RV-Sounds/DBM-RV-Sounds.toc','DBM-RV-Sounds/THIRD_PARTY_NOTICES.txt','DBM-RV-UWoW-BFA-Sounds/DBM-RV-UWoW-BFA-Sounds.lua','DBM-RV-UWoW-BFA-Sounds/DBM-RV-UWoW-BFA-Sounds.toc','DBM-RV-UWoW-Compat/Compat.lua','DBM-RV-UWoW-Compat/DBM-RV-UWoW-Compat.toc'}
ALLOW={'pack.json','target.json','source_gates.json'}|{'data/'+x for x in DATA_FIXED}|{'data/own_addons/'+p for p in OWN_PATHS}
class VerifiedPack:
 def __init__(self,path):
  self.path=Path(path).absolute();require(self.path.is_file(),'PACK_NOT_FOUND');require(not core.is_reparse(self.path),'PACK_REPARSE_REJECTED');require(self.path.stat().st_size<32*1024*1024,'PACK_OVERSIZED')
  self.sha256=core.sha256_file(self.path);self._bytes={}
  try:
   with zipfile.ZipFile(self.path)as z:
    total=0;seen=set()
    for n in z.infolist():
     relpath(n.filename);require(not n.is_dir(),'PACK_DIRECTORY_ENTRY_FORBIDDEN');require(n.filename.casefold()not in seen,'PACK_CASE_COLLISION');seen.add(n.filename.casefold())
     mode=n.external_attr>>16;require(not stat.S_ISLNK(mode)and not(mode&0o170000 and not stat.S_ISREG(mode)),'PACK_UNSAFE_ENTITY')
     total+=n.file_size;require(n.file_size<=8*1024*1024 and total<=32*1024*1024,'PACK_OVERSIZED');require(not n.flag_bits&1,'PACK_ENCRYPTION_FORBIDDEN');require(n.filename in ALLOW,'PACK_UNEXPECTED_MEMBER',n.filename)
     self._bytes[n.filename]=z.read(n)
    require(set(self._bytes)==ALLOW,'PACK_MEMBER_SET_MISMATCH');require(z.testzip()is None,'PACK_CRC_FAILED')
   self.pack=self._json('pack.json');require(self.pack.get('schema')==SCHEMA,'PACK_SCHEMA_UNSUPPORTED');require(self.pack.get('recipe_api')=='I03_SOURCE_RULES_V1','PACK_RECIPE_API_UNSUPPORTED')
   require(self.pack.get('member_hashes')=={p:core.sha256_bytes(b)for p,b in self._bytes.items()if p!='pack.json'},'PACK_MEMBER_SHA_MISMATCH')
   self.target=self._json('target.json');self.files=self.target['files'];self.roots=self.target['roots'];require(len(self.files)==891 and len(self.roots)==29,'PACK_TARGET_SCOPE_INVALID')
   require(self.roots==sorted({dbm_path(p).split('/')[0]for p in self.files}),'PACK_ROOT_SET_MISMATCH')
   require(not {'DBM-Uldir','DBM-Azeroth-BfA','DBM-RV-FreezeTrace','DBM-RV-TestHarness'}&set(self.roots),'PACK_MANAGED_ROOT_FORBIDDEN')
   for p,v in self.files.items():hash64(v['sha256'],'PACK_TARGET_SHA_INVALID');require(type(v['size'])is int and 0<=v['size']<=8*1024*1024,'PACK_TARGET_SIZE_INVALID')
   require(core.aggregate_digest({p:v['sha256']for p,v in self.files.items()})==self.target['tree_digest_sha256'],'PACK_TARGET_DIGEST_MISMATCH')
   self.sources=self._json('source_gates.json')['sources'];require(set(self.sources)=={'S01','S08','S18'},'PACK_SOURCE_IDS_INVALID')
   from engine.source_pins import PINS
   for sid,g in self.sources.items():
    require(set(g['archive_sha256_allowlist'])==set(PINS[sid]),'PACK_SOURCE_PIN_MISMATCH',sid)
    for p,h in g['files'].items():dbm_path(p);hash64(h,'PACK_SOURCE_SHA_INVALID')
   self.plan=self.data_json('build_plan.json')['paths'];require(len(self.plan)==len(self.files)and{r['path']for r in self.plan}==set(self.files),'PACK_PLAN_SET_MISMATCH')
   for r in self.plan:
    dbm_path(r['path']);require(r['mode']in('GENERATED','DONOR','APPROVED_MEDIA'),'PACK_PLAN_MODE_INVALID')
    if r['mode']=='GENERATED':require(r['folder']in FOLDERS,'PACK_RECIPE_FOLDER_INVALID')
    elif r['mode']=='DONOR':require(r['donor']in self.sources and dbm_path(r['source_path'])in self.sources[r['donor']]['files'],'PACK_SOURCE_REFERENCE_INVALID')
    else:relpath(r['bundle_path']);hash64(r['sha256'],'PACK_ASSET_SHA_INVALID')
   for r in self.data_json('reserve_config.json'):
    require(dbm_path(r['path'])in self.files and dbm_path(r['source_path'])in self.sources['S08']['files'],'PACK_RESERVE_PATH_INVALID')
    require(r['server_creature_ids']is None or all(str(v).isdigit()for v in r['server_creature_ids']),'PACK_CREATURE_IDS_INVALID')
   addons=self.data_json('own_addons_manifest.json');require({r['path']for r in addons}==OWN_PATHS and len(addons)==7,'PACK_OWN_ADDON_SET_INVALID')
   for name in ['project_repairs','antorus_rvfix']:
    for r in self.data_json('owned_project_rules/'+name+'.json')['records']:
     require(dbm_path(r['path'])in self.files and r['path']in self.sources['S01']['files'],'PACK_REPAIR_PATH_INVALID')
   self.records=[{'target_relative_path':p,'result_size_bytes':v['size'],'result_file_sha256':v['sha256'],'operation_type':'SOURCE_RECIPE'}for p,v in sorted(self.files.items())]
  except core.EngineFailure:raise
  except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile,UnicodeError)as e:raise core.BaselineFailure('PACK_MALFORMED',str(e))from e
 def _json(self,p):return json.loads(self._bytes[p].decode('utf-8'))
 def data_json(self,p):return self._json('data/'+p)
 def data_bytes(self,p):return self._bytes['data/'+p]
 def materialize(self,work):
  for p,b in self._bytes.items():
   if not p.startswith('data/'):continue
   q=Path(work)/p[5:];q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
 def identity(self):return{k:self.pack[k]for k in ['product','version','build_id','provenance']}|{'pack_sha256':self.sha256,'roots':len(self.roots),'files':len(self.files),'tree_digest_sha256':self.target['tree_digest_sha256']}

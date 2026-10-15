"""Actual shipped EXE, three real pinned sources, isolated target fixtures only."""
from pathlib import Path
import os,sys,subprocess,json,zipfile,hashlib,shutil,time
B=Path(__file__).resolve().parent;PKG=B/'final_install_readback/DBM-RV-Patcher';EXE=PKG/'DBM-RV-Patcher.exe';P=Path('\\\\?\\'+str(B/'frozen_uat_final_r12'));P.mkdir(exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
pack=next((PKG/'UpdatePacks').glob('*.zip'))
with zipfile.ZipFile(pack)as z:target=json.loads(z.read('target.json'))
sources={'S01':B.parent/'patcher_three_source_20261015/S01_PUBLIC_COMMIT.zip','S08':B.parent/'three_source_i03_ii_c_20261015/build_inputs_only/S08.zip','S18':B.parent/'three_source_i03_ii_c_20261015/build_inputs_only/S18.zip'}
rows=[];exe_sha=sha(EXE.read_bytes())
def snapshot(root):
 return{p.relative_to(root).as_posix():sha(p.read_bytes())for p in root.rglob('*')if p.is_file()and not p.relative_to(root).as_posix().startswith('Interface/DBM-RV-Patcher-Backup/')}
def fixture(name,existing=False):
 c=P/name;c.mkdir();wow=c/'wow';add=wow/'Interface/AddOns';add.mkdir(parents=True)
 if existing:
  with zipfile.ZipFile(B.parent/'patcher_protected_20261014/downloads/C13_CANONICAL_03.zip')as z:z.extractall(add)
 for rel,data in [('IndependentAddon/keep.lua',b'keep addon'),('DBM-RV-FreezeTrace/keep.lua',b'keep freeze'),('DBM-RV-TestHarness/keep.lua',b'keep harness'),('DBM-PrivateExtra/keep.lua',b'keep private'),('DBM-random.txt',b'keep file')]:
  p=add/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 (wow/'WTF').mkdir();(wow/'WTF/KEEP.txt').write_bytes(b'UNTOUCHED_WTF')
 return c,wow,add
def invoke(c,wow,name,apply=False,checked=None,overrides=None,extra=(),pack_override=None):
 dest=c/(name+'.json');env=dict(os.environ,LOCALAPPDATA=str(c/'local'));env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
 args=[str(EXE),'--headless-apply'if apply else'--headless-check','--target',str(wow).removeprefix('\\\\?\\'),'--result-json',str(dest)]
 for sid,p in (sources| (overrides or {})).items():
  if p is not None:args+=['--source-'+sid.lower(),str(p)]
 if checked:
  d=checked['details'];args+=(['--approved-backup-path',d['backup_planned_path']] if d.get('backup_planned_path') else []);args+=['--expected-inventory',d['inventory_digest_sha256'],'--expected-mode',d['mode'],'--expected-pack-sha256',d['content_identity']['pack_sha256']]
 if pack_override:args+=['--pack',str(pack_override)]
 args+=list(extra);start=time.monotonic();r=subprocess.run(args,env=env,cwd=str(P),capture_output=True,timeout=90)
 assert dest.exists(),(name,r.returncode,r.stderr[-900:]);result=json.loads(dest.read_text(encoding='utf8'));result['test_process_exit']=r.returncode;result['test_elapsed']=round(time.monotonic()-start,2);return result
def save(name,r,ok):
 rows.append({'name':name,'pass':bool(ok),'outcome':r.get('outcome'),'reason':r.get('reason_code'),'rollback':r.get('rollback_status'),'writes':r.get('target_write_count')});(B/'reports/FINAL_FROZEN_R12_UAT.json').write_text(json.dumps({'exe_sha256':exe_sha,'passed':sum(x['pass']for x in rows),'failed':sum(not x['pass']for x in rows),'cases':rows},ensure_ascii=False,indent=2),encoding='utf8');print(name,rows[-1],flush=True);assert ok,(name,r)
def installed(add):return{p:sha((add/p).read_bytes())for p in target['files']}
def matches(add):return installed(add)=={p:v['sha256']for p,v in target['files'].items()}
c,wow,add=fixture('fresh');before=snapshot(wow);r=invoke(c,wow,'check');save('FROZEN_THREE_PUBLIC_DONORS_CHECK',r,r['outcome']=='READY'and snapshot(wow)==before and r['target_write_count']==0)
r=invoke(c,wow,'apply',True,r);save('FROZEN_FRESH_INSTALL_ALL891',r,r['outcome']=='SUCCESS'and matches(add)and (wow/'WTF/KEEP.txt').read_bytes()==b'UNTOUCHED_WTF')
before=snapshot(wow);r=invoke(c,wow,'already',True);save('FROZEN_ALREADY_INSTALLED_NO_WRITES',r,r['outcome']=='ALREADY_PATCHED'and snapshot(wow)==before)
c,wow,add=fixture('replacement',True);keep={k:v for k,v in snapshot(wow).items()if not any(k.startswith('Interface/AddOns/'+root+'/')for root in target['roots'])}
checked=invoke(c,wow,'check');assert checked['outcome']=='READY';r=invoke(c,wow,'replace',True,checked);save('FROZEN_REPLACE_C13_PRESERVE_DIAGNOSTICS_WTF',r,r['outcome']=='SUCCESS'and matches(add)and all(snapshot(wow).get(k)==v for k,v in keep.items()))
for fault in ['mid_commit_failure','post_commit_corruption']:
 c,wow,add=fixture(fault,True);before=snapshot(wow);checked=invoke(c,wow,'check');r=invoke(c,wow,'fault',True,checked,extra=['--test-fault',fault]);save('FROZEN_ROLLBACK_'+fault,r,r['rollback_status']=='ROLLBACK_VERIFIED'and snapshot(wow)==before)
c,wow,add=fixture('missing');before=snapshot(wow);r=invoke(c,wow,'missing',overrides={'S18':None});save('FROZEN_MISSING_THIRD_REFUSED',r,r['outcome']not in('READY','SUCCESS')and r['target_write_count']==0 and snapshot(wow)==before)
c,wow,add=fixture('wrong');bad=c/'bad.zip';bad.write_bytes(b'wrong third archive');before=snapshot(wow);r=invoke(c,wow,'wrong',overrides={'S18':bad});save('FROZEN_WRONG_THIRD_SHA_REFUSED',r,r['reason_code']=='SOURCE_S18_SHA_MISMATCH'and snapshot(wow)==before and r['target_write_count']==0)
c,wow,add=fixture('stale',True);r=invoke(c,wow,'check');changed=add/'DBM-Core/userchange.txt';changed.write_bytes(b'changed after CHECK');before=snapshot(wow);r=invoke(c,wow,'apply',True,r);save('FROZEN_CHECK_APPLY_TARGET_CHANGE_REFUSED',r,r['reason_code']=='TARGET_CHANGED_SINCE_USER_CHECK'and snapshot(wow)==before and r['target_write_count']==0)
c,wow,add=fixture('pack_code');bad=c/'codepack.zip'
with zipfile.ZipFile(pack)as z,zipfile.ZipFile(bad,'w')as out:
 for n in z.namelist():out.writestr(n,z.read(n))
 out.writestr('data/evil.py','raise RuntimeError("MUST_NOT_EXECUTE")')
before=snapshot(wow);r=invoke(c,wow,'badpack',pack_override=bad);save('FROZEN_PACK_HOST_SCRIPT_REFUSED',r,r['reason_code']=='PACK_UNEXPECTED_MEMBER'and snapshot(wow)==before)
c,wow,add=fixture('backup_refusal',True);checked=invoke(c,wow,'check');before=snapshot(wow)
for suffix,backup in [('outside',str(c/'outside/20261015-201344-dde948dbfa95')),('badname',checked['details']['backup_planned_path']+'-bad')]:
 bad=json.loads(json.dumps(checked));bad['details']['backup_planned_path']=backup;r=invoke(c,wow,suffix,True,bad);save('FROZEN_BACKUP_POLICY_REFUSED_'+suffix,r,r['reason_code']=='BACKUP_PATH_POLICY_MISMATCH'and r['target_write_count']==0 and snapshot(wow)==before)
assert sha(EXE.read_bytes())==exe_sha
print('ALL FROZEN CASES PASS',len(rows))


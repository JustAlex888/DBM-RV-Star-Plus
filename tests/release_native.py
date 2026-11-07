"""Exercise the actual packaged EXE in disposable WoW fixtures, never a live game."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]
def main():
 pkg=ROOT/'release/package/DBM-RV-Patcher';exe=pkg/'DBM-RV-Patcher.exe'
 testroot=ROOT/'release/native-tests';testroot.mkdir(exist_ok=False)
 urls={'S01':'https://codeload.github.com/Aleksart163/DBM-RV-LEG/zip/e97f138de7d3ba846e8a2ee36a35730831e04e27','S08':'https://codeload.github.com/DeadlyBossMods/DBM-Dungeons/zip/2dbfa75c48d654044b597a233c378f1af00d2b62','S18':'https://codeload.github.com/DeadlyBossMods/DeadlyBossMods/zip/8ac1ee4fe4ad54c7de126a39109cf324fd8109ed'}
 sources={}
 local=os.environ.get('DBM_TEST_SOURCE_DIR')
 for sid,url in urls.items():
  p=Path(local)/(sid+'.zip')if local else testroot/(sid+'.zip')
  if not local:urllib.request.urlretrieve(url,p)
  sources[sid]=p
 pack=next((pkg/'UpdatePacks').glob('*.zip'))
 with zipfile.ZipFile(pack)as z:target=json.loads(z.read('target.json'))
 sha=lambda b:hashlib.sha256(b).hexdigest()
 def fixture(name):
  c=testroot/name;add=c/'wow/Interface/AddOns';add.mkdir(parents=True)
  for rel,data in [('DBM-RV-FreezeTrace/keep.lua',b'freeze'),('DBM-RV-TestHarness/keep.lua',b'harness'),('IndependentAddon/keep.lua',b'addon')]:
   p=add/rel;p.parent.mkdir();p.write_bytes(data)
  wtf=c/'wow/WTF/keep.txt';wtf.parent.mkdir();wtf.write_bytes(b'WTF preserved');return c,add
 def snapshot(c):return {p.relative_to(c/'wow').as_posix():sha(p.read_bytes())for p in(c/'wow').rglob('*')if p.is_file()and 'DBM-RV-Patcher-Backup'not in p.parts}
 def invoke(c,name,apply=False,checked=None,extra=()):
  result=c/(name+'.json');args=[str(exe),'--headless-apply'if apply else'--headless-check','--target',str(c/'wow'),'--result-json',str(result)]
  for sid,p in sources.items():args+=['--source-'+sid.lower(),str(p)]
  if checked:
   d=checked['details'];args+=['--expected-inventory',d['inventory_digest_sha256'],'--expected-mode',d['mode'],'--expected-pack-sha256',d['content_identity']['pack_sha256']]
   if d.get('backup_planned_path'):args+=['--approved-backup-path',d['backup_planned_path']]
  r=subprocess.run(args+list(extra),env=dict(os.environ,LOCALAPPDATA=str(c/'local')),capture_output=True,timeout=150)
  assert result.exists(),(name,r.returncode,r.stderr[-600:]);return json.loads(result.read_text(encoding='utf8'))
 rows=[]
 c,add=fixture('fresh');before=snapshot(c);checked=invoke(c,'check');assert checked['outcome']=='READY'and before==snapshot(c);rows.append('read_only_check')
 result=invoke(c,'apply',True,checked);assert result['outcome']=='SUCCESS',result
 assert all(sha((add/p).read_bytes())==v['sha256']for p,v in target['files'].items());rows.append('fresh_all_891_hashes')
 assert all(snapshot(c).get(k)==v for k,v in before.items());rows.append('preserve_wtf_and_diagnostics')
 before=snapshot(c);result=invoke(c,'already',True);assert result['outcome']=='ALREADY_PATCHED'and before==snapshot(c);rows.append('already_installed_no_change')
 for fault in ['mid_commit_failure','post_commit_corruption']:
  c,add=fixture(fault);p=add/'DBM-Core/old.lua';p.parent.mkdir();p.write_bytes(b'old');before=snapshot(c);checked=invoke(c,'check');assert checked['outcome']=='READY',checked
  result=invoke(c,'fault',True,checked,['--test-fault',fault]);assert result['rollback_status']=='ROLLBACK_VERIFIED'and before==snapshot(c),result;rows.append('rollback_'+fault)
 report={'status':'STATIC_VERIFIED','actual_packaged_exe_sha256':sha(exe.read_bytes()),'target_digest':target['tree_digest_sha256'],'checks':rows,'real_wow':'NOT_USED','game_status':'READY_FOR_TEST'}
 (ROOT/'release/NATIVE_TESTS.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
if __name__=='__main__':main()

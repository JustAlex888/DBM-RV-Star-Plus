"""Publish only after the actual packaged EXE passed the native fixture tests."""
from pathlib import Path
import hashlib,json,os,urllib.request,urllib.error,urllib.parse
ROOT=Path(__file__).resolve().parents[1]
def main():
 report=json.loads((ROOT/'release/NATIVE_TESTS.json').read_text())
 assert report['status']=='STATIC_VERIFIED'and len(report['checks'])==6
 exe=ROOT/'release/package/DBM-RV-Patcher/DBM-RV-Patcher.exe'
 assert hashlib.sha256(exe.read_bytes()).hexdigest()==report['actual_packaged_exe_sha256']
 repo=os.environ['GH_RELEASE_REPOSITORY'];assert repo=='JustAlex888/DBM-RV-Star-Plus'
 token=os.environ['GH_RELEASE_TOKEN'];tag='v0.1.17-test'
 headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'DBM-RV-release017','X-GitHub-Api-Version':'2022-11-28'}
 def request(url,data=None,method=None,mime='application/json'):
  raw=json.dumps(data).encode()if isinstance(data,dict)else data
  req=urllib.request.Request(url,data=raw,method=method,headers=headers|{'Content-Type':mime})
  with urllib.request.urlopen(req,timeout=120)as response:return json.load(response)
 api='https://api.github.com/repos/'+repo
 try:
  request(api+'/releases/tags/'+tag)
 except urllib.error.HTTPError as e:
  if e.code!=404:raise
 else:raise RuntimeError('Existing release must never be overwritten automatically')
 notes=(ROOT/'RELEASE_NOTES.md').read_text(encoding='utf8')
 manifest=json.loads((ROOT/'release/SHA256.json').read_text())
 notes+='\n\nПроверки готового Windows EXE: установка 891 файла с проверкой SHA, сохранение WTF и диагностики, повторная установка без записи, два сценария отката — PASS. Это не игровой тест новых изменений.\n\nSHA-256:\n'
 for name,v in manifest.items():notes+='\n`'+name+'`\n`'+v['sha256']+'`\n'
 release=request(api+'/releases',{'tag_name':tag,'target_commitish':os.environ['GH_RELEASE_COMMIT'],'name':'DBM RV*+ 0.1.17 TEST — installer 0.2.11','body':notes,'draft':True,'prerelease':True},'POST')
 for name,v in manifest.items():
  p=ROOT/'release'/name;raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==v['sha256']
  asset=request(release['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(name),raw,'POST','application/zip')
  assert asset['size']==len(raw)
  print('Uploaded',name,v['sha256'],flush=True)
 result=request(api+'/releases/'+str(release['id']),{'draft':False,'prerelease':True},'PATCH')
 print('PUBLISHED',result['html_url'])
if __name__=='__main__':main()

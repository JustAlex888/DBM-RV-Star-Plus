"""Correct release documents while preserving the already tested executable/pack."""
from pathlib import Path
import hashlib,json,os,subprocess,urllib.request,urllib.parse,zipfile
ROOT=Path(__file__).resolve().parents[1]
def main():
 repo=os.environ['GH_RELEASE_REPOSITORY'];assert repo=='JustAlex888/DBM-RV-Star-Plus'
 headers={'Authorization':'Bearer '+os.environ['GH_RELEASE_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'DBM-RV-release-docs'}
 def request(url,data=None,method=None,mime='application/json'):
  raw=json.dumps(data).encode()if isinstance(data,dict)else data
  with urllib.request.urlopen(urllib.request.Request(url,data=raw,method=method,headers=headers|{'Content-Type':mime}),timeout=120)as r:
   return json.load(r)if r.status!=204 else None
 api='https://api.github.com/repos/'+repo;tag='v0.1.17-test';release=request(api+'/releases/tags/'+tag)
 out=ROOT/'release';out.mkdir();install=next(a for a in release['assets']if a['name'].endswith('-INSTALL.zip'));source=next(a for a in release['assets']if a['name'].endswith('-SOURCE.zip'))
 original=out/'original.zip';urllib.request.urlretrieve(install['browser_download_url'],original)
 assert hashlib.sha256(original.read_bytes()).hexdigest()=='779f7f47725aaf0190cea4988c60629e69bbfde00c9ce6b3cb9355ac6fc21ccb'
 path=out/install['name'];changed=[]
 with zipfile.ZipFile(original)as z,zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9)as dest:
  for n in z.namelist():
   raw=z.read(n)
   if n.endswith('/README_RU.txt')or n.endswith('/README_EN.txt'):
    raw=('\n'.join(line for line in raw.decode('utf8').splitlines()if 'diagnostics/'not in line)+'\n').encode('utf8')
   elif n.endswith('/Licenses/THIRD_PARTY_NOTICES.md'):raw=(ROOT/'THIRD_PARTY_NOTICES.md').read_bytes()
   if raw!=z.read(n):changed.append(n)
   dest.writestr(n,raw)
 assert len(changed)==3,changed
 with zipfile.ZipFile(path)as z:
  assert z.testzip()is None
  assert hashlib.sha256(z.read('DBM-RV-Patcher/DBM-RV-Patcher.exe')).hexdigest()=='0b41fe904ab5a49d58bc7a1af812785e9cb542cfd4adc2692211e830755b63b1'
  packs=[n for n in z.namelist()if '/UpdatePacks/'in n]
  assert len(packs)==1 and hashlib.sha256(z.read(packs[0])).hexdigest()=='770ef8abf51f211c76952224eb72f2864e3fd2a1fe64e79c694576075e1bb384'
 tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0');src=out/source['name']
 assert not any(n.startswith('diagnostics/')for n in tracked)
 with zipfile.ZipFile(src,'w',zipfile.ZIP_DEFLATED,compresslevel=9)as z:
  for n in sorted(filter(None,tracked)):z.write(ROOT/n,n)
 manifest={p.name:{'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in [path,src]}
 body=(ROOT/'RELEASE_NOTES.md').read_text(encoding='utf8')+'\n\nИсправлены только материалы выпуска. Проверенные EXE и игровой пакет сохранены без изменений.\n\nSHA-256:\n'
 for name,v in manifest.items():body+='\n`'+name+'`\n`'+v['sha256']+'`\n'
 request(api+'/releases/'+str(release['id']),{'body':body},'PATCH')
 for old,p in [(install,path),(source,src)]:
  uploaded=request(release['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(p.name+'.clean'),p.read_bytes(),'POST','application/zip');assert uploaded['size']==p.stat().st_size
  request(api+'/releases/assets/'+str(old['id']),method='DELETE')
  request(api+'/releases/assets/'+str(uploaded['id']),{'name':p.name},'PATCH')
 ref=request(api+'/git/ref/tags/'+tag);assert ref['object']['sha']=='a8490c95a3b462fddacf9fe4e4b8ba2de65623d7'
 request(api+'/git/refs/tags/'+tag,{'sha':os.environ['GH_RELEASE_COMMIT'],'force':False},'PATCH')
 print(json.dumps({'status':'PASS','documentation_only':True,'unchanged_exe_and_pack':True,'assets':manifest}))
if __name__=='__main__':main()

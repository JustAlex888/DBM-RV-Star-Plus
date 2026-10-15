"""Own-window frozen GUI contract; off-screen, no mouse/keyboard control."""
from pathlib import Path
import subprocess,json,os
B=Path(__file__).resolve().parent;exe=B/'final_install_readback/DBM-RV-Patcher/DBM-RV-Patcher.exe';out=B/'reports/gui';out.mkdir(exist_ok=True)
rows=[]
for lang,page,scale in [('RU',1,1.0),('RU',2,1.0),('EN',1,1.0),('EN',2,1.5)]:
 name=f'{lang}_page{page}_{scale}';j=out/(name+'.json');image=out/(name+'.png');env=dict(os.environ);env.pop('PYTHONHOME',None);env.pop('PYTHONPATH',None)
 r=subprocess.run([str(exe),'--ui-self-test','--ui-language',lang,'--ui-test-page',str(page),'--ui-test-scale',str(scale),'--ui-test-screenshot',str(image),'--result-json',str(j)],env=env,cwd=B,timeout=60,capture_output=True)
 assert j.exists(),(name,r.returncode,r.stderr);data=json.loads(j.read_text());rows.append({'case':name,'exit':r.returncode,'result':data,'image':str(image)});print(name,data['outcome'],flush=True)
 (B/'reports/FINAL_FROZEN_R12_GUI.json').write_text(json.dumps({'cases':rows,'status':'PASS'if all(x['result']['outcome']=='PASS'for x in rows)else'FAIL','interaction':'OWN_WINDOW_OFFSCREEN_NO_USER_INPUT_CONTROL'},ensure_ascii=False,indent=2),encoding='utf8');assert r.returncode==0,data


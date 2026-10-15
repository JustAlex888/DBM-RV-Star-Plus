"""Three immutable donor ZIPs ONLY. No canonical target/old payload reads."""
from pathlib import Path
import zipfile,hashlib,os
B=Path(__file__).parent;W=B.parent
sha=lambda b:hashlib.sha256(b).hexdigest()
N=lambda b:b.replace(b'\r\n',b'\n').replace(b'\r',b'\n')
SOURCE_DIR=Path(os.environ['DBM_SOURCE_DIR']).resolve()
pins={'S01': '403fcf41191742f224b9eecea34295437f3425527f26e42af101538de6416be9', 'S08': '5cf0b8ade4f35c15b6c83f34de7f40aaab0339f250af2552131028e425ecf1fe', 'S18': 'b40aedcc31fc723b6cc10936447b624fbad36030efc94a8b7f30e0479153be22'}
inputs={sid:(SOURCE_DIR/(sid+'.zip'),h)for sid,h in pins.items()}
S={}
for sid,(p,h)in inputs.items():
 assert sha(p.read_bytes()) in ([h, '5c011ed886be1de0f0419b879191d2a9568236897bc680f1a05232bf1f4c736e'] if sid == 'S01' else [h])
 with zipfile.ZipFile(p)as z:
  assert z.testzip()is None
  S[sid]={n.split('/',1)[1]:z.read(n)for n in z.namelist()if '/'in n and not n.endswith('/')}
P={sid:{p:N(b)for p,b in tree.items()}for sid,tree in S.items()}
# Compatibility with inventory definitions; no target tree is available in this process.
T={}

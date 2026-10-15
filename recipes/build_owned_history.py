"""Apply attributed, readable project repairs to the pinned source only."""
from pathlib import Path
import json
from inputs_only import S,sha
B=Path(__file__).parent
data=json.loads((B/'owned_project_rules/project_repairs.json').read_text(encoding='utf8'))
for row in data['records']:
 assert not row['historical_secondary_donors']
 source=S[row['donor']][row['path']];assert sha(source)==row['source_sha256']
 for e in row['edits']:
  pos=e['offset'];end=pos+e['remove_bytes'];assert sha(source[pos:end])==e['remove_sha256']
  source=source[:pos]+e['project_text'].encode()+source[end:]
 assert sha(source)==row['result_sha256']
 q=B/'owned_history_research_only'/row['path'];q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(source)
print('Own historical repairs built',len(data['records']))

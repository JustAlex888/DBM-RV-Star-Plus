"""Legion metadata and all ten historical dungeon load entries, from S18 TOC."""
from pathlib import Path
import re
from inputs_only import S,N
B=Path(__file__).parent;p='DBM-Party-BfA/DBM-Party-BfA.toc';s=N(S['S18'][p]).decode('utf8')
s=s.replace('80000','70300').replace('## Interface: 70300','## Interface: 70300\n## Version: 0.1.14 TEST')
lines=s.splitlines();lines=[l for l in lines if not l.startswith(('## Title-zh','## X-DBM-Mod-Name-zh'))]
at=next(i for i,l in enumerate(lines)if l.startswith('## Title:'));lines.insert(at+1,lines[at].replace('## Title:','## Title-ruRU:').replace('Party-BfA','Подземелья BFA'))
for i,l in enumerate(lines):
 if l.startswith('## X-DBM-Mod-SubCategoriesID:'):
  lines[i:i+1]=["## X-DBM-Mod-SubCategories: Atal'Dazar,Freehold,King's Rest,Shrine of the Storm,Siege of Boralus,Temple of Sethraliss,The MOTHERLODE!!,The Underrot,Tol Dagor,Waycrest Manor","## X-DBM-Mod-SubCategories-ruRU: Атал'Дазар,Вольная гавань,Гробница королей,Святилище Штормов,Осада Боралуса,Храм Сетралис,ЗОЛОТАЯ ЖИЛА!!!,Подгнилье,Тол Дагор,Усадьба Уэйкрестов"];break
s='\n'.join(lines)+'\n';s=s.replace('## X-DBM-Mod-Name-deDE: Gruppe (BfA)','## X-DBM-Mod-Name-deDE: Gruppe (Battle for Azeroth)').replace('## X-DBM-Mod-MinExpansion: 7','## X-DBM-Mod-MinExpansion: 6').replace('TheMotherload\\Azerokk.lua','TheMotherload\\Tikali.lua')
lines=s.splitlines();at=next(i for i,l in enumerate(lines)if l.startswith('localization.'));lines=[l for l in lines if not l.startswith('localization.')];lines[at:at]=['localization.'+lang+'.lua'for lang in ['en','de','es','it','ru','tw','kr','cn']]
s='\n'.join(lines)+'\n## X-UWoW-Compat-Build: UPATCH-20261015-01\n## X-UWoW-Compat-Scope: all-ten-historical-BfA-dungeons\n';q=B/'common_research_only'/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(s,encoding='utf8',newline='\n')

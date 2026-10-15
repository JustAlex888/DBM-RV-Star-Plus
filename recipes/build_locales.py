"""Explicit source-derived locale compatibility recipe, never imports target text.
Small legacy label spellings are readable compatibility data, not embedded Lua bodies.
Their public provenance/attribution gate remains separate.
"""
from pathlib import Path
import re,json
from inputs_only import S,T,N,sha
B=Path(__file__).parent;assert not T
english=N(S['S18']['DBM-Party-BfA/localization.en.lua']).decode('utf-8-sig')
rp=re.search(r'openingRP\s*=\s*("[^\n]+")',english)[1].replace('Gurgthok','Gurthok')
glossary={
 'cn':{'诸王之眠小怪':'国王之眠小怪','塞塔里斯神庙小怪':'塞塔里斯神殿小怪','暴富矿区小怪':'安德麦小怪'},
 'en':{'The MOTHERLODE!! Trash':'The Undermine Trash'},
 'kr':{'왕들의 안식처 일반몹':'왕의 안식처 일반몹','폭풍의 사원 일반몹':'폭풍의 제단 일반몹','보랄러스 공성전 일반몹':'보랄러스의 공성 일반몹','왕노다지 광산!! 일반몹':'언더마인 일반몹','웨이크레스트 저택 일반몹':'웨이크레스트 장원 일반몹'}}
rows=[]
for lang in ['cn','en','kr']:
 p='DBM-Party-BfA/localization.'+lang+'.lua';s=N(S['S18'][p]).decode('utf-8-sig')
 if lang=='cn':
  # The retained base lacks these optional RP snippets and empty selectors.
  s,n=re.subn(r'L:SetMiscLocalization\(\{\s*openingRP[^\n]+\n\}\)','',s);assert n==2,n
  for mid in [2171,2170,2172,2173]:s,n=re.subn(r'^L\s*=\s*DBM:GetModLocalization\('+str(mid)+r'\)\s*$','',s,flags=re.M);assert n==1,(mid,n)
 elif lang=='en':s=s.replace('Gurgthok','Gurthok')
 elif lang=='kr':
  # Retain the known English Ring RP trigger, omit the unused Stormsong trigger.
  matches=list(re.finditer(r'L:SetMiscLocalization\(\{\s*openingRP[^\n]+\n\}\)',s));assert len(matches)==2
  for i,m in reversed(list(enumerate(matches))):s=s[:m.start()]+('L:SetMiscLocalization({\n openingRP = '+rp+'\n})'if i==0 else '')+s[m.end():]
 for old,new in glossary[lang].items():assert s.count(old)==1,old;s=s.replace(old,new)
 base=s
 # Same donor Council warning strings required by the common S08 supplement.
 src=N(S['S08'][p]).decode('utf-8-sig');m=re.search(r'L\s*=\s*DBM:GetModLocalization\(2093\)',src)
 if m and 'warnGoodBrew'not in s:
  end=re.search(r'\nL\s*=\s*DBM:GetModLocalization\(',src[m.end():]);block=src[m.start():m.end()+end.start()]if end else src[m.start():]
  s+='\n-- donor Council supplement\ndo\nlocal L\n'+block+'\nend\n'
 q=B/'locale_research_only'/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(s,encoding='utf8')
 rows.append({'path':p,'source18_sha256':sha(S['S18'][p]),'source08_sha256':sha(S['S08'][p]),'legacy_base_result_sha256':sha(base.encode()),'result_sha256':sha(s.encode()),'label_changes':glossary[lang],'reason':'Preserve existing legacy label/RP contract; not a claim of automatic own copyright'})
for lang in ['de','es','it','ru','tw']:
 p='DBM-Party-BfA/localization.'+lang+'.lua';src=N(S['S08'][p]).decode('utf-8-sig');cut=src.find('-- <<<Operation: Mechagon');s=src[:cut]if cut>=0 else src
 q=B/'locale_research_only'/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(s,encoding='utf8')
 rows.append({'path':p,'source08_sha256':sha(S['S08'][p]),'result_sha256':sha(s.encode()),'reason':'Approved S08 localization; exclude Mechagon as agreed'})
(B/'reports/SOURCE_ONLY_LOCALE_RECIPE.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
print('Built3retained+5supplemental locales from pinned sources and explicit label/RP edits')

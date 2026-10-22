"""Named GT026 display and GUI bug repairs on the pinned Alex sources.
Foreign GUI/layout is retained from the source, including cloned XML nodes.
"""
from pathlib import Path
import re,copy,xml.etree.ElementTree as ET
from inputs_only import S,N
B=Path(__file__).parent
def emit(p,s):
 q=B/'common_research_only'/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(s,encoding='utf8',newline='\n')
def source(p):return N(S['S01'][p]).decode('utf-8-sig')
def once(s,a,b):
 assert s.count(a)==1,(a,s.count(a));return s.replace(a,b,1)
p='DBM-GUI/DBM-GUI.lua';s=source(p)
s=once(s,'noteSpellName = DBM:GetSpellInfo(spellId)','if spellId then\n\t\t\t\t\tnoteSpellName = DBM:GetSpellInfo(tonumber(spellId)) or noteSpellName\n\t\t\t\tend')
for a,b in [('not self.frame.mytype == "area"','self.frame.mytype ~= "area"'),('not self.frame.mytype == "panel"','self.frame.mytype ~= "panel"'),('not type(frame) == "table"','type(frame) ~= "table"')]:s=once(s,a,b)
start=s.index('\t-- Set Revision //');end=s.index('\tDBM_GUI_OptionsFrameWebsite:SetText',start)
s=s[:start]+'''\t-- Companion metadata describes the adaptation; original Core revision is preserved.
 local compatVersion = GetAddOnMetadata and GetAddOnMetadata("DBM-RV-UWoW-Compat", "Version") or nil
 if type(compatVersion) ~= "string" or compatVersion == "" then compatVersion = "0.1.15 TEST" end
 DBM_GUI_OptionsFrameRevision:SetText(L.PatchGitHub or "")
 local patchLink = CreateFrame("Button", nil, DBM_GUI_OptionsFrame)
 patchLink:SetAllPoints(DBM_GUI_OptionsFrameRevision)
 patchLink:RegisterForClicks("LeftButtonUp")
 patchLink:SetScript("OnClick", function()
  DBM:ShowUpdateReminder(nil, nil, L.PatchGitHubDialog or DBM_COPY_URL_DIALOG, "https://github.com/JustAlex888/DBM-RV-Star-Plus")
 end)

 if L.TranslationBy then
  DBM_GUI_OptionsFrameTranslation:SetText(L.TranslationLine or (L.TranslationByPrefix .. L.TranslationBy .. "   •   " .. L.Credits))
 end
 DBM_GUI_OptionsFrameBFAPatch:SetText((L.UWoWPatchCredits or "DBM RV*+ v%s — Just Alex 888 (Ломоносов x1)"):format(compatVersion))
'''+s[end:]
s=once(s,'DBM:ShowUpdateReminder(nil, nil, DBM_COPY_URL_DIALOG, "https://github.com/Aleksart163/DBM-RV")','DBM:ShowUpdateReminder(nil, nil, L.OriginalDBMRVDialog or DBM_COPY_URL_DIALOG, "https://github.com/Aleksart163/DBM-RV")');emit(p,s)
strings={
'en':{'PatchGitHubDialog':'DBM RV*+ update page. Copy this link with Ctrl+C and open it in your browser.','Website':'Original DBM-RV: |cFF73C2FBhttps://github.com/Aleksart163/DBM-RV|r','WebsiteButton':'Original DBM-RV','OriginalDBMRVDialog':'Link to the original DBM-RV by Aleksart163, not the UWoW DBM RV Patch update page.','UWoWPatchCredits':'|cffffd200DBM RV*+ v%s — WoD/BfA content adaptation for UWoW — Just Alex 888 (Ломоносов x1)|r','PatchGitHub':'|cffffd200Patch GitHub:|r |cff73c2fbhttps://github.com/JustAlex888/DBM-RV-Star-Plus|r','TranslationLine':'|cffffd200UWoW adaptation — Aleksart163 (Куплиняшка x100)   •   Special thanks: Danzo (Qfastrun x100)|r'},
'ru':{'PatchGitHubDialog':'Страница обновлений DBM RV*+. Скопируйте ссылку сочетанием Ctrl+C и откройте её в браузере.','TranslationByPrefix':'|cffffd200Адаптация под uwow.biz — |r','TranslationBy':'|cffffd200Aleksart163 (Куплиняшка x100)|r','Credits':'|cffffd200Особая благодарность: Danzo (Qfastrun x100)|r','TranslationLine':'|cffffd200Адаптация под uwow.biz — Aleksart163 (Куплиняшка x100)   •   Особая благодарность: Danzo (Qfastrun x100)|r','Website':'|cffffd200Оригинальный DBM-RV:|r |cff73c2fbhttps://github.com/Aleksart163/DBM-RV|r','WebsiteButton':'Оригинал DBM-RV','OriginalDBMRVDialog':'Ссылка на оригинальный DBM-RV от Aleksart163. Это не страница обновления UWoW DBM RV Patch.','UWoWPatchCredits':'|cffffd200DBM RV*+ v%s — адаптация контента (WoD/BfA) для UWoW — Just Alex 888 (Ломоносов x1)|r','PatchGitHub':'|cffffd200GitHub патча:|r |cff73c2fbhttps://github.com/JustAlex888/DBM-RV-Star-Plus|r'}}
for lang,fields in strings.items():
 p=f'DBM-GUI/localization.{lang}.lua';s=source(p)
 pattern=r'^L\.(?:'+ '|'.join(fields)+r')\s*=.*\n'
 at=re.search(pattern,s,re.M).start();s=re.sub(pattern,'',s,flags=re.M)
 s=s[:at]+''.join('L.'+k+' = "'+v+'"\n'for k,v in fields.items())+s[at:]
 emit(p,s)
# Clone the donor's FontString to create the added credit row; never store its XML body.
p='DBM-GUI/DBM-GUI_Templates.xml';s=source(p)
def font(name):
 m=re.search(r'<FontString name="\$parent'+name+r'"[^>]*>.*?</FontString>',s,re.S);assert m;return m
m=font('Revision');revision=m[0].replace('y="18"','y="29"');new=revision.replace('$parentRevision','$parentBFAPatch').replace('y="29"','y="13"');s=s[:m.start()]+revision+'\n'+new+s[m.end():]
for name,y in [('Translation','45'),('Website','61')]:
 m=font(name);node=m[0];node=re.sub(r'<Anchor [^>]*>','<Anchor point="BOTTOMLEFT" relativeTo="$parent" relativePoint="BOTTOMLEFT">',node);node=re.sub(r'<AbsDimension x="[^"]*" y="[^"]*"/>',f'<AbsDimension x="20" y="{y}"/>',node)
 if name=='Website':node=node.replace('inherits="GameFontNormal"','inherits="GameFontNormalSmall"')
 s=s[:m.start()]+node+s[m.end():]
button=re.search(r'<Button name="\$parentWebsiteButton".*?</Button>',s,re.S);assert button
node=button[0].replace('<AbsDimension x="96" y="22"/>','<AbsDimension x="150" y="22"/>').replace('<AbsDimension x="-20" y="0"/>','<AbsDimension x="-12" y="0"/>');s=s[:button.start()]+node+s[button.end():]
s=once(s,'DBM:ShowUpdateReminder(nil, nil, DBM_COPY_URL_DIALOG)','DBM:ShowUpdateReminder(nil, nil, DBM_GUI_Translations.OriginalDBMRVDialog or DBM_COPY_URL_DIALOG, "https://github.com/Aleksart163/DBM-RV")');ET.fromstring(s);emit(p,s)
p='DBM-Party-Legion/DBM-Party-Legion.toc';emit(p,once(source(p),'## Interface: 70300','## Interface: 70300\n## Version: 0.1.15 TEST'))
p='DBM-Core/DBM-Core.toc';s=source(p)
title='|cffffd200DBM RV*+|r |cff69ccf0Адаптация контента (WoD/BfA) для UWoW|r'
s=re.sub(r'^## Title:.*$',lambda m:'## Title:'+title+'\n## Title-ruRU:'+title,s,flags=re.M)
s=once(s,'## Notes: The most working addon for keys and raids on Legion uwow.biz','## Notes: The most working addon for keys and raids on Legion uwow.biz. Patch developed on the basis of Uwow DBM RV [Modded by Aleksart163 & Danzo]. Author: Tandanu, Nitram and Aleksart163. Aleksart163 (Куплиняшка x100) and Danzo (Qfastrun x100).')
s=once(s,'## Notes-ruRU: Самый рабочий аддон под ключи и рейды на Legion uwow.biz','## Notes-ruRU: Самый рабочий аддон под ключи и рейды на Legion uwow.biz. |cffffd200Патч разработан на базе|r |cffffd200Uwow DBM RV|r |cff69ccf0[Modded by Aleksart163 & Danzo]|r. |cffffd200Автор:|r Tandanu, Nitram and Aleksart163. Aleksart163 (Куплиняшка x100) и Danzo (Qfastrun x100).')
s=once(s,'## Author: Tandanu, Nitram and Aleksart163','## Author: Just Alex 888 (Ломоносов x1)');emit(p,s)
print('GUI and branding recipes: 6 files')

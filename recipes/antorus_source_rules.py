"""Separate historical own RVFIX repairs from the old selective-port labels.
Runtime uses S01 and readable OWN RVFIX edits; direct announcement adapters and
countdown removal are explicitly authored below. No 0.6.11 bytes are input.
"""
from pathlib import Path
import json,re
from inputs_only import S,N,sha
from source_spans import function_text,format_function
B=Path(__file__).parent
def change(s,a,b,n=None):
 assert a in s,a
 if n is not None:assert s.count(a)==n,(a,s.count(a),n)
 return s.replace(a,b)
def run_owned(p):
 data=json.loads((B/'owned_project_rules/antorus_rvfix.json').read_text(encoding='utf8'))
 s=N(S['S01'][p]).decode('utf-8-sig')
 for edit in next(r for r in data['records']if r['path']==p)['edits']:
  start,end=edit['start'],edit['end'];assert sha(s[start:end].encode())==edit['old_sha256'],p
  s=s[:start]+edit['project_text']+s[end:]
 return s

def normal_helper(text):
 body=function_text(text,'ProshlyapMurchalya2')
 body=body.replace('ProshlyapMurchalya2','ProshlyapMurchalyaNormalAdds').replace('ProshlyapMurchal2','ProshlyapMurchalNormalAdds')
 body=re.sub(r'elseif[^\n]*== 3 then','else',body)
 return format_function(body)

out=B/'antorus_research_only'
p='DBM-AntorusBurningThrone/Aggramar.lua';s=run_owned(p)
# The S01 three-message helper is the source of this normal-mode variant.
# Retain its counter, scheduler and chat API; change the localization and stop condition.
at=s.index('-- Синхронизация анонсов')
helpers=normal_helper(s)
for name,original,num in [('scheduleRVFlameRend','ProshlyapMurchalya1',1),('scheduleRVHeroicAdds','ProshlyapMurchalya2',2),('scheduleRVNormalAdds','ProshlyapMurchalyaNormalAdds',2)]:
 helpers+=f'''local function {name}(self, delay)
 if DBM.Options.IgnoreRaidAnnounce2 or not self.Options.ShowProshlyapMurchal{num} or DBM:GetRaidRank() <= 0 then return end
 self:Unschedule({original})
 self.vb.proshlyap{num}Count = 0
 self:Schedule(delay, {original}, self)
end
'''
s=s[:at]+helpers+s[at:]
# Every scheduled Taeshalach voice is cancelled before being rearmed.
s=re.sub(r'^(\s*)(warnTaeshalachTech2:Schedule\()',lambda m:m[1]+'warnTaeshalachTech2:Cancel()\n'+m[1]+'self:Unschedule(warnTaeshalachTech2.Play,warnTaeshalachTech2)\n'+m[1]+m[2],s,flags=re.M)
pattern=r'if not DBM.Options.IgnoreRaidAnnounce2 and self.Options.ShowProshlyapMurchal1 and DBM:GetRaidRank\(\) > 0 then\s*prepareMessage\(self, "premsg_Aggramar_FlameRend_rw", nil, nil, 31\)\s*end'
s,n=re.subn(pattern,'scheduleRVFlameRend(self, 32-delay)',s);assert n==2,n
pattern=r'if not DBM.Options.IgnoreRaidAnnounce2 and self.Options.ShowProshlyapMurchal2 and DBM:GetRaidRank\(\) > 0 then\s*prepareMessage\(self, "premsg_Aggramar_Embers_rw", nil, nil, 2\)\s*end'
s,n=re.subn(pattern,'scheduleRVHeroicAdds(self, 3)',s);assert n==1,n
s=change(s,'if self:IsHeroic() then\n\t\t\tscheduleRVHeroicAdds','if self:IsNormal() then\n scheduleRVNormalAdds(self, 3)\n end\n if self:IsHeroic() then\n\t\t\tscheduleRVHeroicAdds',1)
s=change(s,'elseif self:IsNormal() then\n scheduleRVNormalAdds(self, 3)\n end\n if self:IsHeroic() then','if self:IsNormal() then\n scheduleRVNormalAdds(self, 3)\n end\n elseif self:IsHeroic() then',1)
for delay in ['31','53.5']:
 pattern=r'if not self:IsMythic\(\) and not DBM.Options.IgnoreRaidAnnounce2 and self.Options.ShowProshlyapMurchal1 and DBM:GetRaidRank\(\) > 0 then\s*prepareMessage\(self, "premsg_Aggramar_FlameRend_rw", nil, nil, '+re.escape(delay)+r'\)'
 s,n=re.subn(pattern,'if not self:IsMythic() then\n scheduleRVFlameRend(self, '+('32'if delay=='31'else'54.5')+')',s);assert n==1,n
s=change(s,'if self.Options.SetIconOnBlaze then','if self:IsMythic() and self.Options.SetIconOnBlaze then',2)
# Remove only calls of an already disabled source countdown; keep the timer object.
s=re.sub(r'^\s*countdownWakeofFlame:Start\([^\n]*\)','',s,flags=re.M)
# Rescheduling an aura voice must cancel the previous owned task as well.
s=re.sub(r'^(\s*)(specWarnRavenousBlaze3:Schedule\()',lambda m:m[1]+'specWarnRavenousBlaze3:Cancel()\n'+m[1]+'self:Unschedule(specWarnRavenousBlaze3.Play,specWarnRavenousBlaze3)\n'+m[1]+m[2],s,flags=re.M)
for obj in ['warnTaeshalachTech2','specWarnRavenousBlaze3']:
 pair=rf'([ \t]*{obj}:Cancel\(\)\n[ \t]*self:Unschedule\({obj}\.Play,{obj}\)\n)'
 s=re.sub(pair+pair,lambda m:m[1],s)
q=out/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(s,encoding='utf8',newline='\n')
p='DBM-AntorusBurningThrone/ArgustheUnmaker.lua';s=run_owned(p)
at=s.index('local function startProshlyapationOfMurchal3')
helpers='''local function startRVReoriginationModule(self)
 smartChat(L.RVReoriginationModule:format(DbmRV), "rw")
end
local function scheduleRVReoriginationModule(self, delay)
 if DBM.Options.IgnoreRaidAnnounce2 or not self.Options.ShowProshlyapationOfMurchal2 or DBM:GetRaidRank() <= 0 then return end
 self:Unschedule(startRVReoriginationModule)
 self:Schedule(delay, startRVReoriginationModule, self)
end
'''
s=s[:at]+helpers+s[at:]
for option in ['SetIconOnSoulBurst','SetIconOnSoulBomb','SetIconOnAvatar','SetIconGift']:s=change(s,'if self.Options.'+option+' then','if self:IsMythic() and self.Options.'+option+' then',2 if option!='SetIconGift'else 4)
for delay,new in [('40.5','41.5'),('7','8')]:
 pattern=r'if not DBM.Options.IgnoreRaidAnnounce2 and self.Options.ShowProshlyapationOfMurchal2 and DBM:GetRaidRank\(\) > 0 then\s*prepareMessage\(self, "premsg_ArgustheUnmaker_proshlyap2_rw", nil, nil, '+re.escape(delay)+r'\)\s*end'
 s,n=re.subn(pattern,'scheduleRVReoriginationModule(self, '+new+')',s);assert n==1,n
q=out/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(s,encoding='utf8',newline='\n')
print('Explicit Antorus S01 adapters emitted')

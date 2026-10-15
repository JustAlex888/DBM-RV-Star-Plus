"""Carry forward the later GT004/GT040 measured timing amendments."""
from pathlib import Path
B=Path(__file__).parent
p=B/'owned_history_research_only/DBM-Party-Legion/NeltharionsLair/Ularogg.lua'
s=p.read_text(encoding='utf8')
for a,b in [('timerStanceOfMountainCD:Start(31-delay)','timerStanceOfMountainCD:Start(60-delay)'),('countdownStanceOfMountain:Start(31-delay)','countdownStanceOfMountain:Start(60-delay)'),('warnStanceofMountain2:Schedule(26-delay)','warnStanceofMountain2:Schedule(55-delay)'),('timerSunderCD:Start(10)','timerSunderCD:Start(3)')]:
 assert s.count(a)==2,a;s=s.replace(a,b,1)
p.write_text(s,encoding='utf8',newline='\n')

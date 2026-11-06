import sys, twin, strategies as S
mode=int(sys.argv[1]) if len(sys.argv)>1 else 0
dbg=[]
import json
kw=json.loads(sys.argv[2]) if len(sys.argv)>2 else {}
c=S.dp_strategy(dbg=dbg, **kw)
log=[]
def wrap(o):
    r=c(o); log.append((o['k'],o['t'],o['fec'],o['fne'],o['soc'],r['pb'],dbg[-1][1], o['fec']+sum(r['ev'])-(r['curt'] if r['curt'] is not None else o['fne'])-r['pb']))
    return r
res=twin.simulate(wrap,mode)
print(twin.fmt(res))
best={}
for (k,t,fec,pv,soc,pb,T,g) in log:
    m=t['month']
    if m not in best or g>best[m][7]: best[m]=(k,t,fec,pv,soc,pb,T,g)
for m in sorted(best):
    k,t,fec,pv,soc,pb,T,g=best[m]
    print("m%2d k=%5d day=%3d wd=%d qh=%2d fec=%6.1f pv=%6.1f soc=%5.1f pb=%6.1f T=%6.1f g=%6.1f"%(m,k,t['day'],t['weekday'],t['qh'],fec,pv,soc,pb,T,g))

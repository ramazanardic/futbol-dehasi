import json,sys,math,datetime as dt
sys.path.insert(0,'src'); sys.path.insert(0,'scripts')
from quantfoot.evaluation.auto_learn import calibrated_probability, load_live_calibration
from nesine_kupon import is_hard_market
from quantfoot.markets.families import leg_min_ev
cal=load_live_calibration() or {}
D='tahminler/grokbottahmin/2026-11-21/'
d=json.load(open(sys.argv[1] if len(sys.argv)>1 else D+'nesine_global.json'))
dt_=json.load(open(D+'derin_tahminler.json'))
dropped={(str(r['code']),x.get('name') or x.get('label')) for r in dt_ for x in (r.get('dropped') or [])}
CUT=dt.datetime.fromisoformat('2026-11-21T16:00:00+03:00'); END=dt.datetime.fromisoformat('2026-11-22T04:00:00+03:00')
USED=set(json.loads(__import__('os').environ.get('K7_USED','[]')))|{3389665,3312729}
CORE={'Maç Sonucu','Çifte Şans','1,5 Gol Alt/Üst','2,5 Gol Alt/Üst','3,5 Gol Alt/Üst','Karşılıklı Gol','1. Yarı Sonucu'}
opts={}
for m in d['matches']:
  k=dt.datetime.fromisoformat(m['kickoff_iso'])
  if k<CUT or k>END or m['code'] in USED: continue
  if m.get('price_tier')!='keskin' or not m.get('betting_ok'): continue
  if (m.get('ref_age_hours') or 9)>3: continue
  if m.get('consensus_gap') and m['consensus_gap']>0.05: continue
  f=m.get('fair_1x2')
  for s in m['selections']:
    o=s.get('odds')
    if s['market'] not in CORE or not o or o<1.20: continue
    if (str(m['code']),s['name']) in dropped: continue
    fp=s['fair_prob']
    if s['market']=='Çifte Şans' and f:
      fp={'1-X':f[0]+f[1],'1-2':f[0]+f[2],'X-2':f[1]+f[2]}.get(s['selection'],None) or fp
    elif not s.get('direct'): continue
    p=calibrated_probability(fp,True,cal); ev=p*o-1
    hard=is_hard_market(s['name'],o)
    if hard and ev<leg_min_ev(s['name'],hard): continue
    if ev>=0.20 or p>=0.97: continue
    opts.setdefault(m['code'],[]).append(dict(code=m['code'],ko=m['kickoff'],lg=m['league'],match=f"{m['home']} - {m['away']}",market=s['market'],sel=s['selection'],name=s['name'],odds=o,p=round(p,4),fair=round(1/p,3),ev=round(ev,4),mbs=s.get('mbs'),ref=m['reference'],ref_utc=m.get('ref_fetched_utc')))
# keep top 4 options per match by EV
for k in opts: opts[k]=sorted(opts[k],key=lambda c:-c['ev'])[:4]
STEP=0.002; T=math.log(7.0); CAP=math.ceil(T/STEP)
# dp[k][bin]=(score,legs)  score=sum log p ; bin=floor(sum log odds/STEP) capped
dp=[dict() for _ in range(8)]; dp[0][(0,1)]=(0.0,())
for code,ol in opts.items():
  for kk in range(6,-1,-1):
    for (b,mb),(sc,legs) in list(dp[kk].items()):
      for c in ol:
        nb=min(CAP,b+int(math.log(c['odds'])/STEP+1e-9)); ns=sc+math.log(c['p']); key=(nb,max(mb,c['mbs'] or 1))
        cur=dp[kk+1].get(key)
        if cur is None or ns>cur[0]: dp[kk+1][key]=(ns,legs+(c,))
res={}
for kk in range(1,7):
  bestc=None
  for (b,mb),(sc,legs) in dp[kk].items():
    O=math.prod(c['odds'] for c in legs)
    if b*STEP<T-1e-9 or O<7.0 or max(c['mbs'] or 1 for c in legs)>kk: continue
    if bestc is None or sc>bestc[0]: bestc=(sc,legs)
  if bestc:
    legs=list(bestc[1]); O=math.prod(c['odds'] for c in legs); P=math.exp(bestc[0])
    res[kk]=dict(n=kk,P=round(P,4),odds=round(O,2),payout=round(50*O,2),ev=round(P*O-1,4),legs=legs)
    print(f"n={kk} P={P:.4f} O={O:.2f} EV={P*O-1:+.3f}")
    for c in legs: print('   ',c['code'],c['ko'][11:],c['match'],'|',c['market'],':',c['sel'],c['odds'],c['p'],c['fair'],c['ev'],'mbs',c['mbs'],c['ref'][:12])
allc=sorted([c for v in opts.values() for c in v],key=lambda c:-c['ev'])
json.dump(dict(generated_at=d.get('generated_at'),by_n=res,top_pool=allc[:40]),open(__import__('os').environ.get('K7_OUT','/tmp/kupon7_out.json'),'w'),ensure_ascii=False,indent=1)

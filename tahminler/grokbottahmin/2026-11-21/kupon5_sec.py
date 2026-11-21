import json,sys,math,datetime as dt,itertools
sys.path.insert(0,'src'); sys.path.insert(0,'scripts')
from quantfoot.evaluation.auto_learn import calibrated_probability, load_live_calibration
from nesine_kupon import is_hard_market
from quantfoot.markets.families import leg_min_ev, bet_family
cal=load_live_calibration() or {}
D='tahminler/grokbottahmin/2026-11-21/'
src=sys.argv[1] if len(sys.argv)>1 else D+'nesine_global.json'
d=json.load(open(src))
dt_=json.load(open(D+'derin_tahminler.json'))
dropped={(str(r['code']),x.get('name') or x.get('label')) for r in dt_ for x in (r.get('dropped') or [])}
CUT=dt.datetime.fromisoformat('2026-11-21T15:45:00+03:00')
END=dt.datetime.fromisoformat('2026-11-22T04:00:00+03:00')
USED={3319709,3359425,3318200,3314542,3313958,3313206,3319368,3314007,3314236,3313105,3318757,3313080,3313626,3389665,3312729}
cands=[]
for m in d['matches']:
  k=dt.datetime.fromisoformat(m['kickoff_iso'])
  if k<CUT or k>END or m['code'] in USED: continue
  if m.get('price_tier')!='keskin' or not m.get('betting_ok'): continue
  if (m.get('ref_age_hours') or 9)>3: continue
  if m.get('consensus_gap') and m['consensus_gap']>0.05: continue
  for s in m['selections']:
    o=s.get('odds')
    if not s.get('direct') or not o or o<1.20 or o>4.0: continue
    if (str(m['code']),s['name']) in dropped: continue
    p=calibrated_probability(s['fair_prob'],True,cal); ev=p*o-1
    hard=is_hard_market(s['name'],o); fl=leg_min_ev(s['name'],hard)
    if hard and ev<fl: continue
    if ev>=0.25: continue  # suspicious mismatch
    cands.append(dict(code=m['code'],ko=m['kickoff'],lg=m['league'],match=f"{m['home']} - {m['away']}",market=s['market'],sel=s['selection'],name=s['name'],odds=o,p=round(p,4),fair=round(1/p,3),ev=round(ev,4),ref=m['reference'],age=m['ref_age_hours'],fam=bet_family(s['name'])))
# per match keep top 3 by EV
by={}
for c in cands: by.setdefault(c['code'],[]).append(c)
pool=[]
for k,v in by.items(): pool+=sorted(v,key=lambda c:-c['ev'])[:3]
pool=sorted(pool,key=lambda c:-c['ev'])[:45]
print('pool',len(pool),'from',len(cands))
best=[]
TARGET=20.0
def search(start,legs,lo,lp,codes):
  if lo>=math.log(TARGET):
    best.append((lp,list(legs))); return
  if len(legs)==6: return
  for i in range(start,len(pool)):
    c=pool[i]
    if c['code'] in codes: continue
    legs.append(c); codes.add(c['code'])
    search(i+1,legs,lo+math.log(c['odds']),lp+math.log(c['p']),codes)
    legs.pop(); codes.discard(c['code'])
search(0,[],0,0,set())
best.sort(key=lambda x:-x[0])
out=[]
for lp,legs in best[:8]:
  O=math.prod(c['odds'] for c in legs); P=math.exp(lp)
  out.append(dict(P=round(P,4),odds=round(O,2),payout=round(50*O,2),ev=round(P*O-1,4),legs=legs))
  print(f"P={P:.4f} O={O:.2f} EV={P*O-1:+.3f} n={len(legs)}")
  for c in legs: print('   ',c['code'],c['ko'],c['match'],'|',c['market'],':',c['sel'],c['odds'],c['p'],c['fair'],c['ev'],c['ref'])
json.dump(dict(src=src,generated_at=d.get('generated_at'),pool=pool,top=out),open('/tmp/kupon5_out.json','w'),ensure_ascii=False,indent=1)

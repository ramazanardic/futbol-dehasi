import json,sys,datetime as dt
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
dropped_lbl={(str(r['code']),x.get('label')) for r in dt_ for x in (r.get('dropped') or [])}
CUT=dt.datetime.fromisoformat('2026-11-21T15:30:00+03:00')
EXCL={3389665,3312729}  # kaynak çelişkisi / türetilmiş
best={}
for m in d['matches']:
  if dt.datetime.fromisoformat(m['kickoff_iso'])<CUT or m['code'] in EXCL: continue
  if m.get('price_tier')!='keskin' or not m.get('betting_ok'): continue
  if (m.get('ref_age_hours') or 9)>3: continue
  if m.get('consensus_gap') and m['consensus_gap']>0.05: continue
  for s in m['selections']:
    if not s.get('direct') or not s.get('odds') or s['odds']<float(sys.argv[2] if len(sys.argv)>2 else 1.40) or s['odds']>float(sys.argv[3] if len(sys.argv)>3 else 2.40): continue
    if (str(m['code']),s['name']) in dropped or (str(m['code']),f"{s['market']}: {s['selection']}") in dropped_lbl: continue
    p=calibrated_probability(s['fair_prob'],True,cal); ev=p*s['odds']-1
    hard=is_hard_market(s['name'],s['odds']); fl=leg_min_ev(s['name'],hard)
    if hard and ev<fl: continue
    if ev>=0.25: continue
    r=dict(code=m['code'],ko=m['kickoff'][11:],lg=m['league'],match=f"{m['home']} - {m['away']}",sel=s['name'],market=s['market'],odds=s['odds'],p=round(p,4),fair=round(1/p,3),ev=round(ev,4),ref=m['reference'],age=m['ref_age_hours'],fam=bet_family(s['name']))
    if m['code'] not in best or ev>best[m['code']]['ev']: best[m['code']]=r
L=sorted(best.values(),key=lambda r:-r['ev'])
json.dump(L,open(D+'kupon5000_havuz.json','w'),ensure_ascii=False,indent=1)
print(len(L))
for r in L[:40]: print(r['ev'],r['ko'],r['code'],r['match'],r['sel'],r['odds'],r['fair'],r['ref'],r['lg'])

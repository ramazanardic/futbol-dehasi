import json,sys,math,datetime as dt,itertools
from pathlib import Path
sys.path.insert(0,'src'); sys.path.insert(0,'scripts')
from quantfoot.evaluation.auto_learn import calibrated_probability, load_live_calibration
from quantfoot.data import fotmob as fmb
from quantfoot.data.match_dossier import CachedHttp
cal=load_live_calibration() or {}
D='tahminler/grokbottahmin/2026-11-21/'
ng=json.load(open(D+'nesine_global.json'))
NOW=dt.datetime.now(dt.timezone(dt.timedelta(hours=3)))+dt.timedelta(minutes=10)
END=dt.datetime.fromisoformat('2026-11-22T06:00:00+03:00')
USED={3319709:'K1',3359425:'K1-4',3318200:'K1-4',3314007:'K1-4',3314236:'K3',3313105:'K1-4',3318757:'K1-4',3313080:'K1-4',3313626:'K1-4',
 3314542:'K2',3313958:'K2',3313206:'K2',3319368:'K2/K6',3313940:'K5',3313644:'K5',3313868:'K5',3312554:'K6',3314647:'K6',
 3313572:'K7b',3312753:'K7b',3318505:'K7b',3313774:'K7b',3314607:'K7b'}
CORE={'Maç Sonucu','Çifte Şans','1,5 Gol Alt/Üst','2,5 Gol Alt/Üst','3,5 Gol Alt/Üst','Karşılıklı Gol','1. Yarı Sonucu'}
def cp(p): return calibrated_probability(p,True,cal)
matches=[]; cands=[]
for m in ng['matches']:
  k=dt.datetime.fromisoformat(m['kickoff_iso'])
  if k<NOW or k>END: continue
  sharp = m.get('price_tier')=='keskin' and m.get('betting_ok') and (m.get('ref_age_hours') or 9)<=3 and not (m.get('consensus_gap') and m['consensus_gap']>0.05)
  sel={}
  f=m.get('fair_1x2')
  for s in (m.get('selections') or []):
    if s['market'] not in CORE or not s.get('odds'): continue
    fp=s['fair_prob']
    if s['market']=='Çifte Şans' and f: fp={'1-X':f[0]+f[1],'1-2':f[0]+f[2],'X-2':f[1]+f[2]}.get(s['selection'],fp)
    elif not s.get('direct'): continue
    p=cp(fp); sel[s['name']]=dict(market=s['market'],sel=s['selection'],odds=s['odds'],p=round(p,4),fair=round(1/p,3),ev=round(p*s['odds']-1,4),mbs=s.get('mbs'))
  st=m.get('steam_1x2') or [0,0,0]
  rec=dict(code=m['code'],ko=m['kickoff'],league=m.get('league'),home=m['home'],away=m['away'],sharp=bool(sharp),ref=m.get('reference'),mu=[m.get('mu_home'),m.get('mu_away')],
           fair_1x2=f,steam=st,research=m.get('research'),used=USED.get(m['code']),selections=sel)
  matches.append(rec)
  if not sharp: continue
  for name,s in sel.items():
    red=[]
    # steam against selection side
    if s['market']=='Maç Sonucu':
      i={'1':0,'X':1,'2':2}.get(s['sel']); 
      if i is not None and st[i]<=-0.05: red.append(f'sharp steam aleyhte {st[i]*100:+.1f}p')
    if s['market']=='Çifte Şans':
      idx={'1-X':(0,1),'1-2':(0,2),'X-2':(1,2)}.get(s['sel'],())
      if idx and sum(st[j] for j in idx)<=-0.05: red.append('sharp steam aleyhte')
    cands.append(dict(code=m['code'],ko=m['kickoff'],league=m.get('league'),match=f"{m['home']} - {m['away']}",home=m['home'],away=m['away'],name=name,ref=m.get('reference'),used=USED.get(m['code']),red=red,**s))
json.dump(dict(generated_at=ng['generated_at'],matches=matches,cands=cands),open('/tmp/ba_stage1.json','w'),ensure_ascii=False,default=str)
print(ng['generated_at'],'matches',len(matches),'sharp',sum(r['sharp'] for r in matches),'cands',len(cands))
# --- both-halves BTTS (1. Yarı / 2. Yarı Karşılıklı Gol -> Evet/Evet)
ex=math.exp
bh=[]
for m in ng['matches']:
  k=dt.datetime.fromisoformat(m['kickoff_iso'])
  if k<NOW or k>END or not m.get('mu_home') or not m.get('mu_away'): continue
  mh,ma=m['mu_home'],m['mu_away']
  p1=(1-ex(-0.45*mh))*(1-ex(-0.45*ma)); p2=(1-ex(-0.55*mh))*(1-ex(-0.55*ma)); pb=p1*p2
  ns={s['selection']:s for s in (m.get('selections') or []) if s['market']=='1. Yarı / 2. Yarı Karşılıklı Gol'}
  iy={s['selection']:s for s in (m.get('selections') or []) if s['market']=='1. Yarı Karşılıklı Gol'}
  y2={s['selection']:s for s in (m.get('selections') or []) if s['market']=='2. Yarı Karşılıklı Gol'}
  ee=ns.get('Evet/Evet')
  r=dict(code=m['code'],ko=m['kickoff'],league=m.get('league'),match=f"{m['home']} - {m['away']}",mu=[mh,ma],sharp=m.get('price_tier')=='keskin',ref=m.get('reference'),
         p_iy_kg=round(p1,4),p_2y_kg=round(p2,4),p_both=round(pb,4),fair_both=round(1/pb,2),
         engine_p_both=ee and ee['fair_prob'], nesine_market='1. Yarı / 2. Yarı Karşılıklı Gol → Evet/Evet' if ee else 'Nesine bülteninde yok',
         nesine_odds=ee and ee['odds'], ev=ee and round(pb*ee['odds']-1,4), mbs=ee and ee['mbs'],
         nesine_iy_kg_var=(iy.get('Var') or {}).get('odds'), nesine_2y_kg_var=(y2.get('Var') or {}).get('odds'),used=USED.get(m['code']))
  bh.append(r)
bh.sort(key=lambda r:-r['p_both'])
json.dump(bh,open('/tmp/ba_bothhalves.json','w'),ensure_ascii=False)
for r in bh[:12]: print(r['code'],r['ko'][11:],r['match'],r['mu'],r['p_iy_kg'],r['p_2y_kg'],r['p_both'],r['engine_p_both'],r['nesine_odds'],r['ev'],r['sharp'])

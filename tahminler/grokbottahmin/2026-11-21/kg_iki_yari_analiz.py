"""KG iki yarı (Evet/Evet) – yarı bazlı model + piyasa harmanı + rapor."""
import json,math,datetime as dt,statistics as st
D='tahminler/grokbottahmin/2026-11-21/'
res=json.load(open('tahminler/grokbottahmin/2026-11-21/veri/kg2/collected.json'))
ng=json.load(open(D+'nesine_global.json'))
NGM={m['code']:m for m in ng['matches']}
EX=math.exp
PRIOR_S1=0.445   # tarihsel ilk yarı gol payı
EURO=('Champions','Europa','Conference','Cup','Pokal','Coupe','Copa','Coppa','Beker','Trophy','Libertadores','Sudamericana','Concacaf','Leagues Cup','Playoff')
EARLIER={3313844:'Frankfurt–Hoffenheim',3313406:'NEC–PSV',3312633:'Young Boys–Thun',3313751:'Liefering–Wacker',3314656:'Groningen–Heerenveen',3389687:'Inter Miami–Columbus'}
def agg(L):
  n=len(L)
  if not n: return None
  g=lambda k: sum(x[k] for x in L)/n
  xs=[x for x in L if x.get('xgf') is not None]
  return dict(n=n,gf1=g('gf1'),ga1=g('ga1'),gf2=g('gf2'),ga2=g('ga2'),
    btts1=sum(1 for x in L if x['gf1']>0 and x['ga1']>0)/n, btts2=sum(1 for x in L if x['gf2']>0 and x['ga2']>0)/n,
    both=sum(1 for x in L if x['gf1']>0 and x['ga1']>0 and x['gf2']>0 and x['ga2']>0)/n,
    scored1=sum(1 for x in L if x['gf1']>0)/n, conc1=sum(1 for x in L if x['ga1']>0)/n,
    scored2=sum(1 for x in L if x['gf2']>0)/n, conc2=sum(1 for x in L if x['ga2']>0)/n,
    xgf=(sum(x['xgf'] for x in xs)/len(xs) if xs else None), xga=(sum(x['xga'] for x in xs)/len(xs) if xs else None), nxg=len(xs),
    seq=' '.join(f"{x['venue']}:{x['gf1']}-{x['ga1']}|{x['gf2']}-{x['ga2']}" for x in L[-10:]))
def pk(l1,l2): return (1-EX(-l1))*(1-EX(-l2))
out=[]
for r in res:
  m=NGM.get(r['code']) or {}
  sel={(s['market'],s['selection']):s for s in (m.get('selections') or [])}
  ee=sel.get(('1. Yarı / 2. Yarı Karşılıklı Gol','Evet/Evet')) or {}
  four=[sel.get(('1. Yarı / 2. Yarı Karşılıklı Gol',k)) for k in ('Evet/Evet','Evet/Hayır','Hayır/Evet','Hayır/Hayır')]
  over=sum(1/s['odds'] for s in four if s) if all(four) else None
  odds=ee.get('odds') or r['nesine']['1. Yarı / 2. Yarı Karşılıklı Gol|Evet/Evet']['odds']
  eng=ee.get('fair_prob') or r['nesine']['1. Yarı / 2. Yarı Karşılıklı Gol|Evet/Evet']['fair']
  muh,mua=m.get('mu_home') or r['mu'][0],m.get('mu_away') or r['mu'][1]
  H=agg((r.get('home_form') or {}).get('last') or []); A=agg((r.get('away_form') or {}).get('last') or [])
  rec=dict(code=r['code'],ko=r['ko'],league=r['league'],match=f"{r['home']} - {r['away']}",tier=r['tier'],ref=r.get('ref'),mu=[muh,mua],
     nesine_odds=odds,nesine_odds_1627=r['nesine']['1. Yarı / 2. Yarı Karşılıklı Gol|Evet/Evet']['odds'],market_overround=over and round(over,3),
     nesine_implied_nomargin=(over and round((1/odds)/over,4)),engine_p=eng,
     nesine_iy_kg_var=(sel.get(('1. Yarı Karşılıklı Gol','Var')) or {}).get('odds'),nesine_2y_kg_var=(sel.get(('2. Yarı Karşılıklı Gol','Var')) or {}).get('odds'),
     nesine_kg_var=(sel.get(('Karşılıklı Gol','Var')) or {}).get('odds'),fotmob_id=(r.get('fotmob') or {}).get('id'),
     home_stats=H,away_stats=A,flags=[],notes=[])
  # per-half model
  p_model=None
  if H and A and muh and mua:
    dh1=(H['gf1']+A['ga1'])/2; da1=(A['gf1']+H['ga1'])/2; dh2=(H['gf2']+A['ga2'])/2; da2=(A['gf2']+H['ga2'])/2
    n=min(H['n'],A['n'])
    wtot=0.30*n/10   # veri ağırlığı toplam golde (piyasa keskin -> %70+)
    th=(1-wtot)*muh+wtot*(dh1+dh2); ta=(1-wtot)*mua+wtot*(da1+da2)
    def share(a,b,ng):
      s=a/(a+b) if a+b>0 else PRIOR_S1
      w=ng/(ng+15.0)
      return (1-w)*PRIOR_S1+w*s
    sh=share(dh1,dh2,(dh1+dh2)*n*2); sa=share(da1,da2,(da1+da2)*n*2)
    lh1,lh2,la1,la2=th*sh,th*(1-sh),ta*sa,ta*(1-sa)
    p1=pk(lh1,la1); p2=pk(lh2,la2); p_model=p1*p2
    rec.update(lambdas=dict(h1=round(lh1,3),a1=round(la1,3),h2=round(lh2,3),a2=round(la2,3)),data_lambdas=dict(h1=round(dh1,2),a1=round(da1,2),h2=round(dh2,2),a2=round(da2,2)),
               p_iy_kg=round(p1,4),p_2y_kg=round(p2,4),p_halfmodel=round(p_model,4))
    emp=(H['both']*H['n']+A['both']*A['n']+0.12*6)/(H['n']+A['n']+6)  # 6 sanal maçla %12 önseline büzülmüş
    rec['emp_both_rate_shrunk']=round(emp,4)
    p=0.45*p_model+0.40*(eng or p_model)+0.15*emp
  else:
    p=eng; rec['notes'].append('FotMob yarı verisi yok -> yalnız motor (piyasa) olasılığı')
  rec['p_final']=round(p,4) if p else None
  rec['fair_odds']=p and round(1/p,2)
  rec['ev']=p and odds and round(p*odds-1,4)
  # flags
  for side,key in (('home','home_form'),('away','away_form')):
    F=r.get(key) or {}
    tm=r['home'] if side=='home' else r['away']
    for nx in (F.get('next') or [])[:1]:
      try:
        gap=(dt.datetime.fromisoformat(nx['date']+':00+00:00')-dt.datetime.fromisoformat(r['ko_iso'])).total_seconds()/86400
      except Exception: gap=None
      rec['notes'].append(f"{tm} sonraki maç: {nx['date'][:10]} {nx['comp']} vs {nx['opp']}" + (f" ({gap:.1f} gün sonra)" if gap is not None else ''))
      if gap is not None and gap<=4.5 and any(k in (nx['comp'] or '') for k in EURO): rec['flags'].append(f"rotasyon riski: {tm} {gap:.1f} gün sonra {nx['comp']}")
    lu=((r.get('today') or {}).get(f'{side}_lineup')) or {}
    un=lu.get('unavailable') or []
    tops={(p[0] or '') for p in (F.get('top_players') or [])}
    if un:
      keyout=[u['name'] for u in un if u['name'] in tops]
      rec['notes'].append(f"{tm} eksikler ({len(un)}): "+', '.join(f"{u['name']} ({u['reason']})" for u in un[:8]))
      if keyout: rec['flags'].append(f"{tm} kilit oyuncu eksik: {', '.join(keyout)}")
    else: rec['notes'].append(f"{tm}: FotMob eksik listesi boş/yok")
    if F.get('top_players'): rec[f'{side}_top_players']=F['top_players'][:6]
  w=(r.get('today') or {}).get('weather')
  if w: rec['weather']=w
  if (r.get('today') or {}).get('lineup_type'): rec['lineup_type']=r['today']['lineup_type']
  rec['h2h']=r.get('h2h')
  if H and A:
    if min(H['btts1'],A['btts1'])<0.15: rec['flags'].append('takımlardan biri son maçlarında ilk yarıda nadiren KG (<%15)')
    if (H['xgf'] or 9)<1.0 and (A['xgf'] or 9)<1.0: rec['flags'].append('iki takımın da xG üretimi düşük (<1.0)')
  rec['earlier']=EARLIER.get(r['code'])
  out.append(rec)
out.sort(key=lambda x:-(x['p_final'] or 0))
json.dump(out,open('tahminler/grokbottahmin/2026-11-21/veri/kg2/analysed.json','w'),ensure_ascii=False,indent=1,default=str)
for x in out:
  H,A=x['home_stats'],x['away_stats']
  print(x['code'],x['ko'][11:],x['match'][:34].ljust(34),'P',x['p_final'],'hm',x.get('p_halfmodel'),'eng',x['engine_p'],'emp',x.get('emp_both_rate_shrunk'),'odds',x['nesine_odds'],'EV',x['ev'],'|',
        H and f"H b1{H['btts1']:.1f} b2{H['btts2']:.1f} both{H['both']:.1f} xg{H['xgf']}/{H['xga']}", A and f"A b1{A['btts1']:.1f} b2{A['btts2']:.1f} both{A['both']:.1f} xg{A['xgf']}/{A['xga']}",x['flags'])

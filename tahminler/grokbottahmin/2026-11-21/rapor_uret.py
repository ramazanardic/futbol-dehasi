import json,sys,datetime as dt
sys.path.insert(0,'src'); sys.path.insert(0,'scripts')
from quantfoot.evaluation.auto_learn import calibrated_probability, load_live_calibration
from nesine_kupon import is_hard_market
from quantfoot.markets.families import leg_min_ev
cal=load_live_calibration() or {}
D='tahminler/grokbottahmin/2026-11-21/'
d=json.load(open(D+'nesine_global.json'))
CUT=dt.datetime.fromisoformat('2026-11-21T14:20:00+03:00')
rem=[m for m in d['matches'] if dt.datetime.fromisoformat(m['kickoff_iso'])>CUT and m.get('price_tier')!='ozel_bahis']
rem.sort(key=lambda m:(m['kickoff'],m['league']))
TIER={'keskin':'keskin','global_buro':'global büro','dusuk_guven':'düşük güven','fiyatsiz':'fiyatsız'}
PLAY={(3319709,'MS 1'),(3314542,'Dep 0.5 Alt')}
def f(x): return f"{x:.2f}" if x else "-"
def brief(m):
  r=m.get('research') or {}; out=[]
  mo=r.get('motivation') or {}
  if mo: out.append(f"sıra: {mo.get('home','?')} / {mo.get('away','?')}")
  ab=r.get('absences') or {}
  for s in ('home','away'):
    pl=[p['name'] for p in (ab.get(s) or {}).get('players',[]) if p.get('status')=='sakat' or (p.get('chance') or 100)<=50]
    if pl: out.append(f"{'ev' if s=='home' else 'dep'} eksik: {', '.join(pl[:4])}")
  t=r.get('teams') or {}
  fm=[(t.get(s) or {}).get('form') for s in ('home','away')]
  if any(fm): out.append(f"form {fm[0] or '?'}/{fm[1] or '?'}")
  w=r.get('weather') or {}
  if w: out.append(f"hava {w.get('temp_c')}°C, yağış {w.get('rain_mm')} mm, rüzgâr {w.get('wind_kmh')} km/s"+(" ⚠" if w.get('severe') else ""))
  for fl in r.get('flags') or []: out.append(fl)
  return "; ".join(out) or "-"
rows=[]; ev_list=[]
for m in rem:
  best=None
  for s in m.get('selections') or []:
    if not s.get('odds') or s['odds']<1.2 or s.get('fair_prob') is None: continue
    p=calibrated_probability(s['fair_prob'],bool(s['direct']),cal); ev=p*s['odds']-1
    fl=max(0.02,leg_min_ev(s['name'],is_hard_market(s['name'],s['odds'])))
    if s['direct'] and (best is None or ev>best[0]): best=(ev,s,p)
    if ev>=fl and ev<0.25 and m['price_tier'] in ('keskin','global_buro'):
      ev_list.append((ev,m,s,p,fl))
  nm=m.get('nesine_ms') or [None]*3; fr=m.get('fair_1x2')
  fair=" / ".join(f"{1/x:.2f}" for x in fr) if fr else "-"
  nes=" / ".join(f(x) for x in nm)
  bs=f"{best[1]['name']} {best[1]['odds']:.2f} (adil {1/best[2]:.2f}, EV {best[0]*100:+.1f}%)" if best else "-"
  verdict='**OYNA**' if any((m['code'],sel)in PLAY for sel in ('MS 1','Dep 0.5 Alt')) else 'oynama'
  ref=f"{m.get('reference') or '-'} ({TIER.get(m.get('price_tier'),m.get('price_tier'))})"
  rows.append(f"| {m['kickoff'][11:]} | {m['code']} | {m['league']} | {m['home']} - {m['away']} | {ref} | {fair} | {nes} | {bs} | {brief(m)} | {verdict} |")
ev_list.sort(key=lambda x:-x[0])
json.dump({'n_rem':len(rem),'sharp':sum(m['price_tier']=='keskin' for m in rem),'buro':sum(m['price_tier']=='global_buro' for m in rem),
 'low':sum(m['price_tier']=='dusuk_guven' for m in rem),'none':sum(m['price_tier']=='fiyatsiz' for m in rem),
 'ev':[(round(e,4),m['kickoff'][11:],m['code'],m['home'],m['away'],s['name'],s['odds'],round(1/p,3),s['direct'],m['reference'],round(fl,3)) for e,m,s,p,fl in ev_list]},open(D+'rapor_ozet.json','w'),ensure_ascii=False,indent=1)
open(D+'tablo.md','w').write("| Saat | Kod | Lig | Maç | Referans | Adil 1X2 | Nesine MS | En iyi doğrudan seçim | Dosya özeti | Karar |\n|---|---|---|---|---|---|---|---|---|---|\n"+"\n".join(rows)+"\n")
print(open(D+'rapor_ozet.json').read())

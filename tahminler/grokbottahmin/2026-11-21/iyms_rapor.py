"""İY/MS rapor: sonuç başına ilk 3 (P ve EV), banko İY/MS kuponu, değer tekleri."""
import json,math,datetime as dt
D='tahminler/grokbottahmin/2026-11-21/'
R=[r for r in json.load(open('tahminler/grokbottahmin/2026-11-21/veri/iyms/analysed.json')) if not r['started']]
ng=json.load(open('tahminler/grokbottahmin/2026-11-21/veri/iyms/ng_fresh.json'))
OUT=['1/2','1/1','1/X','X/1','X/X','2/1','2/X','2/2']
NOT={'1/X':'1/0','X/1':'0/1','X/X':'0/0','2/X':'2/0'}
nm=lambda o:NOT.get(o,o)
def item(r,o): return dict(code=r['code'],ko=r['ko'],match=r['match'],league=r['league'],out=nm(o),odds=r['nesine'].get(o),P=r['P'].get(o),EV=r['EV'].get(o),
  model=(r.get('model') or {}).get(o),engine=r['engine'].get(o),emp=r['empirical'].get(o),flags=r['flags'],mbs=r['mbs'])
tops={}
for o in OUT:
  c=[item(r,o) for r in R if r['P'].get(o) and r['nesine'].get(o)]
  tops[nm(o)]=dict(by_P=sorted(c,key=lambda x:-x['P'])[:3],by_EV=sorted(c,key=lambda x:-x['EV'])[:3])
json.dump(tops,open('tahminler/grokbottahmin/2026-11-21/veri/iyms/tops.json','w'),ensure_ascii=False,default=str)
L=[]
L.append(f"# İY/MS derin analiz – 21.11.2026\n\nNesine fiyatları: {ng['generated_at']} · analiz edilen başlamamış maç: {len(R)} (İY/MS açık, keskin referanslı, bugünkü kuponlardaki maçlar hariç)\n")
L.append("Yöntem: P = 0,45×motor (Smarkets/Pinnacle marjsız 1X2+Alt/Üst'ten türetilmiş İY/MS) + 0,40×yarı bazlı Dixon-Coles (takımların son 10 maçındaki 1./2. yarı gol payları; ρ1=−0,10, ρ2=−0,06) + 0,15×takımların gerçek son-10 İY/MS deseni (küçülterek). EV = P×Nesine oranı − 1.\n")
for o in OUT:
  t=tops[nm(o)]
  L.append(f"\n## İY/MS {nm(o)}\n\n| Sıra | Maç | Saat | Oran | P | EV |\n|---|---|---|---|---|---|")
  for i,x in enumerate(t['by_P'],1): L.append(f"| P{i} | {x['match']} | {x['ko'][11:]} | {x['odds']} | {x['P']*100:.1f}% | {x['EV']*100:+.1f}% |")
  for i,x in enumerate(t['by_EV'],1): L.append(f"| EV{i} | {x['match']} | {x['ko'][11:]} | {x['odds']} | {x['P']*100:.1f}% | {x['EV']*100:+.1f}% |")
L.append("\n## Maç ayrıntıları (1/1 veya 2/2 P ≥ %40)\n")
for r in sorted(R,key=lambda r:-max(r['P'].get('1/1',0),r['P'].get('2/2',0))):
  if max(r['P'].get('1/1',0),r['P'].get('2/2',0))<0.40: continue
  H,A=r['home_stats'],r['away_stats']
  L.append(f"### {r['match']} ({r['ko'][11:]}, {r['league']})\n")
  L.append(f"- Nesine İY/MS: "+', '.join(f"{nm(o)} {r['nesine'].get(o)} (P {r['P'].get(o,0)*100:.1f}%, EV {r['EV'].get(o,0)*100:+.0f}%)" for o in ('1/1','X/1','X/X','2/2','X/2') if r['nesine'].get(o)))
  L.append(f"- Keskin marjsız 1X2: {[round(x,3) for x in (r['fair_1x2'] or [])]} · μ {r['mu']} · ref {r['ref']} · yarı λ {r.get('lambdas')}")
  for side,S in (('Ev',H),('Dep',A)):
    if S:
      pc=lambda v,n: 'veri yok' if v is None else f"%{v*100:.0f} ({n} maç)"
      L.append(f"- {side} son {S['n']}: form {S['form']}, İY önde %{S['ht_lead']*100:.0f}, İY berabere %{S['ht_draw']*100:.0f}, İY önde→kazandı {pc(S['lead_conv'],S['n_lead'])}, İY geride→kazandı {pc(S['comeback'],S['n_trail'])} · İY-MS (takım bakışı): {S['seq']}")
    else: L.append(f"- {side}: FotMob verisi yok")
  for side in ('home','away'):
    if r.get(f'{side}_unavailable'): L.append(f"- {'Ev' if side=='home' else 'Dep'} eksik: {', '.join(r[side+'_unavailable'][:8])}")
  if r['flags']: L.append(f"- Bayrak: {'; '.join(r['flags'])}")
  if r['notes']: L.append(f"- Not: {'; '.join(r['notes'])}")
  L.append("")
open('tahminler/grokbottahmin/2026-11-21/veri/iyms/rapor_body.md','w').write('\n'.join(L))
print('\n'.join(L[:200]))

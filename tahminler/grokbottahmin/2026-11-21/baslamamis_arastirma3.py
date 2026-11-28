import json,sys,math,itertools
sys.path.insert(0,'src')
from quantfoot.data.match_dossier import team_match_score
D='tahminler/grokbottahmin/2026-11-21/'
S1=json.load(open('/tmp/ba_stage1.json')); S2=json.load(open('/tmp/ba_stage2.json')); BH=json.load(open('/tmp/ba_bothhalves.json'))
M={m['code']:m for m in S1['matches']}
euro=S2['euro_teams']
def rot(team):
  for t,v in euro.items():
    if any(x in v for x in ('AFC','CAF','CONCACAF','Women','U19','U21')): continue
    if t and team_match_score(team,t)>=0.95: return v
  return None
def reason(c):
  m=M[c['code']]; r=m.get('research') or {}; t=r.get('teams') or {}
  bits=[f"xG-mu {m['mu'][0]}-{m['mu'][1]}" if m['mu'][0] else '']
  for side,i in (('home',0),('away',1)):
    x=t.get(side) or {}; tb=x.get('table') or {}
    if tb.get('rank'): bits.append(f"{x.get('name')} {int(tb['rank'])}./{tb.get('size')}")
  if c.get('form'): bits.append(f"form {c['form'][0]} / {c['form'][1]}")
  st=m['steam']; 
  if st and max(abs(v) for v in st)>=0.02: bits.append(f"steam 1/X/2 {st[0]*100:+.1f}/{st[1]*100:+.1f}/{st[2]*100:+.1f}p")
  hu,au=c.get('home_unavailable') or [],c.get('away_unavailable') or []
  if hu or au: bits.append(f"eksik ev {len(hu)} ({', '.join(hu[:2])}) / dep {len(au)} ({', '.join(au[:2])})")
  return '; '.join(b for b in bits if b)
top=[]
for c in S2['ranked']:
  c['rotation']=[f"{tm}: {v}" for tm in (c['home'],c['away']) for v in [rot(tm)] if v]
  soft=[]
  if c['rotation']: soft.append('rotasyon riski: '+', '.join(c['rotation']))
  if len(c.get('home_unavailable') or [])+len(c.get('away_unavailable') or [])>=10: soft.append('çok eksik oyuncu')
  if c.get('fotmob_id') is None: soft.append('FotMob eşleşmedi (kadro/eksik bilgisi yok)')
  c['soft_flags']=soft; c['reason']=reason(c)
  top.append(c)
clean=[c for c in top if not c['red']]
top20=clean[:20]
# coupon search over banko options (no red flags, not used today, KO not started)
redcodes={c['code'] for c in top if c['red']}
opts={}
for c in S2['banko_all']:
  if c['code'] in redcodes or c['used'] or c['red']: continue
  opts.setdefault(c['code'],[]).append(c)
for k in opts: opts[k]=sorted(opts[k],key=lambda c:-c['p'])[:3]
flat=sorted([c for v in opts.values() for c in v],key=lambda c:-c['p'])
def bestN(n,minO=1.0,excl=set(),pool=flat[:60]):
  best=None
  pool=[c for c in pool if c['code'] not in excl]
  for comb in itertools.combinations(pool,n):
    if len({c['code'] for c in comb})<n: continue
    if max(c['mbs'] or 1 for c in comb)>n: continue
    O=math.prod(c['odds'] for c in comb)
    if O<minO: continue
    P=math.prod(c['p'] for c in comb)
    if best is None or P>best[0]: best=(P,O,comb)
  return best
def fmt(b): return dict(total_odds=round(b[1],3),p_win=round(b[0],4),ev=round(b[0]*b[1]-1,4),legs=[{k:c.get(k) for k in ('code','ko','league','match','market','sel','odds','p','fair','ev','mbs','ref')} for c in b[2]])
coupons={n:fmt(bestN(n,pool=flat[:30])) for n in (2,3,4)}
# 5-leg >=5.00: DP-light: restrict pool to odds>=1.28 to make product reachable, plus combos
pool5=[c for c in flat if c['odds']>=1.25][:40]
c5=[];excl=set()
for i in range(3):
  b=bestN(5,5.0,excl,pool5)
  if not b: break
  c5.append(fmt(b)); excl|={c['code'] for c in b[2]}
pos=sorted([c for c in S1['cands'] if c['ev']>0 and c['odds']>=1.20],key=lambda c:-c['ev'])
bh=[r for r in BH if r['nesine_odds']][:10]; bh_all=BH[:10]
overlap=sorted({(c['code'],c['match'],c['used']) for c in S1['cands'] if c['used']})
out=dict(price_timestamp=S1['generated_at'],n_matches=len(S1['matches']),n_sharp=sum(m['sharp'] for m in S1['matches']),
 top20=top20,red_flagged=[c for c in top if c['red']],positive_ev=pos,coupons=coupons,coupons_5leg_min5=c5,both_halves_btts_in_bulletin=bh,both_halves_btts_all=bh_all,overlap_today=overlap,
 notes=['API-Football bu turda kullanılmadı (kota koruması); FotMob: maç detay (eksikler, form), 23-27 Kasım fikstürü (Avrupa/kupa rotasyonu).',
        'Her iki yarı KG Var: bağımsız yarı Poisson, gol payı %45/%55, takım bazlı yarı eğilim verisi yok -> yalnız mu (xG-mu) kullanıldı; motor (nesine_global) olasılığı karşılaştırma için verildi. BANKO DEĞİL (P %10-20).'])
json.dump(out,open(D+'baslamamis_arastirma.json','w'),ensure_ascii=False,indent=1,default=str)
# markdown
L=[f"# Başlamamış maçlar araştırması — 21.11.2026","",f"Nesine fiyatı: {S1['generated_at']} TSİ; {out['n_matches']} başlamamış maç, {out['n_sharp']} keskin referanslı.","",
"## 1) Banko ilk 20 (P ≥ ~%65, oran 1.20–1.80, sert kırmızı bayrak yok)","","| # | Kod | Saat | Lig | Maç | Pazar → Seçim | Oran | P | Adil | EV | MBS | Ref | Bugün | Gerekçe | Uyarı |","|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for i,c in enumerate(top20,1): L.append(f"| {i} | {c['code']} | {c['ko'][11:]} | {c['league']} | {c['match']} | {c['market']} → {c['sel']} | {c['odds']} | {c['p']:.1%} | {c['fair']} | {c['ev']:+.1%} | {c['mbs']} | {c['ref']} | {c['used'] or '-'} | {c['reason']} | {'; '.join(c['soft_flags']) or '-'} |")
L+=["","Elenen (sharp steam aleyhte): "+", ".join(f"{c['code']} {c['match']} {c['name']} ({'; '.join(c['red'])})" for c in out['red_flagged'])]
L+=["","## 2) Gerçek +EV seçimler (keskin ref, oran ≥1.20)"]+[f"- {c['code']} {c['ko'][11:]} {c['match']} — {c['market']} → {c['sel']} @ {c['odds']} (P {c['p']:.1%}, adil {c['fair']}, EV {c['ev']:+.1%}, MBS {c['mbs']}, {c['ref']}){' — bugün '+c['used'] if c['used'] else ''}" for c in pos]
L+=["","## 3) Banko kuponlar (bugün kullanılmamış maçlar, kırmızı bayraksız)"]
for n,v in coupons.items(): L.append(f"- **{n} maç**: oran {v['total_odds']:.2f}, P {v['p_win']:.1%}, EV {v['ev']:+.1%} — "+"; ".join(f"{l['code']} {l['ko'][11:]} {l['match']} {l['market']} → {l['sel']} @{l['odds']} (P {l['p']:.0%})" for l in v['legs']))
L+=["","### 5 maçlık, toplam ≥5.00 (birbirinden bağımsız maçlar)"]
for i,v in enumerate(c5,1): L.append(f"- **Kupon {chr(64+i)}**: oran {v['total_odds']:.2f}, P {v['p_win']:.1%}, EV {v['ev']:+.1%} — "+"; ".join(f"{l['code']} {l['ko'][11:]} {l['match']} {l['market']} → {l['sel']} @{l['odds']} (P {l['p']:.0%})" for l in v['legs']))
L+=["","## Her iki yarıda KG Var (1. Yarı / 2. Yarı Karşılıklı Gol → Evet/Evet) — BANKO DEĞİL, düşük olasılık","","| Kod | Saat | Maç | xG-mu | P İY KG | P 2Y KG | P her iki yarı | Adil | Motor P | Nesine | EV | İY KG Var oranı | 2Y KG Var oranı |","|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for r in bh: L.append(f"| {r['code']} | {r['ko'][11:]} | {r['match']} | {r['mu'][0]}-{r['mu'][1]} | {r['p_iy_kg']:.1%} | {r['p_2y_kg']:.1%} | {r['p_both']:.1%} | {r['fair_both']} | {(r['engine_p_both'] or 0):.1%} | {r['nesine_odds']} | {r['ev']:+.1%} | {r['nesine_iy_kg_var']} | {r['nesine_2y_kg_var']} |")
L+=["","Bültende bu pazar olmayan ama modelde daha yüksek çıkanlar: "+", ".join(f"{r['code']} {r['match']} P {r['p_both']:.1%}" for r in bh_all if not r['nesine_odds'])]
L+=["","## 4) Bugünkü kuponlarla örtüşen başlamamış maçlar"]+[f"- {c} {m} ({u})" for c,m,u in overlap]
L+=["","## Notlar"]+[f"- {n}" for n in out['notes']]
open(D+'baslamamis_arastirma.md','w').write("\n".join(L)+"\n")
for i,c in enumerate(top20,1): print(i,c['code'],c['ko'][11:],c['match'],c['market'],c['sel'],c['odds'],c['p'],c['fair'],c['ev'],c['mbs'],c['ref'][:9],c['used'],'|',c['reason'][:150],'|',c['soft_flags'])
print('POS',[(c['code'],c['match'],c['market'],c['sel'],c['odds'],c['p'],c['ev']) for c in pos])
for n,v in coupons.items(): print(n,v['total_odds'],v['p_win'],[(l['code'],l['match'],l['market'],l['sel'],l['odds'],l['p']) for l in v['legs']])
for v in c5: print('5L',v['total_odds'],v['p_win'],[(l['code'],l['ko'][11:],l['match'],l['market'],l['sel'],l['odds'],l['p']) for l in v['legs']])
for r in bh: print('BH',r['code'],r['ko'][11:],r['match'],r['p_iy_kg'],r['p_2y_kg'],r['p_both'],r['fair_both'],r['engine_p_both'],r['nesine_odds'],r['ev'],r['sharp'])
print('overlap',overlap)

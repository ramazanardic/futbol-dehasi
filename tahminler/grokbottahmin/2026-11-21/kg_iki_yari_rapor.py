import json,datetime as dt
D='tahminler/grokbottahmin/2026-11-21/'
x=json.load(open('tahminler/grokbottahmin/2026-11-21/veri/kg2/analysed.json'))
allm=json.load(open('tahminler/grokbottahmin/2026-11-21/veri/kg2/all_market.json'))
VERDICT={
3312633:('ONAYLANDI ve 1. sıraya çıktı','Thun son 10 maçının 5’inde iki yarıda da KG oldu (xGA 1.90); YB ilk yarılarda maç başı 1.8 gol atıyor, 1Y KG %60. YB’nin Avrupa maçı yok (sonraki maç 29.11 lig). Thun 26.11’de Conference League’de Ajax’la oynayacak; hafif rotasyon riski var. +EV’nin çoğu ampirik %50’den geliyor. Yalnız yarı modeliyle EV +%2, yalnız motorla −%13. Bu yüzden değer sınırda, kesin değil.'),
3313406:('ZAYIFLADI, değer yok','NEC de PSV de son 10 maçın yalnız 1’inde iki yarıda KG gördü. PSV 24.11’de Real Madrid (CL) maçına çıkacak, rotasyon riski var. NEC’in stoperleri Schuurs ve Nuytinck eksik, bu gol olasılığını artırır. Nesine 5.86 veriyor, adil oran ~7.4, EV −%21.'),
3313844:('DÜŞTÜ (değer yok)','Frankfurt ve Hoffenheim son 10 maçın yalnız 1’inde iki yarıda KG gördü. Hoffenheim ilk yarılarda az gol yiyor (1Y gol yediği maç oranı %30). Nesine 5.61 çok düşük (adil ~7.8), EV −%28. Hoffenheim’da 6 eksik var (Hranáč ve Hajdari stoper), bu gol olasılığını artırır ama fiyatı kurtarmıyor.'),
3314656:('KISMEN ONAYLANDI','Groningen son 10 maçta ilk yarıda maç başı 1.3 gol atıp 1.1 yedi, 1Y KG %50. Kaleci Vaessen ve Hateboer cezalı. Heerenveen ikinci yarılarda maç başı 1.6 gol atıyor. EV −%9; listedeki en az kötü fiyatlardan biri.'),
3313751:('ZAYIFLADI','Wacker İnnsbruck son 10 maçta iki yarıda KG’yi 0 kez gördü ve 2. yarıda 10 maçın sadece 2’sinde gol attı. Liefering’de ise 1Y/2Y KG %50/%50. Bu ligde xG verisi yok. EV −%6.5 (en az kötü), ama veri piyasaya göre aşağı yönlü.'),
3389687:('DÜŞTÜ','Maç MLS playoff serisinde; seri 28.11’de aynı rakiple devam ediyor, bu da temkinli oyun demek. Miami ilk yarılarda az gol yiyor (maç başı 0.3), Columbus ikinci yarılarda az yiyor (0.3). İki takım da son 10 maçın yalnız 1’inde iki yarıda KG gördü. EV −%16.'),
}
EXTRA={
3314269:'Sturm II ve Amstetten son 10 maçın 2’şer tanesinde iki yarıda KG gördü; 1Y KG %50 ve %40. Bu ligde xG ve eksik listesi yok. Nesine 9.46 veriyor; motora göre adil ~9.9, EV yalnız yarı modeliyle ≈ %0, motorla −%4. +%9’un kaynağı ampirik %18. 17:30’da başlıyor.',
3314242:'Utrecht ilk yarılarda zayıf (maç başı 0.4 gol), 2Y KG %60. Cambuur 1Y’de 1.2 gol atıyor. İki tarafta da 5’er eksik var. EV −%12.',
3314768:'Toluca’da 2Y KG %60 ama iki yarıda KG yalnız 10’da 1. Helinho cezalı. EV −%15.',
3313708:'Žilina’nın 2. yarı gücü yüksek (2Y KG %70, iki yarıda KG 10’da 3), ama Dukla’nın 1Y KG oranı %10. Žilina 24.11’de kupa maçı oynayacak. EV −%14.',
3313060:'Liège 2. yarılarda maç başı 1.5 gol yiyor. Anderlecht U23’ün 2Y KG oranı %11. EV −%9.',
}
now=dt.datetime.now(dt.timezone(dt.timedelta(hours=3)))
top=[r for r in x if r['p_final']][:10]
L=[f"# KG İki Yarıda (1. Yarı / 2. Yarı Karşılıklı Gol → Evet/Evet) — derin araştırma, 21.11.2026",
f"Oluşturulma: {now:%H:%M} TSİ. Nesine fiyatları {allm['generated_at'][11:16]} TSİ’de yenilendi (nesine_global.py; keskin referans Pinnacle/OddsMath/Smarkets). Bu pazar {len(allm['all'])} başlamamış maçta açık.",
"",
"**Uyarı: Bu bahis BANKO DEĞİL.** En iyi aday bile yaklaşık 6’da 1 (%17), diğerleri 8–9’da 1 tutar. Nesine’nin bu pazardaki marjı ~%22–27, bu yüzden 1 aday dışında hepsi −EV.",
"",
"## Yöntem",
"- **Piyasa:** Keskin 1X2 ve Alt/Üst fiyatlarından marjsız takım gol beklentisi (μ) alındı. Motorun Evet/Evet adil olasılığı da kullanıldı (GoalTimingModel).",
"- **Veri (FotMob):** Her takımın tüm kulvarlardaki son 10 resmi maçı ve devre arası skorları (HT olayı). Bunlardan 1Y/2Y attığı ve yediği gol ortalaması, 1Y KG %, 2Y KG %, iki yarıda KG % ve xG lehte/aleyhte hesaplandı (xG yalnız FotMob’un verdiği liglerde var). Bugünkü maç sayfasından eksik ve cezalılar, hava durumu, H2H ve takımın sonraki maçı (Avrupa ve kupa rotasyonu) alındı.",
"- **Yarı bazlı model:** Toplam gol: %70 piyasa μ, %30 veri. Yarı payı: takım çiftinin 1Y/2Y gol oranı, %44.5 önseline büzüldü. Her yarı bağımsız Poisson: P(KG yarı) = (1−e^−λh)(1−e^−λa), P(Evet/Evet) = P1·P2.",
"- **Son P:** 0.45 × yarı modeli + 0.40 × motor (piyasa) + 0.15 × ampirik iki yarıda KG oranı. Ampirik oran 20 maçtan, %12 önseline 6 sanal maçla büzüldü. EV = P × Nesine oranı − 1.",
"",
"## Sıralama (ilk 10)",
"| # | Kod | Saat TSİ | Maç | P(Evet/Evet) | 1Y KG | 2Y KG | Adil oran | Nesine | EV | Yarı modeli / Motor / Ampirik |",
"|---|---|---|---|---|---|---|---|---|---|---|"]
for i,r in enumerate(top,1):
  L.append(f"| {i} | {r['code']} | {r['ko'][11:]} | {r['match']} | {r['p_final']:.1%} | {r.get('p_iy_kg',0):.1%} | {r.get('p_2y_kg',0):.1%} | {r['fair_odds']} | {r['nesine_odds']} | {r['ev']:+.1%} | {r.get('p_halfmodel',0):.1%} / {r['engine_p']:.1%} / {r.get('emp_both_rate_shrunk',0):.1%} |")
L+=["","## Maç maç gerekçeler"]
for i,r in enumerate(top,1):
  H,A=r['home_stats'],r['away_stats']
  L.append(f"### {i}. {r['match']} — {r['ko'][11:]} TSİ — P {r['p_final']:.1%}, Nesine {r['nesine_odds']}, EV {r['ev']:+.1%}")
  if r['code'] in VERDICT: L.append(f"- **Önceki listeye göre: {VERDICT[r['code']][0]}.** {VERDICT[r['code']][1]}")
  elif r['code'] in EXTRA: L.append(f"- {EXTRA[r['code']]}")
  for nm,S in (('Ev',H),('Dep',A)):
    if S: L.append(f"- {nm} son {S['n']}: 1Y {S['gf1']:.1f}-{S['ga1']:.1f}, 2Y {S['gf2']:.1f}-{S['ga2']:.1f} (attığı-yediği/maç); 1Y KG %{S['btts1']*100:.0f}, 2Y KG %{S['btts2']*100:.0f}, iki yarıda KG %{S['both']*100:.0f}; xG {('%.2f/%.2f'%(S['xgf'],S['xga'])) if S['xgf'] is not None else 'yok'}. Seri (takım bakışı, 1Y|2Y): `{S['seq']}`")
  if r.get('lambdas'): L.append(f"- λ 1Y {r['lambdas']['h1']}/{r['lambdas']['a1']}, 2Y {r['lambdas']['h2']}/{r['lambdas']['a2']}. Nesine 1Y KG Var {r['nesine_iy_kg_var']}, 2Y KG Var {r['nesine_2y_kg_var']}, KG Var {r['nesine_kg_var']}. Pazar marjı {r['market_overround']}.")
  if r['flags']: L.append("- Bayraklar: "+'; '.join(r['flags']))
  for n in r['notes']: L.append(f"- {n}")
  if r.get('weather'): L.append(f"- Hava: {r['weather']}")
  else: L.append("- Hava: FotMob’da yok")
  L.append("")
L+=["## Önceki 6 adayın durumu"]
for c,(v,why) in VERDICT.items():
  r=next((y for y in x if y['code']==c),None)
  L.append(f"- **{r['match']}** ({r['ko'][11:]}): {v}. P {r['p_final']:.1%}, Nesine {r['nesine_odds']} (16:27’de {r['nesine_odds_1627']}), EV {r['ev']:+.1%}. {why}")
L+=["","## Kaynaklar ve eksikler",
"- Nesine bülteni (scripts/nesine_global.py, 16:37 TSİ). Keskin referanslar: Pinnacle/Smarkets (GitHub Actions), OddsMath, ESPN.",
"- FotMob herkese açık JSON: maç listesi, matchDetails (HT/FT olayları, xG, eksikler, hava, H2H), takım fikstürleri. Kurallara uygun okundu: önbellekli, istekler arası ≥0.8 sn, bot korumasını aşma yok.",
"- Avusturya 2. Liga, Slovakya, National League ve Belçika 1B için FotMob xG vermiyor. 2. Liga ve National League için eksik listesi de yok. Bunlar 'yok' olarak işaretlendi, uydurulmadı.",
"- Hakem profili ve ilk yarı gol zamanlaması (dakika dağılımı) kullanılmadı. Son 10 maç küçük örneklem; ampirik oranlara %15 ağırlık verildi.",
"- API-Football kullanılmadı. Bahis oynanmadı."]
open(D+'kg_iki_yari_detay.md','w').write('\n'.join(L))
json.dump(dict(generated_at=now.isoformat(),nesine_prices_at=allm['generated_at'],market='1. Yarı / 2. Yarı Karşılıklı Gol → Evet/Evet',n_matches_with_market=len(allm['all']),
  method='P=0.45*yarı-Poisson(%70 piyasa μ + %30 FotMob son10 yarı oranları)+0.40*motor+0.15*ampirik(büzülmüş)',
  ranking=top,all_analysed=x,earlier_verdicts={str(k):v for k,v in VERDICT.items()},all_market_matches=[dict(code=a['code'],ko=a['ko'],match=a['home']+' - '+a['away'],odds=a['nesine']['1. Yarı / 2. Yarı Karşılıklı Gol|Evet/Evet']['odds'],engine_p=a['nesine']['1. Yarı / 2. Yarı Karşılıklı Gol|Evet/Evet']['fair']) for a in allm['all']]),
  open(D+'kg_iki_yari_detay.json','w'),ensure_ascii=False,indent=1,default=str)
print('\n'.join(L[:30]))

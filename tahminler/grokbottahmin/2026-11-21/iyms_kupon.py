"""İY/MS kupon önerisi + detay dosyaları (iyms_detay.md/.json). OYNANMAZ."""
import json,math
D='tahminler/grokbottahmin/2026-11-21/'
R={r['code']:r for r in json.load(open('tahminler/grokbottahmin/2026-11-21/veri/iyms/analysed.json'))}
ng=json.load(open('tahminler/grokbottahmin/2026-11-21/veri/iyms/ng_fresh.json')); M={m['code']:m for m in ng['matches']}
tops=json.load(open('tahminler/grokbottahmin/2026-11-21/veri/iyms/tops.json'))
LEGS=[(3314600,'1/1','Linfield ev sahibi 1X2 marjsız %90,6, yarı λ 1,37–0,19; son 10’da İY’de %60 önde. Dikkat: önde olduğu 6 maçın 3’ünü berabere bitirdi.'),
      (3318615,'1/1','Real Madrid son 5 maç G, İY önde bitirdiği 6 maçın 6’sını kazandı; Celta son 10’da İY %60 berabere. Eksik: Mendy, Asencio, Rodrygo; salı PSV (ŞL) var – rotasyon riski düşük-orta.'),
      (3313702,'1/1','Celtic İY önde olduğu 4 maçın 4’ünü kazandı; St. Mirren son 5’te 1 galibiyet, 5 oyuncu eksik (Kabia, Ayunga, Baccus…). Bayrak yok.'),
      (3314405,'1/1','Karagümrük 1X2 marjsız %81; Boluspor son 10’da İY önde olduğunda 3’te 1 kazandı, deplasmanda zayıf. Karagümrük formu dalgalı (LLWLW).'),
      (3312526,'2/2','Roma 1X2 marjsız %79,5; Parma son 5’te 1 galibiyet, İY geride kaldığı 5 maçın hiçbirini çeviremedi; Parma’da 4 eksik (Ndiaye cezalı, Diego Carlos). Roma çarşamba PSG (ŞL) – rotasyon riski.')]
def leg(c,o,why):
  r=R[c]; m=M[c]; sel={(s['market'],s['selection']):s for s in m['selections']}
  iy=sel.get(('1. Yarı Sonucu',o[0]))
  return dict(code=c,ko=r['ko'],league=r['league'],match=r['match'],market='İlk Yarı/Maç Sonucu',selection=o,odds=r['nesine'][o],P=r['P'][o],
    P_engine=r['engine'][o],P_halfmodel=(r['model'] or {}).get(o),emp=r['empirical'][o],EV=r['EV'][o],mbs=r['mbs'],flags=r['flags'],
    unavailable=dict(home=r.get('home_unavailable'),away=r.get('away_unavailable')),reason=why,
    alt_iy=dict(selection='1. Yarı Sonucu '+o[0],odds=iy and iy['odds'],P=iy and iy.get('fair_prob')))
legs=[leg(*x) for x in LEGS]
def combo(n):
  L=legs[:n]; return dict(n=n,legs=[x['match']+' '+x['selection'] for x in L],odds=round(math.prod(x['odds'] for x in L),2),P=round(math.prod(x['P'] for x in L),4),
    EV=round(math.prod(x['odds'] for x in L)*math.prod(x['P'] for x in L)-1,4),
    alt_iy_odds=round(math.prod(x['alt_iy']['odds'] for x in L),2),alt_iy_P=round(math.prod(x['alt_iy']['P'] for x in L),4),
    deadline=min(x['ko'] for x in L))
combos=[combo(n) for n in (3,4,5)]
out=dict(prices=ng['generated_at'],n_matches=len(R),excluded_used=json.load(open('tahminler/grokbottahmin/2026-11-21/veri/iyms/universe.json'))['used'],
  tops=tops,coupon_legs=legs,coupons=combos,
  value_note='Sadece 0,15 ağırlıklı takım deseni nedeniyle pozitif görünen nadir sonuçlar (Karagümrük 2/2 34,0, West Ham 2/0 24,3, NEC 2/1 29,5, Grimsby 2/0 16,75, Celtic 2/2 20,8) keskin piyasa (motor) olasılığıyla hepsi negatif EV. Güvenilir +EV İY/MS yok.',
  matches=list(R.values()))
json.dump(out,open(D+'iyms_detay.json','w'),ensure_ascii=False,indent=1,default=str)
L=[open('tahminler/grokbottahmin/2026-11-21/veri/iyms/rapor_body.md').read()]
L.append("\n## Önerilen İY/MS kuponu (OYNANMADI)\n\n| # | Maç | Saat | Seçim | Oran | P | Motor P | Yarı-model P | EV | Gerekçe |\n|---|---|---|---|---|---|---|---|---|---|")
for i,x in enumerate(legs,1):
  L.append(f"| {i} | {x['match']} | {x['ko'][11:]} | {x['selection']} | {x['odds']} | {x['P']*100:.1f}% | {x['P_engine']*100:.1f}% | {x['P_halfmodel']*100:.1f}% | {x['EV']*100:+.1f}% | {x['reason']} |")
L.append("\n| Kupon | Bacaklar | Toplam oran | Birleşik P | EV | Son oynama | Aynı maçlar İY sonucu ile (oran / P) |\n|---|---|---|---|---|---|---|")
for c in combos: L.append(f"| {c['n']}’lü | {', '.join(c['legs'])} | {c['odds']} | {c['P']*100:.1f}% | {c['EV']*100:+.1f}% | {c['deadline'][11:]} öncesi | {c['alt_iy_odds']} / {c['alt_iy_P']*100:.1f}% |")
L.append("\nNot: Nesine bugün bu maçlarda “1. Yarı Sonucu” oranını İY/MS 1/1–2/2 ile neredeyse aynı (hatta yüksek) vermiş; İY sonucu her zaman İY/MS x/x’i kapsadığı için aynı maçlarda İY sonucu daha yüksek tutma ihtimaliyle benzer oran verir.\n")
L.append("\n## Değer (nadir sonuç) notu\n\n"+out['value_note']+"\n\nVeri boşlukları: 75 başlamamış maçın 33’ünde FotMob formu çekilmedi (aday dışı; sadece motor + lig ortalaması yarı payı). Sakatlık listesi FotMob ‘unavailable’ alanından; ilk 11’ler henüz açıklanmadı. Hariç tutulanlar: bugünkü kuponlardaki tüm maçlar ve 5,03’lük kupon (Milan(K)–Sassuolo(K), Sturm II–Amstetten, Lazio, Catanzaro, Napoli).")
open(D+'iyms_detay.md','w').write('\n'.join(L))
for x in legs: print(x['match'],x['selection'],x['odds'],round(x['P'],3),x['alt_iy'])
for c in combos: print(c)

#!/usr/bin/env python3
"""denetim_2026-11-22_raw.json -> denetim_2026-11-22.json (özet) + denetim_2026-11-22.md"""
import json
from pathlib import Path

D = Path("/workspace/futbol-dehasi/tahminler/grokbottahmin/2026-11-22")
r = json.loads((D / "denetim_2026-11-22_raw.json").read_text())
L = json.loads((D / "dersler_2026-11-22.json").read_text())


def sc(x):
    if x.get("ft"):
        ht = f"İY {x['ht'][0]}-{x['ht'][1]} / " if x.get("ht") else ""
        return f"{ht}MS {x['ft'][0]}-{x['ft'][1]}"
    if x.get("live"):
        return f"canlı {x['live'][0]}-{x['live'][1]} ({x.get('minute')}')"
    return x.get("state") or "?"


def res(w):
    return {True: "✅", False: "❌", None: "⏳"}[w]


def pct(v):
    return "–" if v is None else f"%{v*100:.1f}"


def table(d, title):
    o = [f"| {title} | n | Tuttu | İsabet | Ort. P | Fark | Bekleyen |", "|---|---|---|---|---|---|---|"]
    for k, v in d.items():
        if v["n"] == 0 and v["pending_or_unknown"] == 0:
            continue
        gap = "–" if v["gap"] is None else f"{v['gap']*100:+.1f}p"
        o.append(f"| {k} | {v['n']} | {v['won']} | {pct(v['hit'])} | {pct(v['avg_p'])} | {gap} | {v['pending_or_unknown']} |")
    return "\n".join(o)


md = [f"# Denetim 2026-11-22 (sabah) — Futbol-Dehasi / grokbot", "",
      f"Oluşturma: {r['generated_at']}. Kaynaklar: {'; '.join(r['sources'])}.",
      "Skor uydurulmadı: bulunamayan ⏳/bilinmiyor olarak bırakıldı. Bahisler 90' skoruyla notlandı.", ""]
md += ["## Oynanan kuponlar", ""]
tot_stake = tot_ret = 0
for c in r["coupons"]:
    if not c["played"]:
        continue
    tot_stake += c["stake"]
    tot_ret += c["return_tl"] or 0
    md += [f"### {c['id']} — {c['stake']} TL × {c['odds']} (yatırıldı {c['placed']}) → **{c['status']}**", "",
           "| Başlama | Maç | Seçim | Oran | Skor | Sonuç |", "|---|---|---|---|---|---|"]
    for l in c["legs"]:
        md.append(f"| {l['ko']} | {l['match']} | {l['name']} | {l['odds']} | {sc(l)} | {res(l['won'])} |")
    md.append(f"\nBacak: {c['legs_won']} tuttu, {c['legs_lost']} yattı, {c['legs_pending']} bekliyor.\n")
md.append(f"**Toplam (4 kupon): yatırılan {tot_stake} TL, dönen {tot_ret} TL.**\n")
md += ["## Oynanmayan kupon dosyaları", ""]
for c in r["coupons"]:
    if c["played"]:
        continue
    md += [f"### {c['id']} — {c['title']} — {c['odds']} oran → **{c['status']}**", "",
           "| Başlama | Maç | Seçim | Oran | Skor | Sonuç |", "|---|---|---|---|---|---|"]
    for l in c["legs"]:
        md.append(f"| {l['ko']} | {l['match']} | {l['name']} | {l['odds']} | {sc(l)} | {res(l['won'])} |")
    md.append("")
s = r["summary"]
md += ["## Genel isabet", "", table({
    "21K akşam+gece ana seçimler (önceki denetimde notlanamayan)": s["21K_yeniden_headline"],
    "22K ana seçimler (başlamış)": s["22K_ana_secim"],
    "Ana seçim havuzu (tekil)": s["headline_havuz"],
    "Tüm uygun seçimler havuzu": s["tum_uygun_havuz"],
    "Kupon bacakları (tekil, tüm dosyalar)": s["kupon_bacak_tekil"],
    "Oynanan kupon bacakları": s["kupon_bacak_oynanan"]}, "Küme"), ""]
md += ["## Kalibrasyon (tahmin P → gerçek)", "", "### Ana seçim havuzu", "", table(r["calibration_headline"], "P aralığı"), "",
       "### Tüm uygun seçimler", "", table(r["calibration_tum_uygun"], "P aralığı"), "",
       "### Kupon bacakları", "", table(r["calibration_kupon_bacak"], "P aralığı"), ""]
md += ["## Aileye göre", "", "### Ana seçim havuzu", "", table(r["family_headline"], "Aile"), "",
       "### Tüm uygun seçimler", "", table(r["family_tum_uygun"], "Aile"), "",
       "### Kupon bacakları", "", table(r["family_kupon_bacak"], "Aile"), ""]
if r.get("csv_tarih_hatasi_23K"):
    md += ["## Veri hatası: 22 Kasım CSV'sinde yanlış tarihli maçlar", "",
           f"`mac_tahminleri.csv` içinde **{len(r['csv_tarih_hatasi_23K'])}** seçim \"2026-11-22 00:00–04:10\" diye yazılmış, "
           "ama Nesine'de bu maçlar **23 Kasım** gecesi (Pazar→Pazartesi). Yani bunlar henüz oynanmadı; dün gecenin "
           "maçları değil. Gece için verilen 'en olası skorlar' listesi (River–Lanus, Instituto–Huracán vb.) da bu maçlardı.", "",
           "| CSV saati | Nesine gerçek | Maç | Seçim |", "|---|---|---|---|"]
    for m in r["csv_tarih_hatasi_23K"]:
        md.append(f"| {m['csv_kickoff']} | {m['nesine_kickoff']} | {m['match']} | {m['name']} |")
    md.append("")
md += ["## Dersler (kupon kurma)", ""] + [f"{i}. {x}" for i, x in enumerate(L["lessons"], 1)] + [""]
(D / "denetim_2026-11-22.md").write_text("\n".join(md), encoding="utf-8")
slim = {k: v for k, v in r.items() if k not in ("rows_22K_tum",)}
slim["lessons"] = L["lessons"]
slim["totals_played"] = {"stake_tl": tot_stake, "return_tl": tot_ret}
(D / "denetim_2026-11-22.json").write_text(json.dumps(slim, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("yazıldı", tot_stake, tot_ret)

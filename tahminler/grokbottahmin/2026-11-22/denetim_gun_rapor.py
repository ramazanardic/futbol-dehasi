#!/usr/bin/env python3
"""denetim_gun_1715_raw.json -> denetim_gun_1715.json (özet) + denetim_gun_1715.md"""
import json
import sys
from pathlib import Path

OUT = sys.argv[1] if len(sys.argv) > 1 else "1715"

D = Path("/workspace/futbol-dehasi/tahminler/grokbottahmin/2026-11-22")
r = json.loads((D / f"denetim_gun_{OUT}_raw.json").read_text())
L = json.loads((D / "dersler_2026-11-22.json").read_text())
ICON = {"tuttu": "✅", "yattı": "❌", "bekliyor": "⏳", "belirsiz": "❓", "iptal/ertelendi": "🚫"}


def sc(x):
    if x.get("ms"):
        ht = f"İY {x['iy'][0]}-{x['iy'][1]} / " if x.get("iy") else ""
        return f"{ht}MS {x['ms'][0]}-{x['ms'][1]}"
    if x.get("canli"):
        ht = f"İY {x['iy'][0]}-{x['iy'][1]}, " if x.get("iy") else ""
        return f"{ht}canlı {x['canli'][0]}-{x['canli'][1]}" + (f" ({x['dk']}')" if x.get("dk") else "")
    return "–"


def pct(v):
    return "–" if v is None else f"%{v*100:.1f}"


def ic(d):
    return ICON.get(d.split(" (")[0], "") + " " + d


def table(d, title):
    o = [f"| {title} | n | Tuttu | İsabet | Ort. P | Fark | Bekleyen | Belirsiz |", "|---|---|---|---|---|---|---|---|"]
    for k, v in d.items():
        gap = "–" if v["fark"] is None else f"{v['fark']*100:+.1f}p"
        o.append(f"| {k} | {v['n']} | {v['tuttu']} | {pct(v['isabet'])} | {pct(v['ort_p'])} | {gap} | {v['bekleyen']} | {v['belirsiz']} |")
    return "\n".join(o)


o = r["ozet"]
md = ["# Denetim 2026-11-22 gün içi — Futbol-Dehasi / grokbot", "",
      f"Oluşturma: {r['generated_at']}. Kaynaklar: {'; '.join(r['kaynaklar'])}.",
      "Skor uydurulmadı: skoru bulunamayan ❓ belirsiz, başlamamış/sürmekte olan ⏳ bekliyor. Bahisler 90' skoruyla notlandı; "
      "İY pazarları devre arası geçmişse İY skoruyla kesinleştirildi.", "",
      "## Özet", "", table({"Sohbette önerilen seçimler (tekil)": o["sohbet_tekil"],
                             "Havuz: maç başına en iyi seçim (P≥0,65, oran≥1,20)": o["havuz_en_iyi_P65"],
                             "Havuz: tüm P≥0,65 adaylar": o["havuz_tum_P65"]}, "Küme"), ""]
md += ["## Sohbette önerilen seçimler", ""]
cur = None
for x in r["sohbet_secimleri"]:
    if x["grup"] != cur:
        cur = x["grup"]
        md += ["", f"### {cur}", "", "| Başlama | Maç | Seçim | Oran | P | Skor | Sonuç |", "|---|---|---|---|---|---|---|"]
    md.append(f"| {x['ko'][5:]} | {x['mac']} | {x['secim']} | {x['oran'] or '–'} | {pct(x['p'])} | {sc(x)} | {ic(x['durum'])} |")
md += ["", "### Gruplara göre", "", table(r["sohbet_grup"], "Grup"), "", "### Aileye göre (tekil)", "", table(r["sohbet_aile"], "Aile"), ""]
md += ["## Oynanan kuponlar (oynanan_kuponlar.json)", ""]
for k, v in (r.get("oynanan_kuponlar") or {}).items():
    md += [f"### {k} — {v['stake']} TL × {v['oran']} (yatırıldı {v['placed']}) → **{v['durum']}**, dönen {v['donen_tl']} TL", "",
           "| Başlama | Maç | Seçim | Oran | Skor | Sonuç |", "|---|---|---|---|---|---|"]
    md += [f"| {b['ko'][5:]} | {b['mac']} | {b['secim']} | {b['oran']} | {sc(b)} | {ic(b['durum'])} |" for b in v["bacaklar"]]
    md.append("")
md += ["## Önerilen / dosyadaki kuponlar (oynanmadı)", ""]
for k, v in r["kuponlar"].items():
    if "bacaklar" in v:
        md += [f"### {k} — oran {v['oran']}, model P {pct(v['p_model'])} → **{v['durum']}**", "",
               "| Başlama | Maç | Seçim | Oran | Skor | Sonuç |", "|---|---|---|---|---|---|"]
        md += [f"| {b['ko'][5:]} | {b['mac']} | {b['secim']} | {b['oran']} | {sc(b)} | {ic(b['durum'])} |" for b in v["bacaklar"]]
        md.append("")
    else:
        md.append(f"- **{k}** → {v['durum']} ({v['tuttu']} tuttu, {v['yattı']} yattı, {v['bekleyen']} bekliyor)")
md += ["", "## Havuz (analiz_1000_1400 + analiz_gun): maç başına en iyi P≥0,65 seçim", "",
       "### Aileye göre", "", table(r["havuz_en_iyi_aile"], "Aile"), "",
       "### P bandına göre (kalibrasyon)", "", table(r["havuz_en_iyi_band"], "P bandı"), "",
       "### Seçime göre", "", table(r["havuz_en_iyi_secim"], "Seçim"), "",
       "### Fiyat katmanına göre", "", table(r["havuz_en_iyi_katman"], "Katman"), "",
       "## Havuz: tüm P≥0,65 adaylar", "", "### Aileye göre", "", table(r["havuz_tum_aile"], "Aile"), "",
       "### P bandına göre", "", table(r["havuz_tum_band"], "P bandı"), "",
       "## Sonuçlanan havuz seçimleri (maç başına en iyi)", "", "| Başlama | Maç | Seçim | Oran | P | Skor | Sonuç |", "|---|---|---|---|---|---|---|"]
md += [f"| {x['ko'][5:]} | {x['mac']} | {x['secim']} | {x['oran']} | {pct(x['p'])} | {sc(x)} | {ic(x['durum'])} |"
       for x in sorted(r["havuz_en_iyi"], key=lambda x: x["ko"]) if x["durum"] != "bekliyor"]
md += ["", "## Dersler", ""] + [f"{i}. {x}" for i, x in enumerate(L["lessons"], 1)] + [""]
(D / f"denetim_gun_{OUT}.md").write_text("\n".join(md), encoding="utf-8")
slim = {k: v for k, v in r.items() if k != "havuz_tum"}
slim["havuz_tum_sonuclanan"] = [x for x in r["havuz_tum"] if x["won"] is not None]
slim["dersler"] = L["lessons"]
(D / f"denetim_gun_{OUT}.json").write_text(json.dumps(slim, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("yazıldı")

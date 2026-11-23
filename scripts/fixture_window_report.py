#!/usr/bin/env python3
"""Read-only consolidated analysis of every NOT-YET-STARTED calendar-day fixture.

Uses only real upstream data produced by this repo's Nesine/global-odds engine.
Never invents missing stats, implied odds or injury reports; does not place bets.

QUANTFOOT_AI=chatgbttahmin python scripts/fixture_window_report.py \
  --date-from 2026-11-23 --date-to 2026-11-24 --out /tmp/football-fixtures

Data input is Nesine's 07:00–07:00 BETTING-day snapshots; this report converts
them to Turkey's 00:00–00:00 CALENDAR dates and filters future kickoffs.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
from pathlib import Path

TSI = dt.timezone(dt.timedelta(hours=3))
ROOT = Path(__file__).resolve().parents[1]
AI = os.environ.get("QUANTFOOT_AI", "chatgbttahmin")
PATH = ROOT / "tahminler" / AI


def val(x):
    try:
        n = float(x)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _fmt(x, digits=1):
    f = val(x)
    return f"{f:.{digits}f}" if f is not None else "doğrulanamadı"


def _prob(x):
    f = val(x)
    return f"%{100 * f:.1f}" if f is not None and 0 <= f <= 1 else "yok"


def kickoff(m):
    value = m.get("kickoff_iso") or m.get("kickoff")
    if not value:
        return None
    try:
        t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return t.astimezone(TSI) if t.tzinfo is not None else t.replace(tzinfo=TSI)
    except ValueError:
        return None


def _short(x, limit=165):
    if x in (None, "", [], {}):
        return ""
    if isinstance(x, (dict, list)):
        x = json.dumps(x, ensure_ascii=False, default=str)
    return str(x).replace("\n", " ").replace("|", "/")[:limit]


def top5(m):
    # The engine builds its top-5 independently, with each candidate's original probability source.
    existing = m.get("en_yuksek_5")
    if isinstance(existing, list) and existing:
        return existing[:5]
    sels = [s for s in (m.get("selections") or []) if
            val(s.get("fair_prob")) is not None and val(s.get("odds")) is not None]
    # Only a fallback presentation order; do not pretend the result is five distinct market families.
    return sorted(sels, key=lambda s: val(s.get("fair_prob")) or 0, reverse=True)[:5]


def load_deep(day):
    filename = PATH / day / "derin_tahminler.json"
    if not filename.exists():
        return {}
    try:
        data = json.loads(filename.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {str(row.get("code")): row for row in data if isinstance(row, dict)}
    except (OSError, ValueError):
        pass
    return {}


def collect(first, last, now):
    # Betting day 07:00–07:00. Need prior betting day too for 00:00–06:59
    # calendar matches. All duplicates deduplicated by Nesine code and kickoff.
    start = first - dt.timedelta(days=1)
    dates = [start + dt.timedelta(days=i) for i in range((last - start).days + 1)]
    gathered, sources = {}, []
    for day in dates:
        day_iso = day.isoformat()
        path = PATH / day_iso / "nesine_global.json"
        if not path.exists():
            sources.append({"betting_date": day_iso, "status": "missing",
                            "path": str(path.relative_to(ROOT))})
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            sources.append({"betting_date": day_iso, "status": type(exc).__name__,
                            "path": str(path.relative_to(ROOT))})
            continue
        sources.append({"betting_date": day_iso, "status": "ok",
                        "generated_at": data.get("generated_at"),
                        "ref_age_hours": data.get("ref_age_hours"),
                        "number_of_matches_in_betting_day": len(data.get("matches") or []),
                        "path": str(path.relative_to(ROOT))})
        deep = load_deep(day_iso)
        for m in data.get("matches") or []:
            ko = kickoff(m)
            if not ko or ko <= now or not first <= ko.date() <= last:
                continue
            key = (str(m.get("code")), ko.isoformat())
            record = {**m, "_calendar_date": ko.date().isoformat(),
                      "_kickoff_tsi": ko.isoformat(),
                      "_research_snapshot": data.get("generated_at"),
                      "_source_betting_date": day_iso,
                      "_deep": deep.get(str(m.get("code")))}
            gathered[key] = record
    return sorted(gathered.values(), key=lambda x: x["_kickoff_tsi"]), sources


def build_report(first, last, now):
    matches, sources = collect(first, last, now)
    stats = {"total_future": len(matches),
             "globally_priced": sum(x.get("status") == "fiyatlandı" for x in matches),
             "non_global_or_unpriced": sum(x.get("status") != "fiyatlandı" for x in matches),
             "team_research": sum(bool(x.get("research")) for x in matches),
             "deep_with_history": sum(bool((x.get("_deep") or {}).get("games")) for x in matches),
             "oddsmath_or_direct": sum(any(s.get("direct") is True for s in x.get("selections") or [])
                                       for x in matches),
             "markets_with_price": sum(len(x.get("selections") or []) for x in matches),
             "special_bets": sum(x.get("price_tier") == "ozel_bahis" for x in matches)}
    compact = []
    for m in matches:
        research = m.get("research") or {}
        top = top5(m)
        compact.append({
            "code": m.get("code"), "kickoff_tsi": m["_kickoff_tsi"],
            "date": m["_calendar_date"], "league": m.get("league"),
            "home": m.get("home"), "away": m.get("away"),
            "pricing_status": m.get("status"),
            "price_tier": m.get("price_tier"),
            "bookmaker_reference": m.get("reference"),
            "reference_age_h": m.get("ref_age_hours"),
            "number_of_offered_markets": m.get("n_nesine_selections"),
            "number_of_priced_selections": len(m.get("selections") or []),
            # All 21+ market families, prices, probabilities and EV—not just top five.
            "all_priced_selections": m.get("selections") or [],
            "all_offered_selections": m.get("offered_selections") or [],
            "research_full": research,
            "mu_home": m.get("mu_home"), "mu_away": m.get("mu_away"),
            "fair_1x2": m.get("fair_1x2"),
            "goal_over_2_5": next((s.get("fair_prob") for s in m.get("selections") or []
                                   if s.get("name") == "2.5 Üst"), None),
            "weather": research.get("weather") or m.get("weather"),
            "risks": research.get("flags") or m.get("risk_flags") or [],
            "team_research_present": bool(research),
            "team_evidence": research.get("teams"),
            "absences": research.get("absences") or research.get("tm_absences"),
            "deep_history": m.get("_deep"),
            "top5": top,
            "upstream_source_betting_date": m["_source_betting_date"],
            "upstream_generated_at": m["_research_snapshot"],
        })
    return {"snapshot_tsi": now.isoformat(), "calendar_window": [first.isoformat(), last.isoformat()],
            "ai_area": AI, "statistics": stats, "inputs": sources, "fixtures": compact}


def save(report, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / "all_upcoming_matches.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),
                                                   encoding="utf-8")
    columns = ("date", "kickoff_tsi", "code", "league", "home", "away", "pricing_status", "price_tier",
               "bookmaker_reference", "reference_age_h", "number_of_offered_markets",
               "number_of_priced_selections", "mu_home", "mu_away", "goal_over_2_5",
               "top5", "risks", "team_research_present", "upstream_generated_at")
    with (out / "all_upcoming_matches.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for m in report["fixtures"]:
            writer.writerow({k: (_short(m.get(k), 900) if isinstance(m.get(k), (dict, list)) else m.get(k))
                             for k in columns})
    stat = report["statistics"]
    md = [f"# Başlamamış bütün Nesine maçları: {report['calendar_window'][0]} – {report['calendar_window'][1]}",
          "", f"**Canlı kesit:** {report['snapshot_tsi']} TSİ",
          "Maçlar **takvim tarihine** göre filtrelendi. Nesine verisi 07:00–07:00 bahis günü olarak geldiğinden",
          "önceki bahis gününün gece maçları da denetlendi.", "",
          f"- Başlamamış maç: **{stat['total_future']}**",
          f"- Küresel kaynakla fiyatlanmış: **{stat['globally_priced']}**",
          f"- Fiyatlanmamış / düşük güven: **{stat['non_global_or_unpriced']}**",
          f"- Araştırma verisi olan: **{stat['team_research']}**",
          f"- Derin geçmiş maç dosyası olan: **{stat['deep_with_history']}**",
          f"- Toplam fiyatlanan pazar tercihi: **{stat['markets_with_price']}**",
          "",
          "## Gün bazlı eksiksiz maç listesi", "",
          "Her maçta mevcut olan tüm 1X2 oranları, xG beklentileri, tüm fiyatlı 21+ pazarın oran/olasılık/EV değerleri, sakatlık ve",
          "form verileri JSON'da saklıdır. Sayısı veya güveni bilinmeyen hiçbir istatistik uydurulmaz.", ""]
    for day in report["calendar_window"]:
        pass
    for day in sorted({m["date"] for m in report["fixtures"]}):
        md += [f"### {day}", "",
               "| Saat TSİ | Lig | Maç (Nesine kodu) | Fiyat / kaynak | xG (ev–dep) | 1/X/2 | 2,5 Üst |",
               "|---|---|---|---|---|---|---|"]
        for m in (r for r in report["fixtures"] if r["date"] == day):
            p = m.get("fair_1x2") or []
            ptxt = " / ".join(_prob(x) for x in p) if len(p) == 3 else "doğrulanamadı"
            mu = f"{_fmt(m['mu_home'])} / {_fmt(m['mu_away'])}"
            quote = _short(m.get("bookmaker_reference") or m.get("pricing_status"), 36)
            md.append(f"| {m['kickoff_tsi'][11:16]} | {_short(m['league'], 35)} | "
                      f"{_short(m['home'], 27)} – {_short(m['away'], 27)} ({m['code']}) | "
                      f"{quote} | {mu} | {ptxt} | {_prob(m['goal_over_2_5'])} |")
        md.append("")
    md += ["## Her maçın en yüksek beş piyasa olasılığı", "",
           "**Sıralama ≠ bahis önerisi.** Seçimler aynı maça ait olduğundan birbirleriyle korelasyonludur.",
           "Sakatlık/hava bilgisi yalnızca kaynakta mevcutsa güvenilir kabul edilir.", ""]
    for m in report["fixtures"]:
        names = []
        for s in m["top5"]:
            if isinstance(s, dict):
                name = s.get("name") or s.get("market") or s.get("label") or s.get("selection") or "bilinmeyen"
                p = s.get("p_cal") or s.get("p") or s.get("fair_prob") or s.get("probability")
                odds = s.get("odds") or s.get("nesine_oran")
                names.append(f"{_short(name, 42)} {_prob(p)}" +
                             (f" @ {_fmt(odds, 2)}" if val(odds) is not None else ""))
        md.append(f"- **{m['date']} {m['kickoff_tsi'][11:16]}** {m['home']} – {m['away']}: " +
                  ("; ".join(names) if names else "Doğrulanmış piyasa olasılığı yok"))
    md += ["", "## Kaynak ve kapsam uyarıları", "",
           "- Şimdiden başlamış karşılaşmalar hariç; tarihleri Türkiye saatine göre seçtik.",
           "- Nesine başlangıç saati geriden güncellenmiş olabilir; bahis öncesi canlı durumu tekrar kontrol et.",
           "- Dış referansın yaşı / sakatlık / on bir / hava ve lig eşleşmesi doğrulanmazsa güvenli kupon üretilmez.",
           "- Küresel piyasa adil olasılığı ile model son kalibre edilmiş kupon olasılığı aynı şey değildir.",
           "- Karşılaşma veya pazar eksikse 'yok' olarak korunur; ne oran ne performans varsayılır.",
           "- JSON: her maç için tüm açılmış kaynak alanları. CSV: tüm başlamamış maçların analize uygun tablosu.",
           "", "## Veri kaynaklarının çekilme durumu", ""]
    for x in report["inputs"]:
        md.append(f"- {x['betting_date']}: {x['status']}, bülten maçı "
                  f"{x.get('number_of_matches_in_betting_day', '-')}, zaman {x.get('generated_at', '-')}, "
                  f"global fiyat yaşı {x.get('ref_age_hours', '-')} saat")
    (out / "all_upcoming_matches.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date-from", required=True, type=dt.date.fromisoformat)
    ap.add_argument("--date-to", required=True, type=dt.date.fromisoformat)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.date_to < args.date_from:
        ap.error("--date-to must not precede --date-from")
    report = build_report(args.date_from, args.date_to, dt.datetime.now(TSI))
    save(report, args.out)
    print(json.dumps({"snapshot": report["snapshot_tsi"], **report["statistics"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()

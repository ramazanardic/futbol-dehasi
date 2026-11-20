"""Pre-kick-off check of every coupon leg, and closing-price (CLV) record.

    python scripts/kupon_kontrol.py kontrol --date 2026-11-20   # after nesine_global.py (scheduled.py kadro)
    python scripts/kupon_kontrol.py ozet                         # all days: does the pick beat the closing price?

`kontrol` compares each not-started leg of the day's coupons (tahminler/claudetahmin/<date>/kupon_*x_*.json) with the
newest analysis (nesine_global.json, re-run with line-ups ~1 h before kick-off) and warns when a leg should be
replaced: global probability under the 55 % leg floor or down >= 5 points, Nesine selection suspended, Nesine
odds under 1.20, an important absence announced after the price (research_block) or a new risk/steam flag.
Output: tahminler/claudetahmin/<date>/kupon_kontrol.md (+ Windows pop-up / Telegram for new warnings).

Line-ups: in the 15-minute watcher (live odds), each not-started leg of a coupon in force whose kick-off is at most
LINEUP_WINDOW_MIN away is re-checked on the announced ESPN line-up (regular goalkeeper / top scorer / 3+ regulars
missing); until the line-up is out it is asked again on the next run, then the result is kept in kupon_clv.json.

The same run keeps, per leg, the last global probability seen before kick-off (kupon_clv.json). That is the
closing price: CLV = closing probability - probability when the coupon was built. A system that picks well
sees the sharp market move towards its picks (positive CLV) long before results prove anything.
`ozet` aggregates every day into tahminler/claudetahmin/clv.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / "tahminler" / os.environ.get("QUANTFOOT_AI", "claudetahmin")  # the asking AI's own folder
DAILY = AREA  # analysis, coupons, checks and CLV all live there
TSI = dt.timezone(dt.timedelta(hours=3))
MIN_PROB = 0.55     # coupon leg floor (user rule)
MIN_ODDS = 1.20
DROP_ALERT = 0.05   # global probability fell this much since the coupon was built
LINEUP_WINDOW_MIN = 75


def lineup_flags(m: dict) -> list[str] | None:
    """Line-up warnings of an ESPN-linked match; None while the line-ups are not announced (or no ESPN event)."""
    ev = (m.get("research") or {}).get("espn_event")
    if not ev:
        return None
    sys.path.insert(0, str(ROOT / "src"))
    from quantfoot.data import match_research as mr
    res = mr.research(str(ev))
    if not res or not any(t.get("lineup_announced") for t in (res.get("teams") or {}).values()):
        return None
    return mr.staleness_flags(res, None)


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def betting_day(now: dt.datetime | None = None) -> str:
    """The Nesine betting day runs 07:00-07:00 TSİ (late kick-offs belong to the previous day)."""
    now = now or dt.datetime.now(TSI)
    return (now.date() if now.hour >= 7 else now.date() - dt.timedelta(days=1)).isoformat()


def active_coupons(date: str) -> set[str]:
    """Stems of the coupons currently in force: the latest file of every (target, family) group."""
    latest: dict[tuple[str, str], str] = {}
    for f in sorted((AREA / date).glob("kupon_*x_*.json")):
        parts = f.stem.split("_")
        latest[(parts[1], parts[2] if len(parts) >= 4 else "karma")] = f.stem
    return set(latest.values())


def coupon_legs(date: str) -> dict[str, dict]:
    """Every leg of the day's coupon files, keyed by code|key (a leg in several coupons is checked once)."""
    legs: dict[str, dict] = {}
    for f in sorted((AREA / date).glob("kupon_*x_*.json")):
        data = _load(f) or {}
        for i, c in enumerate(data.get("coupons", []), 1):
            for leg in c.get("legs", []):
                lid = f"{leg['code']}|{leg.get('key')}"
                e = legs.setdefault(lid, {**leg, "coupons": []})
                e["coupons"].append(f"{f.stem} #{i}")
    return legs


def live_odds() -> dict[int, dict[str, float]] | None:
    """Live Nesine odds (lower of two bulletin reads). The analysis file can be older than the coupons: on 20 Nov an
    older analysis showed a leg at 1.44 while the coupon was built and re-checked live at 1.61-1.64."""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from nesine_kupon import read_bulletin_odds  # noqa: PLC0415
        return read_bulletin_odds()[0]
    except Exception:  # noqa: BLE001 - fall back to the analysis odds
        return None


def check(date: str, now: dt.datetime | None = None, live: dict | None = None,
          lineups=None, active: set[str] | None = None) -> tuple[list[dict], dict]:
    """``live``: {code: {key: odds}} from the Nesine bulletin now; None = odds of the analysis file.
    ``lineups``: match -> line-up warnings or None (not announced); called for legs of ``active`` coupons only."""
    now = now or dt.datetime.now(TSI)
    analysis = _load(DAILY / date / "nesine_global.json") or {}
    by_code = {int(m["code"]): m for m in analysis.get("matches", [])}
    clv_path = AREA / date / "kupon_clv.json"
    clv = _load(clv_path) or {}
    rows = []
    for lid, leg in coupon_legs(date).items():
        m = by_code.get(int(leg["code"]))
        kick = dt.datetime.fromisoformat(m["kickoff_iso"]) if m else None
        rec = clv.setdefault(lid, {"match": leg["match"], "market": leg["market"], "selection": leg["selection"],
                                   "kickoff": leg["kickoff"], "p_pick": leg["p"], "odds_pick": leg["odds"],
                                   "direct": leg.get("direct"), "reference": leg.get("reference"), "alerted": []})
        rec["coupons"] = leg["coupons"]
        started = kick is None or kick <= now
        s = next((x for x in (m or {}).get("selections", []) if x.get("key") == leg.get("key")), None)
        row = {"lid": lid, "leg": leg, "started": started, "p_now": None, "odds_now": None, "warn": []}
        if not started:
            res = m.get("research") or {}
            if m.get("status") != "fiyatlandı":
                row["warn"].append("global fiyat yok")
            odds = s["odds"] if s else None
            if live is not None:
                odds = (live.get(int(leg["code"])) or {}).get(leg.get("key"))
            if s is None or odds is None:
                row["warn"].append("Nesine'de yok / askıda")
            else:
                s = {**s, "odds": odds}
                row["p_now"], row["odds_now"] = s["fair_prob"], odds
                if m.get("status") == "fiyatlandı":
                    rec.update(p_close=s["fair_prob"], odds_close=s["odds"],
                               close_seen=now.isoformat(timespec="minutes"), close_ref=m.get("reference"))
                if s["fair_prob"] < MIN_PROB:
                    row["warn"].append(f"olasılık %{100 * s['fair_prob']:.0f}: %55 altına düştü")
                elif leg["p"] - s["fair_prob"] >= DROP_ALERT:
                    row["warn"].append(f"olasılık {100 * (leg['p'] - s['fair_prob']):.0f} puan düştü")
                if s["odds"] < MIN_ODDS:
                    row["warn"].append(f"Nesine oranı {s['odds']:.2f}: 1,20 altında")
            if m.get("research_block"):
                row["warn"].append(f"önemli eksik: {m['research_block']}")
            for fl in res.get("flags") or []:
                row["warn"].append(f"uyarı: {fl}")
            in_force = active is None or any(c.split(" #")[0] in active for c in leg["coupons"])
            if lineups and in_force and "lineup" not in rec and kick - now <= dt.timedelta(minutes=LINEUP_WINDOW_MIN):
                try:
                    fl = lineups(m)
                except Exception as e:  # noqa: BLE001 — a failed line-up fetch must not stop the coupon check
                    fl = None
                    print(f"ilk 11 alınamadı ({leg['match']}): {type(e).__name__}")
                if fl is not None:
                    rec["lineup"] = fl
            for fl in rec.get("lineup") or []:
                row["warn"].append(f"ilk 11: {fl}")
        row["new_warn"] = [w for w in row["warn"] if w not in rec["alerted"]]
        rec["alerted"] = sorted(set(rec["alerted"]) | set(row["warn"]))
        rows.append(row)
    clv_path.write_text(json.dumps(clv, ensure_ascii=False, indent=1), encoding="utf-8")
    return rows, clv


def coupon_totals(date: str, rows: list[dict]) -> list[dict]:
    """Each coupon's total Nesine odds on the live odds of its not-started legs (started legs keep their odds):
    the target is a MINIMUM (user rule), so a coupon that slipped under it must be flagged before it is played."""
    now_odds = {r["lid"]: r["odds_now"] for r in rows if not r["started"]}
    out = []
    for f in sorted((AREA / date).glob("kupon_*x_*.json")):
        data = _load(f) or {}
        target = float(data.get("target") or f.name.split("_")[1].rstrip("x"))
        for i, c in enumerate(data.get("coupons", []), 1):
            total, missing = 1.0, False
            for leg in c.get("legs", []):
                lid = f"{leg['code']}|{leg.get('key')}"
                o = now_odds[lid] if lid in now_odds else leg["odds"]
                if o is None:
                    missing, o = True, leg["odds"]
                total *= o
            out.append({"coupon": f"{f.stem} #{i}", "target": target, "built": c["nesine_odds"], "now": round(total, 2),
                        "below": total < target - 1e-9, "missing": missing})
    return out


def clv_stats(clv: dict, now: dt.datetime) -> dict:
    """Legs whose match has started and whose closing probability was seen."""
    done = []
    for r in clv.values():
        try:
            kick = dt.datetime.fromisoformat(r["kickoff"]).replace(tzinfo=TSI)
        except (KeyError, ValueError):
            continue
        if kick <= now and r.get("p_close") is not None:
            done.append(r["p_close"] - r["p_pick"])
    n = len(done)
    return {"n": n, "mean": sum(done) / n if n else None, "pos": sum(d > 0.0005 for d in done),
            "neg": sum(d < -0.0005 for d in done)}


def _fmt_stats(st: dict) -> str:
    if not st["n"]:
        return "henüz kapanış fiyatı görülen başlamış maç yok"
    return (f"{st['n']} bacak · ortalama CLV **{100 * st['mean']:+.1f} puan** · lehimize {st['pos']}, "
            f"aleyhimize {st['neg']}, değişmeyen {st['n'] - st['pos'] - st['neg']}")


def _notify(text: str) -> None:
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from notify_telegram import send_telegram_message  # noqa: PLC0415
        send_telegram_message(text)
    except Exception:  # noqa: BLE001 - optional channel
        pass
    if os.name == "nt":
        subprocess.run(["msg", os.environ.get("USERNAME", "*"), "/TIME:900", text[:250]], capture_output=True, timeout=30)


def cmd_kontrol(date: str, notify: bool = True) -> None:
    now = dt.datetime.now(TSI)
    rows, clv = check(date, now, live_odds(), lineups=lineup_flags, active=active_coupons(date))
    if not rows:
        print(f"{date}: kupon yok")
        return
    md = [f"# {date} — kupon bacakları maç öncesi kontrol ({now:%H:%M} TSİ)", "",
          "İlk 11'ler ~1 saat önce açıklandıktan sonra yeniden yapılan analizle karşılaştırma. "
          "⚠ olan bacağı oynamadan önce değiştirin.", "",
          "| Saat | Maç | Seçim | Oran (kupon → şimdi) | Olasılık (kupon → şimdi) | Durum | Kupon |",
          "|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: x["leg"]["kickoff"]):
        leg = r["leg"]
        if r["started"]:
            rec = clv.get(r["lid"], {})
            pc = rec.get("p_close")
            durum = "başladı" + (f" · kapanış %{100 * pc:.1f} (CLV {100 * (pc - leg['p']):+.1f})" if pc is not None else "")
            odds, prob = f"{leg['odds']:.2f}", f"%{100 * leg['p']:.1f}"
        else:
            durum = "⚠ " + "; ".join(r["warn"]) if r["warn"] else "✓ uygun"
            odds = f"{leg['odds']:.2f} → {r['odds_now']:.2f}" if r["odds_now"] else f"{leg['odds']:.2f} → -"
            prob = f"%{100 * leg['p']:.1f} → %{100 * r['p_now']:.1f}" if r["p_now"] is not None else f"%{100 * leg['p']:.1f} → -"
        md.append(f"| {leg['kickoff'][-5:]} | {leg['match']} | {leg['market']}: {leg['selection']} | {odds} | {prob} | "
                  f"{durum} | {', '.join(leg['coupons'])} |")
    totals = coupon_totals(date, rows)
    if totals:
        md += ["", "**Kupon toplam oranları (bilgi için; kupon kurulduğu andaki oranlarla verildi, sonradan yeniden kurulmaz):**", "",
               "| Kupon | En az | Kurulduğunda | Şimdi | Durum |", "|---|---|---|---|---|"]
        md += [f"| {t['coupon']} | {t['target']:g} | {t['built']:.2f} | {t['now']:.2f} | "
               + ("⚠ minimumun altına düştü" if t["below"] else "✓") + (" · askıda bacak var" if t["missing"] else "") + " |"
               for t in totals]
    md += ["", f"**Kapanış fiyatı (CLV), bugün:** {_fmt_stats(clv_stats(clv, now))}", ""]
    out = AREA / date / "kupon_kontrol.md"
    out.write_text("\n".join(md), encoding="utf-8")
    active = active_coupons(date)
    fresh = [r for r in rows if r["new_warn"] and not r["started"]
             and any(c.split(" #")[0] in active for c in r["leg"]["coupons"])]  # alerts only for coupons in force
    print(f"{len(rows)} bacak kontrol edildi, {sum(1 for r in rows if r['warn'] and not r['started'])} uyarı "
          f"({len(fresh)} yeni) -> {out}")
    # Odds drifting after a coupon was given is not important to the user (20 Nov): coupons are not rebuilt and no
    # pop-up is sent for it; the live totals stay in the report for information only.
    if fresh and notify:
        _notify("QuantFoot kupon uyarısı: " + " | ".join(
            f"{r['leg']['kickoff'][-5:]} {r['leg']['match']} {r['leg']['selection']}: {'; '.join(r['new_warn'])}" for r in fresh))


def cmd_ozet() -> None:
    now = dt.datetime.now(TSI)
    md = ["# Kupon bacakları — kapanış fiyatı (CLV) takibi", "",
          "CLV = maç başlamadan önce görülen son global olasılık − kupon kurulurkenki global olasılık. "
          "Sürekli pozitif CLV, sonuçlar kanıtlamadan önce seçimlerin piyasadan önde olduğunu gösterir.", "",
          "| Gün | Bacak | Ortalama CLV | Lehimize | Aleyhimize |", "|---|---|---|---|---|"]
    allc: dict = {}
    for d in sorted(p.parent.name for p in AREA.glob("*/kupon_clv.json")):
        clv = _load(AREA / d / "kupon_clv.json") or {}
        st = clv_stats(clv, now)
        allc.update({f"{d}|{k}": v for k, v in clv.items()})
        if st["n"]:
            md.append(f"| {d} | {st['n']} | {100 * st['mean']:+.1f} puan | {st['pos']} | {st['neg']} |")
    md += ["", f"**Toplam:** {_fmt_stats(clv_stats(allc, now))}", ""]
    out = AREA / "clv.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"-> {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("kontrol")
    k.add_argument("--date", default=betting_day())
    k.add_argument("--sessiz", action="store_true", help="Pop-up / Telegram uyarısı gönderme")
    sub.add_parser("ozet")
    args = ap.parse_args()
    if args.cmd == "kontrol":
        cmd_kontrol(args.date, notify=not args.sessiz)
    else:
        cmd_ozet()


if __name__ == "__main__":
    main()

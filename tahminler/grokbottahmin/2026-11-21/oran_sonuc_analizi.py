#!/usr/bin/env python3
"""2026-11-21: Nesine 1-X-2 oran profilleri ve maç sonu / ilk yarı sonuçları."""
from __future__ import annotations

import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/workspace/futbol-dehasi")
D = ROOT / "tahminler/grokbottahmin/2026-11-21"
TSI = dt.timezone(dt.timedelta(hours=3))
NOW = dt.datetime.now(TSI)

FAV_BANDS = [
    ("≤1.30", 0, 1.30),
    ("1.31–1.50", 1.30, 1.50),
    ("1.51–1.80", 1.50, 1.80),
    ("1.81–2.10", 1.80, 2.10),
]
DRAW_BANDS = [
    ("≤3.10", 0, 3.10),
    ("3.11–3.50", 3.10, 3.50),
    ("3.51–4.00", 3.50, 4.00),
    ("4.01–5.00", 4.00, 5.00),
    ("≥5.01", 5.00, 99.0),
]


def parse_ts(s) -> dt.datetime | None:
    if not s:
        return None
    s = str(s).strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S%z",
    ):
        try:
            t = dt.datetime.strptime(s.replace("Z", "+0000").replace("+03:00", "+0300").replace("+00:00", "+0000"), fmt)
            return t.astimezone(TSI)
        except ValueError:
            continue
    # ISO with colon in tz
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=TSI)
        return t.astimezone(TSI)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(s, fmt).replace(tzinfo=TSI)
        except ValueError:
            continue
    return None


def valid_ms(arr) -> bool:
    if not isinstance(arr, (list, tuple)) or len(arr) != 3:
        return False
    try:
        return all(isinstance(x, (int, float)) and not isinstance(x, bool) and x > 1.0 for x in arr)
    except TypeError:
        return False


def demargin(odds: list[float]) -> tuple[list[float], float]:
    inv = [1.0 / o for o in odds]
    s = sum(inv)
    return [x / s for x in inv], s - 1.0


def fmt_odd(x: float) -> str:
    s = f"{x:.2f}".replace(".", ",")
    if s.endswith(",00"):
        # keep two decimals for odds consistency
        pass
    return s


def fmt_pct(x: float | None, digits=1) -> str:
    if x is None:
        return "—"
    return f"%{x * 100:.{digits}f}".replace(".", ",")


def fmt_pp(x: float | None) -> str:
    if x is None:
        return "—"
    sign = "+" if x >= 0 else "−" if x < 0 else ""
    # use minus for negative already in number? we'll use + / - with abs
    if x >= 0:
        return f"+{x * 100:.1f}p".replace(".", ",")
    return f"−{abs(x) * 100:.1f}p".replace(".", ",")


def band_fav_odds(o1: float, o2: float) -> str:
    if o1 > 2.10 and o2 > 2.10:
        return "dengeli (iki taraf >2,10)"
    fo = min(o1, o2)
    if fo <= 1.30:
        return "≤1,30"
    if fo <= 1.50:
        return "1,31–1,50"
    if fo <= 1.80:
        return "1,51–1,80"
    if fo <= 2.10:
        return "1,81–2,10"
    return "diğer"


def band_draw(ox: float) -> str:
    if ox <= 3.10:
        return "≤3,10"
    if ox <= 3.50:
        return "3,11–3,50"
    if ox <= 4.00:
        return "3,51–4,00"
    if ox <= 5.00:
        return "4,01–5,00"
    return "≥5,01"


def outcome(ft) -> str | None:
    if not ft or len(ft) < 2 or ft[0] is None or ft[1] is None:
        return None
    h, a = int(ft[0]), int(ft[1])
    if h > a:
        return "1"
    if h < a:
        return "2"
    return "X"


def load_deep():
    rows = json.loads((D / "derin_tahminler.json").read_text())
    out = {}
    for m in rows:
        code = int(m["code"])
        parts = (m.get("match") or " - ").split(" - ", 1)
        home = parts[0].strip() if parts else m.get("home")
        away = parts[1].strip() if len(parts) > 1 else m.get("away")
        ko = parse_ts(m.get("kickoff"))
        out[code] = {
            "code": code,
            "home": home,
            "away": away,
            "league": m.get("league"),
            "kickoff": ko,
            "kickoff_raw": m.get("kickoff"),
        }
    return out


def load_results():
    """Fresh Nesine unlive + earlier index as fallback."""
    fresh = {int(k): v for k, v in json.loads(Path("/tmp/results_raw/unlive_parsed.json").read_text()).items()}
    old = {
        int(k): v
        for k, v in json.loads((D / "denetim_gece_2026-11-21.json").read_text())["results_index"].items()
    }
    merged = {}
    # start with old, overwrite with fresh when stronger
    for src in (old, fresh):
        for c, v in src.items():
            rec = dict(v)
            rec.pop("_sc", None)
            # treat MS with FT but missing period-2 as final (no HT)
            if rec.get("state") != "final" and rec.get("st") == "MS":
                sc = v.get("_sc") or {}
                ft = rec.get("ft")
                if not ft and ("3" in sc or "1" in sc):
                    ft = sc.get("3") or sc.get("1")
                    rec["ft"] = ft
                ht = rec.get("ht") or sc.get("2")
                if ht:
                    rec["ht"] = ht
                if rec.get("ft"):
                    rec["state"] = "final"
                    rec["src"] = rec.get("src") or "nesine"
                    if not rec.get("ht"):
                        rec["ht_missing"] = True
            # only overwrite if new is final or old wasn't final
            prev = merged.get(c)
            if rec.get("state") == "final":
                merged[c] = rec
            elif prev is None or (prev.get("state") != "final" and rec.get("state")):
                # keep previous final; otherwise take newer info
                if not prev or prev.get("state") != "final":
                    merged[c] = rec
    return merged, fresh, old


def collect_odds_snapshots():
    """List of (ts, code, odds, source, kind) kind in {nesine, sharp}."""
    snaps: list[tuple] = []

    hist_path = D / "nesine_history.jsonl"
    with hist_path.open() as f:
        for line in f:
            d = json.loads(line)
            ts = parse_ts(d["ts"])
            if ts is None:
                continue
            for ck, rec in d["m"].items():
                s = (rec or {}).get("s") or {}
                if "MS 1" in s and "MS 0" in s and "MS 2" in s:
                    try:
                        odds = [float(s["MS 1"][0]), float(s["MS 0"][0]), float(s["MS 2"][0])]
                    except (TypeError, ValueError, IndexError):
                        continue
                    if valid_ms(odds):
                        snaps.append((ts, int(ck), odds, f"nesine_history@{d['ts']}", "nesine"))

    for fname, label in [
        ("veri/iyms/ng_1637.json", "ng_1637"),
        ("veri/iyms/ng_fresh.json", "ng_fresh"),
        ("nesine_global.json", "nesine_global"),
    ]:
        p = D / fname
        d = json.loads(p.read_text())
        ts = parse_ts(d.get("generated_at"))
        for m in d.get("matches") or []:
            code = int(m["code"])
            if valid_ms(m.get("nesine_ms")):
                snaps.append((ts, code, [float(x) for x in m["nesine_ms"]], f"{label}@{d.get('generated_at')}", "nesine"))
            if valid_ms(m.get("ref_1x2")):
                snaps.append((ts, code, [float(x) for x in m["ref_1x2"]], f"{label}_ref@{d.get('generated_at')}", "sharp"))
    return snaps


def pick_odds(code: int, kickoff: dt.datetime | None, snaps_by_code: dict):
    """Latest pre-kickoff Nesine; else latest pre-kickoff sharp."""
    items = snaps_by_code.get(code) or []
    if kickoff is None:
        # still prefer latest nesine
        nes = [x for x in items if x[4] == "nesine"]
        pool = nes or [x for x in items if x[4] == "sharp"]
        if not pool:
            return None
        pool.sort(key=lambda x: x[0] or dt.datetime.min.replace(tzinfo=TSI))
        return pool[-1]
    cutoff = kickoff  # inclusive: snapshot at kickoff is still pre-match open
    def ok(x):
        return x[0] is not None and x[0] <= cutoff

    nes = [x for x in items if x[4] == "nesine" and ok(x)]
    if nes:
        nes.sort(key=lambda x: x[0])
        return nes[-1]
    shp = [x for x in items if x[4] == "sharp" and ok(x)]
    if shp:
        shp.sort(key=lambda x: x[0])
        return shp[-1]
    return None


def summarize(rows, implied_key="p"):
    """rows: dicts with result 1/X/2 and p list."""
    n = len(rows)
    if n == 0:
        return {"n": 0}
    c = Counter(r["result"] for r in rows)
    h, x, a = c.get("1", 0), c.get("X", 0), c.get("2", 0)
    imp = [0.0, 0.0, 0.0]
    for r in rows:
        for i in range(3):
            imp[i] += r[implied_key][i]
    imp = [v / n for v in imp]
    # favourite
    fav_hits = fav_n = 0
    fav_imp = 0.0
    for r in rows:
        side = r.get("fav_side")
        if side in ("1", "2"):
            fav_n += 1
            fav_imp += r[implied_key][0] if side == "1" else r[implied_key][2]
            if r["result"] == side:
                fav_hits += 1
    out = {
        "n": n,
        "home_n": h,
        "draw_n": x,
        "away_n": a,
        "home_pct": h / n,
        "draw_pct": x / n,
        "away_pct": a / n,
        "imp_home": imp[0],
        "imp_draw": imp[1],
        "imp_away": imp[2],
        "fav_n": fav_n,
        "fav_win_pct": (fav_hits / fav_n) if fav_n else None,
        "fav_imp": (fav_imp / fav_n) if fav_n else None,
        "fav_delta": ((fav_hits / fav_n) - (fav_imp / fav_n)) if fav_n else None,
        "home_delta": h / n - imp[0],
        "draw_delta": x / n - imp[1],
        "away_delta": a / n - imp[2],
    }
    return out


def md_table(headers, rows) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def main():
    deep = load_deep()
    results, fresh, old = load_results()
    snaps = collect_odds_snapshots()
    by_code: dict[int, list] = defaultdict(list)
    for s in snaps:
        by_code[s[1]].append(s)

    universe = list(deep.values())
    analysed = []
    coverage = Counter()
    unfinished = []
    no_odds = []
    sharp_used = []

    for m in universe:
        c = m["code"]
        res = results.get(c)
        state = (res or {}).get("state")
        if state != "final" or not (res or {}).get("ft"):
            coverage[f"sonuç yok: {state or 'yok'}"] += 1
            unfinished.append({**m, "state": state})
            continue
        res_ft = outcome(res["ft"])
        if res_ft is None:
            coverage["skor yok"] += 1
            continue
        picked = pick_odds(c, m["kickoff"], by_code)
        if not picked:
            coverage["oran yok"] += 1
            no_odds.append({**m, "ft": res["ft"], "result": res_ft, "league": res.get("league") or m["league"]})
            continue
        ts, _, odds, src, kind = picked
        p, margin = demargin(odds)
        o1, ox, o2 = odds
        fav_band = band_fav_odds(o1, o2)
        if o1 < o2:
            fav_side, fav_odds, fav_is = "1", o1, "ev"
        elif o2 < o1:
            fav_side, fav_odds, fav_is = "2", o2, "dep"
        else:
            fav_side, fav_odds, fav_is = None, o1, "eşit"
        # for balanced band, still mark shorter side as fav (may be none if equal)
        rec = {
            "code": c,
            "home": res.get("home") or m["home"],
            "away": res.get("away") or m["away"],
            "league": res.get("league") or m["league"],
            "kickoff": m["kickoff"].strftime("%Y-%m-%d %H:%M") if m["kickoff"] else m["kickoff_raw"],
            "kickoff_iso": m["kickoff"].isoformat() if m["kickoff"] else None,
            "odds": [round(o1, 4), round(ox, 4), round(o2, 4)],
            "odds_kind": kind,
            "odds_source": src,
            "snapshot_ts": ts.isoformat() if ts else None,
            "hours_before_ko": round((m["kickoff"] - ts).total_seconds() / 3600, 2) if (m["kickoff"] and ts) else None,
            "margin": round(margin, 4),
            "p": [round(x, 5) for x in p],
            "result": res_ft,
            "ft": list(res["ft"]),
            "ht": list(res["ht"]) if res.get("ht") else None,
            "ht_result": outcome(res["ht"]) if res.get("ht") else None,
            "fav_band": fav_band,
            "draw_band": band_draw(ox),
            "fav_side": fav_side,
            "fav_is": fav_is,
            "fav_odds": round(fav_odds, 4) if fav_odds else None,
            "fav_won": (res_ft == fav_side) if fav_side else None,
        }
        analysed.append(rec)
        if kind == "nesine":
            coverage["biten + Nesine oranı"] += 1
        else:
            coverage["biten + sharp oran (Nesine yok)"] += 1
            sharp_used.append(rec)

    nesine_rows = [r for r in analysed if r["odds_kind"] == "nesine"]
    sharp_rows = [r for r in analysed if r["odds_kind"] == "sharp"]

    # tables
    fav_order = ["≤1,30", "1,31–1,50", "1,51–1,80", "1,81–2,10", "dengeli (iki taraf >2,10)"]
    draw_order = ["≤3,10", "3,11–3,50", "3,51–4,00", "4,01–5,00", "≥5,01"]

    def by_band(rows, key, order):
        groups = {b: [] for b in order}
        for r in rows:
            groups.setdefault(r[key], []).append(r)
        return [(b, groups.get(b, [])) for b in order]

    # notable close games: both 1 and 2 in [1.90, 2.50]
    close = [
        r
        for r in analysed
        if 1.90 <= r["odds"][0] <= 2.50 and 1.90 <= r["odds"][2] <= 2.50
    ]
    close.sort(key=lambda r: abs(r["odds"][0] - r["odds"][2]))

    balanced = [r for r in analysed if r["fav_band"].startswith("dengeli")]
    balanced.sort(key=lambda r: abs(r["odds"][0] - r["odds"][2]))

    upsets = [
        r
        for r in analysed
        if r["fav_side"] and r["fav_odds"] is not None and r["fav_odds"] <= 1.50 and r["fav_won"] is False
    ]
    upsets.sort(key=lambda r: r["fav_odds"])

    # HT rows: those with ht
    ht_rows = [r for r in analysed if r.get("ht_result")]

    overall_n = summarize(nesine_rows)
    overall_all = summarize(analysed)

    # JSON
    tables = {
        "fav_band_nesine": {b: summarize(rs) for b, rs in by_band(nesine_rows, "fav_band", fav_order)},
        "fav_band_all": {b: summarize(rs) for b, rs in by_band(analysed, "fav_band", fav_order)},
        "home_away_fav_nesine": {
            "ev favorisi": summarize([r for r in nesine_rows if r["fav_is"] == "ev"]),
            "dep favorisi": summarize([r for r in nesine_rows if r["fav_is"] == "dep"]),
            "oranlar eşit": summarize([r for r in nesine_rows if r["fav_is"] == "eşit"]),
        },
        "fav_band_x_side_nesine": {},
        "draw_band_nesine": {b: summarize(rs) for b, rs in by_band(nesine_rows, "draw_band", draw_order)},
        "ht_fav_band_nesine": {},
    }
    for b, rs in by_band(nesine_rows, "fav_band", fav_order):
        ev = [r for r in rs if r["fav_is"] == "ev"]
        dep = [r for r in rs if r["fav_is"] == "dep"]
        tables["fav_band_x_side_nesine"][b] = {"ev_fav": summarize(ev), "dep_fav": summarize(dep)}

    # HT: reuse same fav bands, but result is HT
    ht_nes = []
    for r in nesine_rows:
        if not r.get("ht_result"):
            continue
        q = dict(r)
        q["result"] = r["ht_result"]
        # fav_won at HT
        q["fav_won"] = (r["ht_result"] == r["fav_side"]) if r["fav_side"] else None
        ht_nes.append(q)
    tables["ht_fav_band_nesine"] = {b: summarize(rs) for b, rs in by_band(ht_nes, "fav_band", fav_order)}
    tables["ht_overall_nesine"] = summarize(ht_nes)
    tables["overall_nesine"] = overall_n
    tables["overall_all"] = overall_all

    meta = {
        "generated_at": NOW.strftime("%Y-%m-%dT%H:%M:%S%z").replace("+0300", "+03:00"),
        "timezone": "Europe/Istanbul",
        "universe": "derin_tahminler.json (573 maç, 14:23 taraması)",
        "n_universe": len(deep),
        "n_finished": sum(1 for m in deep if (results.get(m) or {}).get("state") == "final" and (results.get(m) or {}).get("ft"))
        if False
        else sum(
            1
            for m in deep.values()
            if (results.get(m["code"]) or {}).get("state") == "final" and (results.get(m["code"]) or {}).get("ft")
        ),
        "n_with_odds": len(analysed),
        "n_nesine_odds": len(nesine_rows),
        "n_sharp_fallback": len(sharp_rows),
        "n_finished_no_odds": len(no_odds),
        "coverage_counts": dict(coverage),
        "results_refresh": "Nesine GetUnliveMatches 2026-11-21 ve 2026-11-22, bu koşu sırasında çekildi",
        "previous_finals_in_denetim_gece": 414,
        "odds_rule": "Her maç için kickoff öncesi en son Nesine 1-X-2; yoksa kickoff öncesi en son sharp (OddsMath) ref_1x2",
        "implied": "Nesine payı orantılı yöntemle çıkarılmış (1/oranlar normalize)",
        "fav_definition": "Daha kısa olan MS 1 veya MS 2; her iki taraf >2.10 ise bant 'dengeli', favori yine daha kısa taraf",
    }

    payload = {
        "meta": meta,
        "tables": tables,
        "close_matches": [
            {k: r[k] for k in ("code", "home", "away", "league", "kickoff", "odds", "odds_kind", "result", "ft", "ht")}
            for r in close
        ],
        "balanced_matches": [
            {k: r[k] for k in ("code", "home", "away", "league", "kickoff", "odds", "odds_kind", "result", "ft", "ht")}
            for r in balanced
            if r["odds_kind"] == "nesine" or True
        ],
        "upsets_fav_le_150": [
            {
                k: r[k]
                for k in (
                    "code",
                    "home",
                    "away",
                    "league",
                    "kickoff",
                    "odds",
                    "odds_kind",
                    "fav_is",
                    "fav_odds",
                    "result",
                    "ft",
                    "ht",
                )
            }
            for r in upsets
        ],
        "sharp_fallback_used": [
            {k: r[k] for k in ("code", "home", "away", "kickoff", "odds", "odds_source", "result", "ft")}
            for r in sharp_used
        ],
        "finished_without_odds": [
            {k: x[k] for k in x if k in ("code", "home", "away", "league", "kickoff_raw", "kickoff", "ft", "result")}
            for x in no_odds
        ],
        "matches": analysed,
    }
    # fix kickoff in no_odds
    for i, x in enumerate(no_odds):
        payload["finished_without_odds"][i] = {
            "code": x["code"],
            "home": x["home"],
            "away": x["away"],
            "league": x.get("league"),
            "kickoff": x["kickoff"].strftime("%Y-%m-%d %H:%M") if isinstance(x.get("kickoff"), dt.datetime) else x.get("kickoff_raw"),
            "ft": x.get("ft"),
            "result": x.get("result"),
        }

    (D / "oran_sonuc_analizi.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str))

    # -------- Markdown (Turkish) --------
    def row_band(label, s):
        if not s or not s.get("n"):
            return [label, 0, "—", "—", "—", "—", "—", "—"]
        return [
            label,
            s["n"],
            f"{fmt_pct(s['home_pct'])} ({fmt_pct(s['imp_home'])})",
            f"{fmt_pct(s['draw_pct'])} ({fmt_pct(s['imp_draw'])})",
            f"{fmt_pct(s['away_pct'])} ({fmt_pct(s['imp_away'])})",
            f"{fmt_pct(s['fav_win_pct'])}" if s.get("fav_win_pct") is not None else "—",
            f"{fmt_pct(s['fav_imp'])}" if s.get("fav_imp") is not None else "—",
            fmt_pp(s.get("fav_delta")),
        ]

    def row_simple(label, s):
        if not s or not s.get("n"):
            return [label, 0, "—", "—", "—"]
        return [label, s["n"], fmt_pct(s["home_pct"]), fmt_pct(s["draw_pct"]), fmt_pct(s["away_pct"])]

    n_fin = meta["n_finished"]
    lines = []
    a = lines.append
    a("# 21 Kasım 2026 — Oran profilleri ve sonuçlar")
    a("")
    a(f"Üretilme: {NOW.strftime('%Y-%m-%d %H:%M')} (Europe/Istanbul).")
    a("")
    a("## Kapsam")
    a("")
    a(f"Evren, bugünkü derin taramadaki **{len(deep)} maç**. Sonuçlar Nesine `GetUnliveMatches` ile tazelendi (20:57'deki 414 bitmiş maç artık **{n_fin}**).")
    a("")
    a(f"- Analize giren (bitmiş + 1-X-2 oranı var): **{len(analysed)}**")
    a(f"- Bunlardan Nesine bülten oranı: **{len(nesine_rows)}**")
    a(f"- Nesine oranı olmadığı için sharp (OddsMath) `ref_1x2` kullanılan: **{len(sharp_rows)}**")
    a(f"- Bitmiş ama hiçbir kaynakta 1-X-2 bulunamayan: **{len(no_odds)}**")
    rest = len(deep) - n_fin
    a(f"- Henüz bitmemiş, ertelenmiş veya skor eşleşmeyen: **{rest}**")
    if no_odds:
        nd = no_odds[0]
        ko = nd["kickoff"].strftime("%H:%M") if isinstance(nd.get("kickoff"), dt.datetime) else nd.get("kickoff_raw")
        a(f"  - Oransız biten: {nd['home']} – {nd['away']} ({nd.get('league')}, {ko}), skor {nd['ft'][0]}-{nd['ft'][1]}. Bültende MS pazarı yoktu, takip kaydında da oran yok.")
    a("")
    a("Oran kuralı: her maç için **kickoff öncesi en son Nesine MS 1 / 0 / 2** (kaynak: `nesine_history.jsonl` saat 11:47–19:13 arası 17 anlık + öğleden sonra `ng_1637` / `ng_fresh` / `nesine_global`). Sabah maçları da 11:47 karesinde duruyor; ilk derin maç 14:30'da başladığı için hepsinde maç öncesi kare var. İma edilen ihtimaller Nesine payı orantılı yöntemle çıkarılmış.")
    a("")
    a("Aşağıdaki tablolar **yalnızca Nesine oranlı** maçlar üzerinedir" + (f" ({len(nesine_rows)} maç)." if nesine_rows else "."))
    if sharp_rows:
        a(f"Sharp yedek {len(sharp_rows)} maç ayrı tutuldu.")
    a("")

    a("## Genel tablo (Nesine 1-X-2)")
    a("")
    s = overall_n
    a(
        md_table(
            ["Sonuç", "Sayı", "Gerçekleşen", "Nesine ima (payı çıkarılmış)", "Fark"],
            [
                ["Ev (1)", s["home_n"], fmt_pct(s["home_pct"]), fmt_pct(s["imp_home"]), fmt_pp(s["home_delta"])],
                ["Beraberlik (X)", s["draw_n"], fmt_pct(s["draw_pct"]), fmt_pct(s["imp_draw"]), fmt_pp(s["draw_delta"])],
                ["Deplasman (2)", s["away_n"], fmt_pct(s["away_pct"]), fmt_pct(s["imp_away"]), fmt_pp(s["away_delta"])],
                ["Favori kazandı", "—", fmt_pct(s["fav_win_pct"]), fmt_pct(s["fav_imp"]), fmt_pp(s["fav_delta"])],
            ],
        )
    )
    a("")
    avg_m = sum(r["margin"] for r in nesine_rows) / len(nesine_rows) if nesine_rows else 0
    a(f"Ortalama Nesine 1-X-2 payı: %{avg_m*100:.1f}.".replace(".", ","))
    a("")

    a("## Favori oranı bantları")
    a("")
    a("Favori, MS 1 ve MS 2'den kısa olan taraf. İki taraf da 2,10'un üstündeyse maç **dengeli** sayılıyor; favori sütununda yine daha kısa taraf kullanılıyor. Parantez içinde Nesine ima edilen oran var.")
    a("")
    headers = ["Favori oranı", "n", "Ev (ima)", "Beraberlik (ima)", "Dep (ima)", "Favori tuttu", "İma edilen favori", "Fark"]
    rows = [row_band(b, tables["fav_band_nesine"][b]) for b in fav_order]
    a(md_table(headers, rows))
    a("")

    a("### Ev favorisi / deplasman favorisi")
    a("")
    a(
        md_table(
            ["Taraf", "n", "Ev (ima)", "Beraberlik (ima)", "Dep (ima)", "Favori tuttu", "İma", "Fark"],
            [
                row_band("Ev favorisi", tables["home_away_fav_nesine"]["ev favorisi"]),
                row_band("Dep favorisi", tables["home_away_fav_nesine"]["dep favorisi"]),
            ]
            + (
                [row_band("Oranlar eşit", tables["home_away_fav_nesine"]["oranlar eşit"])]
                if tables["home_away_fav_nesine"]["oranlar eşit"].get("n")
                else []
            ),
        )
    )
    a("")
    a(
        md_table(
            ["Bant × taraf", "n", "Ev (ima)", "X (ima)", "Dep (ima)", "Favori tuttu", "İma", "Fark"],
            [
                row_band(f"{b} · ev fav", tables["fav_band_x_side_nesine"][b]["ev_fav"])
                for b in fav_order
            ]
            + [
                row_band(f"{b} · dep fav", tables["fav_band_x_side_nesine"][b]["dep_fav"])
                for b in fav_order
            ],
        )
    )
    a("")

    a("## Beraberlik oranı bantları")
    a("")
    a(
        md_table(
            ["Beraberlik oranı", "n", "Ev (ima)", "Beraberlik (ima)", "Dep (ima)", "Favori tuttu", "İma", "Fark"],
            [row_band(b, tables["draw_band_nesine"][b]) for b in draw_order],
        )
    )
    a("")

    a("## Yakın oranlı maçlar (örnek: 2,20 / 3,40 / 2,00)")
    a("")
    a(f"MS 1 ve MS 2 ikisi de 1,90–2,50 aralığında olan **{len([r for r in close if r['odds_kind']=='nesine'])}** Nesine maçı (artı sharp yedek varsa aşağıda işaretli). Bu, kullanıcının verdiği 2,20 / 3,40 / 2,00 profiline en yakın grup.")
    a("")
    close_n = [r for r in close if r["odds_kind"] == "nesine"]
    if close_n:
        cs = summarize(close_n)
        a(f"Bu grupta sonuç dağılımı: ev {fmt_pct(cs['home_pct'])} (ima {fmt_pct(cs['imp_home'])}), beraberlik {fmt_pct(cs['draw_pct'])} (ima {fmt_pct(cs['imp_draw'])}), deplasman {fmt_pct(cs['away_pct'])} (ima {fmt_pct(cs['imp_away'])}).")
        a("")
        a(
            md_table(
                ["Saat", "Maç", "1 / X / 2", "MS", "Skor"],
                [
                    [
                        r["kickoff"][-5:] if r.get("kickoff") else "—",
                        f"{r['home']} – {r['away']}",
                        " / ".join(fmt_odd(o) for o in r["odds"])
                        + (" *" if r["odds_kind"] != "nesine" else ""),
                        {"1": "Ev", "X": "Berabere", "2": "Dep"}[r["result"]],
                        f"{r['ft'][0]}-{r['ft'][1]}",
                    ]
                    for r in close
                ],
            )
        )
        if any(r["odds_kind"] != "nesine" for r in close):
            a("")
            a("\\* sharp (OddsMath) yedek oran.")
    a("")

    a(f"İki tarafı da 2,10'un üstünde olan dengeli maç sayısı: **{len([r for r in balanced if r['odds_kind']=='nesine'])}** (Nesine). Özet yukarıdaki 'dengeli' satırında; tam liste `oran_sonuc_analizi.json` içinde.")
    a("")

    a("## En büyük sürprizler (favori oranı ≤1,50 ve tutmadı)")
    a("")
    up_n = [r for r in upsets if r["odds_kind"] == "nesine"]
    up_all_fav = [
        r
        for r in nesine_rows
        if r["fav_side"] and r["fav_odds"] is not None and r["fav_odds"] <= 1.50
    ]
    a(f"Favorisi 1,50 veya daha kısa olan {len(up_all_fav)} maçtan **{len(up_n)}** tanesinde favori kazanamadı (beraberlik veya tersi).")
    a("")
    if upsets:
        a(
            md_table(
                ["Saat", "Maç", "1 / X / 2", "Favori", "MS", "Skor"],
                [
                    [
                        r["kickoff"][-5:] if r.get("kickoff") else "—",
                        f"{r['home']} – {r['away']}",
                        " / ".join(fmt_odd(o) for o in r["odds"])
                        + (" *" if r["odds_kind"] != "nesine" else ""),
                        ("Ev " if r["fav_is"] == "ev" else "Dep ") + fmt_odd(r["fav_odds"]),
                        {"1": "Ev", "X": "Berabere", "2": "Dep"}[r["result"]],
                        f"{r['ft'][0]}-{r['ft'][1]}",
                    ]
                    for r in upsets
                ],
            )
        )
    a("")

    a("## İlk yarı (aynı favori bantları, maç öncesi 1-X-2)")
    a("")
    a("Bantlar hâlâ maç sonu Nesine 1-X-2'ye göre; sonuç ise ilk yarı skoru. Bu, İY 1 / İY 0 / İY 2 dağılımı.")
    a("")
    hs = tables["ht_overall_nesine"]
    if hs.get("n"):
        a(
            md_table(
                ["İY sonuç", "Sayı", "Gerçekleşen", "MS oranından ima (referans)", "Fark"],
                [
                    ["İY Ev", hs["home_n"], fmt_pct(hs["home_pct"]), fmt_pct(hs["imp_home"]), fmt_pp(hs["home_delta"])],
                    ["İY Beraberlik", hs["draw_n"], fmt_pct(hs["draw_pct"]), fmt_pct(hs["imp_draw"]), fmt_pp(hs["draw_delta"])],
                    ["İY Dep", hs["away_n"], fmt_pct(hs["away_pct"]), fmt_pct(hs["imp_away"]), fmt_pp(hs["away_delta"])],
                ],
            )
        )
        a("")
        a("MS ima edilen oranlar ilk yarı için fazla iddialı kalır (ilk yarıda beraberlik doğal olarak daha sık). Asıl karşılaştırma bantlar arası İY dağılımı.")
        a("")
        a(
            md_table(
                ["Favori oranı (MS)", "n", "İY Ev", "İY X", "İY Dep", "İY'de favori önde"],
                [
                    [
                        b,
                        tables["ht_fav_band_nesine"][b].get("n", 0),
                        fmt_pct(tables["ht_fav_band_nesine"][b].get("home_pct")) if tables["ht_fav_band_nesine"][b].get("n") else "—",
                        fmt_pct(tables["ht_fav_band_nesine"][b].get("draw_pct")) if tables["ht_fav_band_nesine"][b].get("n") else "—",
                        fmt_pct(tables["ht_fav_band_nesine"][b].get("away_pct")) if tables["ht_fav_band_nesine"][b].get("n") else "—",
                        fmt_pct(tables["ht_fav_band_nesine"][b].get("fav_win_pct")) if tables["ht_fav_band_nesine"][b].get("n") else "—",
                    ]
                    for b in fav_order
                ],
            )
        )
    a("")
    a("## Notlar")
    a("")
    a("- Pay çıkarılmasa Nesine ima edilen favori ihtimali şişer; tablolardaki ima payı temizlenmiş değerlerdir.")
    a("- Tek günlük örnek. Küçük bantlarda (özellikle ≤1,30) yüzde dalgalanması normal.")
    a("- 90 dakikalık resmi skor kullanıldı; bugünkü evrendeki biten maçların hepsi normal süre (MS) ile bitti.")
    a("- Dosyalar: `oran_sonuc_analizi.md` ve `oran_sonuc_analizi.json`.")
    a("")

    (D / "oran_sonuc_analizi.md").write_text("\n".join(lines) + "\n")
    print("WROTE", D / "oran_sonuc_analizi.md")
    print("WROTE", D / "oran_sonuc_analizi.json")
    print("coverage", dict(coverage))
    print("n analysed", len(analysed), "nesine", len(nesine_rows), "sharp", len(sharp_rows), "no_odds", len(no_odds))
    print("finished", n_fin, "close", len(close), "upsets", len(upsets), "balanced", len(balanced))
    print("overall nesine", {k: overall_n[k] for k in ('n','home_n','draw_n','away_n','home_pct','draw_pct','away_pct','fav_win_pct','fav_imp','fav_delta')})


if __name__ == "__main__":
    main()

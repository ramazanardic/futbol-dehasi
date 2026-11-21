"""Sonuç defteri: oynanan kuponları kaydet, biten maçları notla, notlanan bacakları kalıcı deftere ekle.

    python scripts/sonuc_defteri.py kaydet --dosya tahminler/<ai>/<gün>/kupon_5x_1930.json --id A5 --tutar 100
    python scripts/sonuc_defteri.py kaydet --dosya ... --id K2000 --tutar 300 --oran 7.21 --oranlar 3319685=1.69
    python scripts/sonuc_defteri.py notla                # açık kuponların bacaklarını FotMob sonucuyla notla
    python scripts/sonuc_defteri.py ozet                 # defterden kalibrasyon: aile aile tahmin vs gerçekleşen

21 Kasım denetiminin (denetim_topla / denetim_rapor) genelleştirilmiş, repodaki hali. Dosyalar yalnız bu yapay
zekânın klasöründe (``QUANTFOOT_AI``): ``oynanan_kuponlar.json`` (kayıt — kupon modlarının açık maç maruziyeti de
buradan okunur) ve ``defter/bacaklar.csv`` (her sonuçlanan bacak bir kez; kalibrasyon zamanla bununla iyileşir).
Sonuç uydurulmaz: eşleşmeyen maç "eşleşmedi", bitmeyen "bekliyor" kalır. API-Football kullanılmaz.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantfoot.evaluation.leg_grading import decide, fetch_result, market_family  # noqa: E402
from quantfoot.paths import ai_area  # noqa: E402
from quantfoot.strategy import kupon_modu as KM  # noqa: E402

TSI = dt.timezone(dt.timedelta(hours=3))
LEDGER_COLS = ["graded_at", "date", "coupon_id", "mode", "code", "match", "league", "ko", "market", "sel", "name",
               "family", "odds", "p", "p_market", "live", "won", "ht", "ft"]
BUCKETS = (0.0, 0.40, 0.55, 0.65, 0.75, 0.85, 1.01)


def ledger_path(area: Path) -> Path:
    return Path(area) / "defter" / "bacaklar.csv"


def read_ledger(area: Path) -> list[dict]:
    f = ledger_path(area)
    if not f.exists():
        return []
    with f.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def append_ledger(area: Path, rows: list[dict]) -> int:
    """Yeni sonuçlanan bacakları ekle; (kupon, maç, seçim) zaten defterdeyse tekrar yazma. Eklenen satır sayısı."""
    f = ledger_path(area)
    f.parent.mkdir(parents=True, exist_ok=True)
    have = {(r["coupon_id"], str(r["code"]), r["name"]) for r in read_ledger(area)}
    new = [r for r in rows if (r["coupon_id"], str(r["code"]), r["name"]) not in have]
    if not new:
        return 0
    write_header = not f.exists()
    with f.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=LEDGER_COLS, extrasaction="ignore")
        if write_header:
            w.writeheader()
        w.writerows(new)
    return len(new)


# ------------------------------------------------------------------------------------------------ kaydet

def legs_from_file(path: Path, index: int = 0) -> list[dict]:
    """Bilinen kupon dosyası biçimleri: {"legs": [...]}, {"coupons": [{"legs": [...]}]} (nesine_kupon)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data.get("legs"), list):
        legs = data["legs"]
    elif isinstance(data.get("coupons"), list) and data["coupons"]:
        legs = data["coupons"][index]["legs"]
    else:
        raise ValueError(f"{path}: bacak listesi bulunamadı")
    out = []
    for leg in legs:
        ko = leg.get("ko") or leg.get("kickoff") or ""
        out.append({"code": leg.get("code"), "match": leg.get("match"), "home": leg.get("home"), "away": leg.get("away"),
                    "league": leg.get("league"), "ko": str(ko)[:16], "market": leg.get("market"),
                    "sel": leg.get("sel") or leg.get("selection"), "name": leg.get("name") or leg.get("selection"),
                    "odds": float(leg["odds"]), "p": float(leg.get("p") or leg.get("probability") or 0),
                    "p_market": leg.get("p_market") or leg.get("market_prob"), "live": bool(leg.get("live"))})
    return out


def cmd_kaydet(args: argparse.Namespace, area: Path) -> None:
    legs = legs_from_file(args.dosya, args.kupon_no - 1)
    for item in args.oranlar or []:
        code, o = item.split("=", 1)
        for leg in legs:
            if str(leg["code"]) == code.strip():
                leg["odds"] = float(o)
    res = KM.guard_legs(legs, args.mod if args.mod in KM.MODES else "banko", at_selection=False)
    c = KM.register_placed(area, {"id": args.id, "date": args.tarih, "placed_at": dt.datetime.now(TSI).isoformat(timespec="minutes"),
                                  "stake": args.tutar, "odds": args.oran or round(math.prod(l["odds"] for l in legs), 2),
                                  "mode": args.mod, "source": str(args.dosya), "legs": legs,
                                  "guard_ok": res.ok, "guard_errors": res.errors})
    print(f"{c['id']} kaydedildi: {len(legs)} maç, oran {c['odds']:.2f}, {c['stake']:g} TL · {KM.honest_line(res, c['stake'])}")
    if not res.ok:
        print("⚠ Bu kupon kurallara uymuyor: " + "; ".join(res.errors))


# ------------------------------------------------------------------------------------------------ notla

def coupon_status(legs: list[dict]) -> str:
    st = [leg.get("won") for leg in legs]
    if any(x is False for x in st):
        return "kaybetti"
    if st and all(x is True for x in st):
        return "kazandı"
    return "açık"


def grade_coupons(coupons: list[dict], results: dict) -> list[dict]:
    """Kayıttaki açık bacakları ``results`` (kod → FotMob sonucu) ile notla; yeni sonuçlanan defter satırlarını döndür."""
    now = dt.datetime.now(TSI).isoformat(timespec="minutes")
    rows = []
    for c in coupons:
        for leg in c.get("legs") or []:
            if leg.get("won") is not None:
                continue
            r = results.get(leg.get("code")) or results.get(str(leg.get("code")))
            if not r:
                continue
            w = decide(leg, r)
            leg["state"] = r.get("state")
            if w is None:
                continue
            leg.update(won=w, ht=r.get("ht"), ft=r.get("ft"))
            rows.append({"graded_at": now, "date": c.get("date") or str(leg.get("ko", ""))[:10], "coupon_id": c["id"],
                         "mode": c.get("mode", ""), "code": leg.get("code"), "match": leg.get("match"),
                         "league": leg.get("league"), "ko": leg.get("ko"), "market": leg.get("market"), "sel": leg.get("sel"),
                         "name": leg.get("name") or leg.get("sel"), "family": market_family(leg), "odds": leg.get("odds"),
                         "p": leg.get("p"), "p_market": leg.get("p_market"), "live": bool(leg.get("live")),
                         "won": int(bool(w)), "ht": json.dumps(r.get("ht")), "ft": json.dumps(r.get("ft"))})
        c["status"] = coupon_status(c.get("legs") or [])
    return rows


def summary_lines(coupons: list[dict]) -> list[str]:
    out, staked, back, open_stake = [], 0.0, 0.0, 0.0
    for c in coupons:
        legs = c.get("legs") or []
        s = c.get("status") or "açık"
        won = sum(1 for leg in legs if leg.get("won") is True)
        lost = sum(1 for leg in legs if leg.get("won") is False)
        p = math.prod(float(leg.get("p") or 0) for leg in legs)
        staked += float(c.get("stake") or 0)
        if s == "kazandı":
            back += float(c["stake"]) * float(c["odds"])
        elif s == "açık":
            open_stake += float(c.get("stake") or 0)
        out.append(f"- {c['id']} ({c.get('mode') or '-'}, {c.get('stake')} TL @ {float(c.get('odds') or 0):.2f}): {s.upper()} — "
                   f"{won} tuttu, {lost} yattı, {len(legs) - won - lost} bekliyor; kurulurken tutma ihtimali %{100 * p:.1f}")
    settled = staked - open_stake
    out.append(f"Toplam yatırılan {staked:.0f} TL; sonuçlanan {settled:.0f} TL → geri dönen {back:.2f} TL "
               f"(net {back - settled:+.2f} TL); açıkta {open_stake:.0f} TL.")
    return out


def cmd_notla(args: argparse.Namespace, area: Path) -> None:
    from quantfoot.data.fotmob import FotMob, parse_matches
    from quantfoot.data.match_dossier import CachedHttp
    coupons = KM.load_placed(area)
    todo = [c for c in coupons if c.get("status") in KM.OPEN_STATES]
    if not todo:
        print("Açık kupon yok.")
        print("\n".join(summary_lines(coupons)))
        return
    days = sorted({str(leg.get("ko", ""))[:10] for c in todo for leg in c["legs"] if leg.get("won") is None and leg.get("ko")})
    fm = FotMob(CachedHttp(area / "defter" / "fotmob_cache"), delay_s=0.7)
    fm_list: list[dict] = []
    seen_days = set()
    for d in days:
        for day in (dt.date.fromisoformat(d), dt.date.fromisoformat(d) + dt.timedelta(days=1)):
            if day not in seen_days and day <= dt.date.today() + dt.timedelta(days=1):
                seen_days.add(day)
                fm_list += parse_matches(fm.matches_on(day, ttl_s=600) or {})
    overrides = {int(k): v for k, v in (json.loads(args.eslesme) if args.eslesme else {}).items()}
    cache: dict = {}
    results = {}
    for c in todo:
        for leg in c["legs"]:
            if leg.get("won") is None:
                results[leg["code"]] = fetch_result(leg, fm, fm_list, overrides, cache)
    rows = grade_coupons(todo, results)
    KM.save_placed(area, coupons)
    n = append_ledger(area, rows)
    unmatched = sorted({leg.get("match") for c in todo for leg in c["legs"] if (results.get(leg["code"]) or {}).get("state") == "eşleşmedi"})
    print(f"{len(rows)} bacak sonuçlandı, deftere {n} yeni satır ({ledger_path(area).relative_to(ROOT) if ledger_path(area).is_relative_to(ROOT) else ledger_path(area)}).")
    if unmatched:
        print("FotMob'da eşleşmeyen: " + ", ".join(str(x) for x in unmatched) + " (--eslesme '{\"<kod>\": <fotmob id>}' ile verilebilir)")
    print("\n".join(summary_lines(coupons)))


# ------------------------------------------------------------------------------------------------ özet

def calibration_report(rows: list[dict]) -> list[str]:
    def stats(rs):
        n = len(rs)
        if not n:
            return None
        ps = [min(max(float(r["p"]), 1e-4), 1 - 1e-4) for r in rs]
        ys = [int(r["won"]) for r in rs]
        brier = sum((p - y) ** 2 for p, y in zip(ps, ys)) / n
        ll = -sum(y * math.log(p) + (1 - y) * math.log(1 - p) for p, y in zip(ps, ys)) / n
        return n, sum(ps) / n, sum(ys) / n, brier, ll
    rows = [r for r in rows if r.get("p") not in (None, "", "None") and r.get("won") not in (None, "")]
    out = ["| Grup | n | Ort. tahmin | Gerçekleşen | Brier | Log-loss |", "|---|---|---|---|---|---|"]
    groups: dict[str, list] = defaultdict(list)
    for r in rows:
        groups["tümü"].append(r)
        groups[f"aile: {r.get('family') or '?'}"].append(r)
        groups[f"mod: {r.get('mode') or '?'}"].append(r)
        p = float(r["p"])
        b = next(f"{lo:.2f}–{hi:.2f}" for lo, hi in zip(BUCKETS, BUCKETS[1:]) if lo <= p < hi)
        groups[f"bant: {b}"].append(r)
    for k in sorted(groups, key=lambda x: (x != "tümü", x)):
        s = stats(groups[k])
        if s:
            out.append(f"| {k} | {s[0]} | %{100 * s[1]:.1f} | %{100 * s[2]:.1f} | {s[3]:.4f} | {s[4]:.4f} |")
    if rows and len(rows) < 200:
        out.append("")
        out.append(f"Not: {len(rows)} bacak az — kalibrasyon kararları için en az ~200 sonuçlanmış bacak gerekir; "
                   "o zamana kadar olasılıklar keskin piyasaya yaslanır (data/calibration/blend_weights.json).")
    return out


def cmd_ozet(args: argparse.Namespace, area: Path) -> None:
    rows = read_ledger(area)
    if not rows:
        print("Defter boş (önce: sonuc_defteri.py notla).")
        return
    print("\n".join(calibration_report(rows)))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="komut", required=True)
    k = sub.add_parser("kaydet", help="oynanan kuponu kayda ekle")
    k.add_argument("--dosya", type=Path, required=True)
    k.add_argument("--kupon-no", type=int, default=1)
    k.add_argument("--id", required=True)
    k.add_argument("--tutar", type=float, required=True)
    k.add_argument("--oran", type=float, default=None, help="oynanırken toplam oran (varsayılan: bacak çarpımı)")
    k.add_argument("--oranlar", nargs="*", help="oynanırken değişen bacak oranları: <kod>=<oran>")
    k.add_argument("--mod", default="banko", help="banko / risk / canli / eski")
    k.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    n = sub.add_parser("notla", help="açık kuponları FotMob sonucuyla notla ve deftere ekle")
    n.add_argument("--eslesme", default=None, help="elle eşleşme JSON: {\"<nesine kodu>\": <fotmob id>}")
    sub.add_parser("ozet", help="defterden kalibrasyon raporu")
    args = ap.parse_args(argv)
    area = ai_area()
    {"kaydet": cmd_kaydet, "notla": cmd_notla, "ozet": cmd_ozet}[args.komut](args, area)


if __name__ == "__main__":
    main()

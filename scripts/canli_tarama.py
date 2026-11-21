"""Canlı fırsat tarayıcı — Nesine canlı oranı, canlı gol modelinin adil fiyatını geçiyor mu?

    QUANTFOOT_AI=grokbottahmin python scripts/canli_tarama.py --bir-kez --canli-rezerv 100
    QUANTFOOT_AI=grokbottahmin python scripts/canli_tarama.py --aralik 300 --sure 120    # 2 saat, 5 dk'da bir

ASLA bahis yapmaz. API-Football KULLANMAZ. Kaynaklar: Nesine canlı + maç öncesi bülten (okuma),
ESPN scoreboard/summary (dakika, skor, kırmızı kart, şut, isabetli şut, korner). Çıktı:
tahminler/<QUANTFOOT_AI>/canli/<tarih>.jsonl (+ .md satırları), tekrar engeli: canli/durum.json.
Hiç fırsat yoksa tek satır: "Fırsat yok".
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot import settings as S  # noqa: E402
from quantfoot.data import fotmob as fmb  # noqa: E402
from quantfoot.data import live_scan as ls  # noqa: E402
from quantfoot.data.match_dossier import CachedHttp  # noqa: E402
from quantfoot.paths import ai_area  # noqa: E402

UA = {"User-Agent": "QuantFoot-GrokBot/1.0 (kisisel arastirma; okuma)", "Accept": "application/json"}
PRE_REFRESH_S = 30 * 60


def _get(url: str, params: dict | None = None, timeout: float = 12.0) -> dict | None:
    try:
        r = requests.get(url, params=params, headers=UA, timeout=timeout)
        return r.json() if r.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None


def load_prematch(folder: Path, now: float, fetch=_get) -> dict[int, dict]:
    """Maç öncesi Nesine fiyatlarını önbellekte tut: başlayan maç bültenden düşse de son fiyatı kalır."""
    f = folder / "on_bulten.json"
    data = json.loads(f.read_text()) if f.exists() else {"t": 0, "events": {}}
    if now - data.get("t", 0) > PRE_REFRESH_S:
        payload = fetch(ls.NESINE_PRE_URL, None, 25.0)
        if payload:
            fresh = ls.parse_nesine_prematch(payload)
            ev = {int(k): v for k, v in data["events"].items()}
            ev.update(fresh)
            cutoff = (now - 36 * 3600) * 1000
            ev = {k: v for k, v in ev.items() if (v.get("kickoff_ms") or 0) >= cutoff}
            data = {"t": now, "events": {str(k): v for k, v in ev.items()}}
            f.write_text(json.dumps(data, ensure_ascii=False))
    return {int(k): v for k, v in data["events"].items()}


def annotate_banko(ops: list[dict]) -> None:
    """Canlı fırsatı banko bacak kuralıyla işaretle (kupona girecekse): piyasa P'si zorunlu, P ≥ %65 (piyasanın en çok
    +5 puan üstü), oran 1.20–1.80. Canlı model doğrulanmadığı için kupon kararında yalnız ``banko_ok`` olanlar kullanılır."""
    from quantfoot.strategy import banko_guard as bg
    from quantfoot.strategy import kupon_modu as KM
    cfg = KM.policy("banko").guard
    for o in ops:
        leg = bg.BankoLeg(match_id=str(o.get("code")), label=f"{o.get('match')} {o.get('market')}",
                          odds=float(o.get("nesine_odds") or 0), p=float(o.get("fair_prob") or 0), live=True,
                          p_market=o.get("market_prob"))
        err, _ = bg.check_leg(leg, cfg, at_selection=True)
        o["banko_ok"] = not err
        o["banko_errors"] = err


def scan_once(args: argparse.Namespace, folder: Path, fetch=_get, now: dt.datetime | None = None,
              fotmob: "fmb.FotMob | None" = None) -> tuple[list[dict], dict]:
    now = now or dt.datetime.now(S.TSI)
    stats = {"nesine_live": 0, "espn_live": 0, "fotmob_live": 0, "matched": 0, "priced": 0, "opportunities": 0, "new": 0}
    live = fetch(ls.NESINE_LIVE_URL, None, 15.0)
    if not live:
        stats["error"] = "Nesine canlı bülten okunamadı"
        return [], stats
    nes = [e for e in ls.parse_nesine_live(live) if e["markets"]]
    stats["nesine_live"] = len(nes)
    espn = ls.parse_espn_scoreboard(fetch(ls.ESPN_SCOREBOARD, None, 15.0) or {})
    stats["espn_live"] = len(espn)
    pre = load_prematch(folder, now.timestamp(), fetch)
    fm_live: list[dict] | None = None
    detail_calls = 0
    ops: list[dict] = []
    for e in nes:
        lv = ls.match_live(e, espn)
        if not lv and fotmob is not None:
            if fm_live is None:
                fm_live = fmb.parse_matches(fotmob.matches_on(now.date(), ttl_s=60) or {}, live_only=True)
                stats["fotmob_live"] = len(fm_live)
            m = fmb.find_match(fm_live, e["home"] or "", e["away"] or "")
            if m:
                lv = {"fotmob": m}
        if not lv:
            continue
        stats["matched"] += 1
        pm = ls.match_prematch(e, pre)
        lam = ls.prematch_lambdas(pm, lv.get("espn_odds"))
        if not lam:
            continue
        if "fotmob" in lv:
            det = None
            if detail_calls < args.fotmob_detay:
                det = fotmob.details(lv["fotmob"]["id"], ttl_s=240)
                detail_calls += 1
            lv = ls.live_from_fotmob(lv["fotmob"], det)
            st = lv["stats"]
        else:
            summ = fetch(ls.ESPN_SUMMARY, {"event": lv["event_id"]}, 10.0)
            st = ls.parse_espn_summary(summ or {}, lv["home_id"], lv["away_id"])
        stats["priced"] += 1
        ops += ls.evaluate(e, lv, lam, st, min_ev=args.min_ev, reserve=args.canli_rezerv,
                           kelly_mult=S.KELLY_MULTIPLIER, cap_frac=args.kupon_limit_oran,
                           step=S.STAKE_STEP_TL, min_stake=S.MIN_STAKE_TL)
    annotate_banko(ops)
    stats["opportunities"] = len(ops)
    sf = folder / "durum.json"
    state = json.loads(sf.read_text()) if sf.exists() else {}
    fresh = ls.dedupe(ops, state, now)
    sf.write_text(json.dumps(state))
    stats["new"] = len(fresh)
    if fresh:
        day = now.strftime("%Y-%m-%d")
        with (folder / f"{day}.jsonl").open("a") as fh:
            for o in fresh:
                fh.write(json.dumps({**o, "t": now.isoformat()}, ensure_ascii=False) + "\n")
        with (folder / f"{day}.md").open("a") as fh:
            for o in fresh:
                fh.write(f"- {now:%H:%M} TSİ {ls.format_line(o)}\n")
    return fresh, stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bir-kez", action="store_true", help="tek tarama (zamanlayıcı için)")
    ap.add_argument("--aralik", type=int, default=300, help="döngü aralığı, saniye")
    ap.add_argument("--sure", type=int, default=120, help="döngü süresi, dakika")
    ap.add_argument("--min-ev", type=float, default=S.LIVE_MIN_EV)
    ap.add_argument("--canli-rezerv", type=float, default=None,
                    help="canlı için ayrılan kasa (TL); verilmezse canli/rezerv.json (kupon_politikasi.py yazar)")
    ap.add_argument("--kupon-limit-oran", type=float, default=S.STAKE_COUPON_FRAC, help="tek bahis en çok rezerv oranı")
    ap.add_argument("--fotmob-detay", type=int, default=8, help="tarama başına en çok FotMob maç ayrıntısı isteği")
    ap.add_argument("--ayrintili", action="store_true")
    args = ap.parse_args()
    folder = ai_area() / "canli"
    folder.mkdir(parents=True, exist_ok=True)
    if args.canli_rezerv is None:
        rf = folder / "rezerv.json"
        args.canli_rezerv = float(json.loads(rf.read_text()).get("canli_rezerv_tl", 0)) if rf.exists() else S.LIVE_RESERVE_TL
    end = time.time() + args.sure * 60
    while True:
        t0 = time.time()
        fm = fmb.FotMob(CachedHttp(folder / "onbellek"), delay_s=0.5) if fmb.enabled() else None
        fresh, stats = scan_once(args, folder, fotmob=fm)
        if stats.get("error"):
            print(f"Tarama yapılamadı: {stats['error']}")
        elif not fresh:
            print("Fırsat yok" + (f" (Nesine canlı {stats['nesine_live']}, eşleşen (ESPN/FotMob) {stats['matched']}, "
                                  f"fiyatlanan {stats['priced']})" if args.ayrintili else ""))
        else:
            for o in fresh:
                print(ls.format_line(o))
        if args.ayrintili:
            print(f"  süre {time.time() - t0:.1f} sn · {stats}")
        if args.bir_kez or time.time() + args.aralik > end:
            break
        time.sleep(args.aralik)


if __name__ == "__main__":
    main()

"""Çok günlük öz-geliştirme ve kalibrasyon denetçisi (yalnız aktif yapay zekânın kendi klasörünü okur).

AGENTS.md / GEMINI.md izolasyon kuralına sıkı biçimde uyar:
  * Yalnız ``tahminler/<QUANTFOOT_AI>/YYYY-MM-DD/`` altındaki kendi gün dosyalarını okur.
  * Başka hiçbir yapay zekânın klasörüne dokunmaz, listelemez, okumaz.

Her bitmiş maçtaki kupon bölgesi seçimleri (``oran >= 1.20`` ve ``P >= 0.60``) ile ana tahminleri
resmî Nesine sonuçlarıyla (``fetch_results`` + ``settle_selection``) çözer ve:
  1. Alt-pazar (exact selection name) bazında James-Stein büzüştürülmüş artık (``shrunk_residual``)
  2. Olasılık dilimleri (``%60-65``, ``%65-70``, ``%70-75``, ``%75-85``, ``%85+``)
  3. Fiyat kaynağı (doğrudan keskin piyasa vs türetilmiş model)
  4. Keskin borsa steam kırılımı (``steam yok`` vs ``orta 3–6p`` vs ``sert >=6p``)
  5. ``market_diagnosis`` v3 ayrıştırma başarımı (``REHAB`` vs ``OK`` vs ``TUZAK``)
  6. Zehirli alt-pazar alarmları ve altın havuz önerileri

çıktılarını ``oz_gelistirme_raporu.md`` ve ``oz_gelistirme_raporu.json`` olarak üretir.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import csv
import datetime as dt
import json
import math
from pathlib import Path
import re
from typing import Any

from quantfoot.data.nesine import fetch_results
from quantfoot.evaluation.auto_learn import market_family
from quantfoot.evaluation.settlement import settle_selection
from quantfoot.markets.market_diagnosis import canonical_name, diagnose_selection, parse_steam_pp

TSI = dt.timezone(dt.timedelta(hours=3))
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DEFAULT_PRIOR_N = 150.0
DEFAULT_MIN_N = 20
DEFAULT_MIN_P = 0.60
DEFAULT_MIN_ODDS = 1.20
PROB_BANDS = (
    (0.60, 0.65, "60-65%"),
    (0.65, 0.70, "65-70%"),
    (0.70, 0.75, "70-75%"),
    (0.75, 0.85, "75-85%"),
    (0.85, 1.01, "85-100%"),
)


def _flt(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        v = float(str(val).replace(",", "."))
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _shrink(raw_residual: float, n: int, prior_n: float = DEFAULT_PRIOR_N) -> float:
    if n <= 0:
        return 0.0
    return raw_residual * (n / (n + prior_n))


def _steam_pp(match: Mapping[str, Any]) -> float:
    return parse_steam_pp(match)


def _steam_bucket(pp: float) -> str:
    if pp >= 6.0:
        return "sert_steam (>=6p)"
    if pp >= 3.0:
        return "orta_steam (3-6p)"
    return "steam_yok (<3p)"


def _prob_band(p: float) -> str:
    for lo, hi, label in PROB_BANDS:
        if lo <= p < hi:
            return label
    return "<60%"


def _build_diag_ctx(match: Mapping[str, Any], sel: Mapping[str, Any]) -> dict[str, Any]:
    res = match.get("research") or {}
    tm = res.get("tm_absences") or {}
    ua = res.get("user_absences") or {}
    f1x2 = match.get("fair_1x2")
    mot_reg = res.get("motivation_regime") or {}
    dead_rubber = bool(mot_reg.get("dead_rubber"))
    if not dead_rubber and isinstance(res.get("motivation"), Mapping):
        from quantfoot.markets.lineup_xg import assess_motivation_risk
        dead_rubber = assess_motivation_risk(
            res["motivation"].get("home"),
            res["motivation"].get("away"),
        ).dead_rubber
    ref_prof = res.get("referee_profile")
    ref_card_z = (
        ref_prof.get("card_zscore")
        if isinstance(ref_prof, Mapping)
        else res.get("referee_card_zscore")
    )
    cons_disp = match.get("consensus_dispersion") or {}
    ctx: dict[str, Any] = {
        "mu_home": match.get("mu_home"),
        "mu_away": match.get("mu_away"),
        "fair_1x2": f1x2,
        "reference": match.get("reference"),
        "league": match.get("league"),
        "direct": bool(sel.get("direct")),
        "flags": res.get("flags") or match.get("flags") or [],
        "steam_1x2": match.get("steam_1x2"),
        "consensus_kl": cons_disp.get("max_kl_divergence") if isinstance(cons_disp, Mapping) else None,
        "home_gk1_out": bool((tm.get("home") or {}).get("gk1_out") or (ua.get("home") or {}).get("gk_out")),
        "away_gk1_out": bool((tm.get("away") or {}).get("gk1_out") or (ua.get("away") or {}).get("gk_out")),
        "home_top_scorer_out": bool((tm.get("home") or {}).get("top_scorer_out")),
        "away_top_scorer_out": bool((tm.get("away") or {}).get("top_scorer_out")),
        "dead_rubber": dead_rubber,
        "referee_card_zscore": ref_card_z,
    }
    return ctx


class _Acc:
    __slots__ = ("n", "hits", "sum_p", "sum_brier", "sum_ret", "n_ret")

    def __init__(self) -> None:
        self.n = 0
        self.hits = 0
        self.sum_p = 0.0
        self.sum_brier = 0.0
        self.sum_ret = 0.0
        self.n_ret = 0

    def add(self, p: float, won: bool, odds: float | None = None) -> None:
        y = 1.0 if won else 0.0
        self.n += 1
        self.hits += int(won)
        self.sum_p += p
        self.sum_brier += (p - y) ** 2
        if odds is not None and odds > 1.0:
            self.n_ret += 1
            self.sum_ret += (odds - 1.0) if won else -1.0

    def summarize(self, prior_n: float = DEFAULT_PRIOR_N) -> dict[str, Any]:
        if self.n == 0:
            return {
                "n": 0, "hits": 0, "hit_rate": 0.0, "mean_p": 0.0,
                "raw_residual": 0.0, "shrunk_residual": 0.0, "brier": 0.0, "flat_roi": None,
            }
        hr = self.hits / self.n
        mp = self.sum_p / self.n
        raw = hr - mp
        return {
            "n": self.n,
            "hits": self.hits,
            "hit_rate": round(hr, 4),
            "mean_p": round(mp, 4),
            "raw_residual": round(raw, 4),
            "shrunk_residual": round(_shrink(raw, self.n, prior_n), 4),
            "brier": round(self.sum_brier / self.n, 4),
            "flat_roi": round(self.sum_ret / self.n_ret, 4) if self.n_ret > 0 else None,
        }


def list_ai_dates(ai_dir: Path) -> list[str]:
    """Yalnız bu yapay zekânın kendi klasöründeki YYYY-MM-DD günlerini listeler."""
    if not ai_dir.exists() or not ai_dir.is_dir():
        return []
    return sorted(
        p.name
        for p in ai_dir.iterdir()
        if p.is_dir() and DATE_RE.match(p.name) and (p / "nesine_global.json").exists()
    )


def _fetch_dates_with_next_day(dates: Sequence[str]) -> dict[int, dict[str, Any]]:
    query_dates: set[str] = set()
    for d in dates:
        query_dates.add(d)
        try:
            nxt = dt.date.fromisoformat(d) + dt.timedelta(days=1)
            query_dates.add(nxt.isoformat())
        except ValueError:
            pass
    return fetch_results(sorted(query_dates))


def run_self_audit(
    ai_dir: Path,
    *,
    dates: Sequence[str] | None = None,
    results_by_code: Mapping[int, Mapping[str, Any]] | None = None,
    min_p: float = DEFAULT_MIN_P,
    min_odds: float = DEFAULT_MIN_ODDS,
    prior_n: float = DEFAULT_PRIOR_N,
    min_n: int = DEFAULT_MIN_N,
) -> dict[str, Any]:
    """Aktif yapay zekânın kendi bitmiş günlerini çok boyutlu olarak denetler."""
    ai_path = Path(ai_dir).resolve()
    available = list_ai_dates(ai_path)
    target_dates = [d for d in (dates or available) if d in available]

    if results_by_code is None:
        results = _fetch_dates_with_next_day(target_dates) if target_dates else {}
    else:
        results = {int(k): dict(v) for k, v in results_by_code.items()}

    overall = _Acc()
    main_picks_acc = _Acc()
    by_selection: dict[str, _Acc] = {}
    by_family: dict[str, _Acc] = {}
    by_band: dict[str, _Acc] = {}
    by_price_kind: dict[str, _Acc] = {}
    by_steam: dict[str, _Acc] = {}
    by_steam_market: dict[str, _Acc] = {}
    by_diag_bucket: dict[str, _Acc] = {}
    day_summaries: list[dict[str, Any]] = []
    corp_probs: list[float] = []
    corp_outcomes: list[float] = []

    settled_match_codes: set[int] = set()

    for d in target_dates:
        day_dir = ai_path / d
        ng_path = day_dir / "nesine_global.json"
        if not ng_path.exists():
            continue
        ng = json.loads(ng_path.read_text(encoding="utf-8"))
        day_acc = _Acc()
        day_matches = 0

        for m in ng.get("matches") or []:
            if m.get("status") != "fiyatlandı":
                continue
            try:
                code = int(m["code"])
            except (KeyError, TypeError, ValueError):
                continue
            res = results.get(code)
            if not res or not res.get("completed"):
                continue
            ht = tuple(res["ht"])
            ft90 = tuple(res["ft90"])
            day_matches += 1
            settled_match_codes.add(code)

            sp = _steam_pp(m)
            sb = _steam_bucket(sp)

            for sel in m.get("selections") or []:
                odds = _flt(sel.get("odds"))
                p = _flt(sel.get("fair_prob"))
                if odds is None or p is None or odds < min_odds or p < min_p:
                    continue
                cname = canonical_name(sel.get("name"))
                if not cname:
                    continue
                try:
                    won = settle_selection(cname, ht, ft90)
                except (ValueError, KeyError, IndexError):
                    won = None
                if won is None:
                    continue

                fam = market_family(cname)
                pkind = "direct" if sel.get("direct") else "derived"
                band = _prob_band(p)

                overall.add(p, won, odds)
                corp_probs.append(float(p))
                corp_outcomes.append(1.0 if won else 0.0)
                day_acc.add(p, won, odds)
                by_selection.setdefault(cname, _Acc()).add(p, won, odds)
                by_family.setdefault(fam, _Acc()).add(p, won, odds)
                by_band.setdefault(band, _Acc()).add(p, won, odds)
                by_price_kind.setdefault(pkind, _Acc()).add(p, won, odds)
                by_steam.setdefault(sb, _Acc()).add(p, won, odds)

                if cname in ("MS 1", "MS 2"):
                    by_steam_market.setdefault(f"MS 1/2 | {sb}", _Acc()).add(p, won, odds)
                elif cname in ("İY 1.5 Alt", "2.5 Alt", "3.5 Alt", "4.5 Alt"):
                    by_steam_market.setdefault(f"ALT | {sb}", _Acc()).add(p, won, odds)

                diag = diagnose_selection(cname, p, _build_diag_ctx(m, sel), for_coupon=True)
                bucket = "REHAB" if (diag.ok and diag.rehabilitated) else ("OK" if diag.ok else "TUZAK_RED")
                by_diag_bucket.setdefault(bucket, _Acc()).add(p, won, odds)

        # Ana tahminler (mac_tahminleri.csv) kontrolü
        csv_path = day_dir / "mac_tahminleri.csv"
        day_main = _Acc()
        if csv_path.exists():
            with csv_path.open(encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    code_s = str(row.get("nesine_kodu") or "").strip()
                    if not code_s.isdigit():
                        continue
                    res = results.get(int(code_s))
                    if not res or not res.get("completed"):
                        continue
                    cname = canonical_name(row.get("secim_adi") or row.get("secim"))
                    p = _flt(row.get("olasilik"))
                    odds = _flt(row.get("nesine_oran"))
                    if not cname or p is None:
                        continue
                    try:
                        won = settle_selection(cname, tuple(res["ht"]), tuple(res["ft90"]))
                    except (ValueError, KeyError, IndexError):
                        won = None
                    if won is None:
                        continue
                    main_picks_acc.add(p, won, odds)
                    day_main.add(p, won, odds)

        day_summaries.append({
            "date": d,
            "settled_matches": day_matches,
            "coupon_zone": day_acc.summarize(prior_n),
            "main_picks": day_main.summarize(prior_n),
        })

    sel_stats = {k: v.summarize(prior_n) for k, v in by_selection.items()}
    fam_stats = {k: v.summarize(prior_n) for k, v in by_family.items()}
    band_stats = {label: by_band[label].summarize(prior_n) for _, _, label in PROB_BANDS if label in by_band}
    pkind_stats = {k: v.summarize(prior_n) for k, v in by_price_kind.items()}
    steam_stats = {k: v.summarize(prior_n) for k, v in sorted(by_steam.items())}
    steam_mkt_stats = {k: v.summarize(prior_n) for k, v in sorted(by_steam_market.items())}
    diag_stats = {k: by_diag_bucket[k].summarize(prior_n) for k in ("REHAB", "OK", "TUZAK_RED") if k in by_diag_bucket}

    toxic_alarms = sorted(
        [
            {"selection": k, **st}
            for k, st in sel_stats.items()
            if st["n"] >= min_n and (st["shrunk_residual"] <= -0.020 or st["raw_residual"] <= -0.060)
        ],
        key=lambda x: (x["raw_residual"], -x["n"]),
    )
    golden_pools = sorted(
        [
            {"selection": k, **st}
            for k, st in sel_stats.items()
            if st["n"] >= min_n and (st["shrunk_residual"] >= 0.012 or (st["hit_rate"] >= 0.70 and st["raw_residual"] >= 0.03))
        ],
        key=lambda x: (-x["hit_rate"], -x["raw_residual"], -x["n"]),
    )
    calibration_suggestions = [
        {
            "pattern": f"^{re.escape(item['selection'])}$",
            "n": item["n"],
            "hit_rate": item["hit_rate"],
            "mean_p": item["mean_p"],
            "residual": item["raw_residual"],
            "shrunk_residual": item["shrunk_residual"],
        }
        for item in toxic_alarms[:10]
    ]

    corp_calibration: dict[str, Any] | None = None
    if len(corp_probs) >= 5:
        from quantfoot.evaluation.clv_tracker import corp_reliability_decomposition
        c_res = corp_reliability_decomposition(corp_outcomes, corp_probs)
        corp_calibration = {
            "n": c_res.n,
            "brier": round(c_res.brier, 5),
            "corp_ece": round(c_res.corp_ece, 5),
            "mcb": round(c_res.mcb, 5),
            "dsc": round(c_res.dsc, 5),
            "unc": round(c_res.unc, 5),
            "skill_vs_climo": round(c_res.dsc - c_res.mcb, 5),
            "n_isotonic_levels": c_res.n_isotonic_levels,
        }

    clv_summary: dict[str, Any] | None = None
    ledger_path = ai_path / "clv_defteri.jsonl"
    if ledger_path.exists():
        try:
            from quantfoot.evaluation.clv_ledger import summarize_clv_ledger
            clv_summary = summarize_clv_ledger(ledger_path)
        except Exception:  # noqa: BLE001 — CLV özeti isteğe bağlı
            clv_summary = None

    return {
        "ai": ai_path.name,
        "generated_at": dt.datetime.now(TSI).isoformat(timespec="minutes"),
        "dates": target_dates,
        "settled_matches": len(settled_match_codes),
        "filters": {"min_p": min_p, "min_odds": min_odds, "prior_n": prior_n, "min_n": min_n},
        "overall_coupon_zone": overall.summarize(prior_n),
        "corp_calibration": corp_calibration,
        "clv_summary": clv_summary,
        "main_picks": main_picks_acc.summarize(prior_n),
        "days": day_summaries,
        "by_diagnosis_v3": diag_stats,
        "by_band": band_stats,
        "by_price_kind": pkind_stats,
        "by_steam": steam_stats,
        "by_steam_market": steam_mkt_stats,
        "by_family": fam_stats,
        "by_selection": sel_stats,
        "toxic_alarms": toxic_alarms,
        "golden_pools": golden_pools,
        "calibration_suggestions": calibration_suggestions,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    """Öz-geliştirme denetim raporunu okunaklı Türkçe Markdown olarak biçimlendir."""
    ov = report["overall_coupon_zone"]
    mp = report["main_picks"]
    lines = [
        f"# Öz-Geliştirme ve Kalibrasyon Denetim Raporu — `{report['ai']}`",
        "",
        f"- **Oluşturulma:** {report['generated_at']}",
        f"- **Denetlenen günler:** {', '.join(report['dates']) or '-'} ({report['settled_matches']} bitmiş fiyatlı maç)",
        f"- **Kupon bölgesi (P ≥ %{100*report['filters']['min_p']:.0f}, oran ≥ {report['filters']['min_odds']:.2f}):** "
        f"**{ov['hits']}/{ov['n']} (%{100*ov['hit_rate']:.1f})** vs beklenen %{100*ov['mean_p']:.1f} "
        f"(artık **{100*ov['raw_residual']:+.1f}p**, Brier `{ov['brier']:.4f}`)",
        f"- **Ana tahminler (`mac_tahminleri.csv`):** "
        f"**{mp['hits']}/{mp['n']} (%{100*mp['hit_rate']:.1f})** vs beklenen %{100*mp['mean_p']:.1f} "
        f"(artık **{100*mp['raw_residual']:+.1f}p**)",
        "",
        "## 1. `market_diagnosis` v3 Ayrıştırma Başarımı",
        "",
        "| Sınıf | Adet | İsabet | Gerçek % | Beklenen % | Artık | Brier | Düz 1u ROI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for k, st in (report.get("by_diagnosis_v3") or {}).items():
        roi_s = f"%{100*st['flat_roi']:+.1f}" if st["flat_roi"] is not None else "-"
        lines.append(
            f"| **{k}** | {st['n']} | {st['hits']} | %{100*st['hit_rate']:.1f} | %{100*st['mean_p']:.1f} | "
            f"{100*st['raw_residual']:+.1f}p | {st['brier']:.4f} | {roi_s} |"
        )

    lines += [
        "",
        "## 2. Keskin Borsa Steam Kırılımı (v3 Kalkan Doğrulaması)",
        "",
        "| Pazar / Steam Dilimi | Adet | İsabet | Gerçek % | Beklenen % | Artık |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for k, st in (report.get("by_steam_market") or {}).items():
        k_md = str(k).replace("|", "·")
        lines.append(
            f"| {k_md} | {st['n']} | {st['hits']} | %{100*st['hit_rate']:.1f} | %{100*st['mean_p']:.1f} | {100*st['raw_residual']:+.1f}p |"
        )

    lines += [
        "",
        "## 3. Altın Havuzlar (En Yüksek İsabet & Pozitif Artık)",
        "",
        "| Alt-Pazar | Adet | İsabet | Gerçek % | Beklenen % | Artık | Büzüştürülmüş | Düz 1u ROI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in (report.get("golden_pools") or [])[:12]:
        roi_s = f"%{100*item['flat_roi']:+.1f}" if item["flat_roi"] is not None else "-"
        lines.append(
            f"| **{item['selection']}** | {item['n']} | {item['hits']} | %{100*item['hit_rate']:.1f} | "
            f"%{100*item['mean_p']:.1f} | {100*item['raw_residual']:+.1f}p | {100*item['shrunk_residual']:+.1f}p | {roi_s} |"
        )
    if not report.get("golden_pools"):
        lines.append("| _Eşiği geçen örnek yok_ | - | - | - | - | - | - | - |")

    lines += [
        "",
        "## 4. Zehirli Alt-Pazar Alarmları (Aksiyon Gerektirenler)",
        "",
        "| Alt-Pazar | Adet | İsabet | Gerçek % | Beklenen % | Artık | Büzüştürülmüş | Düz 1u ROI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in (report.get("toxic_alarms") or [])[:12]:
        roi_s = f"%{100*item['flat_roi']:+.1f}" if item["flat_roi"] is not None else "-"
        lines.append(
            f"| **{item['selection']}** | {item['n']} | {item['hits']} | %{100*item['hit_rate']:.1f} | "
            f"%{100*item['mean_p']:.1f} | {100*item['raw_residual']:+.1f}p | {100*item['shrunk_residual']:+.1f}p | {roi_s} |"
        )
    if not report.get("toxic_alarms"):
        lines.append("| _Zehirli alarm yok_ | - | - | - | - | - | - | - |")

    lines += [
        "",
        "## 5. Olasılık Dilimleri ve Fiyat Kaynağı",
        "",
        "| Dilim / Kaynak | Adet | İsabet | Gerçek % | Beklenen % | Artık | Brier |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for k, st in (report.get("by_band") or {}).items():
        lines.append(
            f"| {k} | {st['n']} | {st['hits']} | %{100*st['hit_rate']:.1f} | %{100*st['mean_p']:.1f} | {100*st['raw_residual']:+.1f}p | {st['brier']:.4f} |"
        )
    for k, st in (report.get("by_price_kind") or {}).items():
        lines.append(
            f"| kaynak: `{k}` | {st['n']} | {st['hits']} | %{100*st['hit_rate']:.1f} | %{100*st['mean_p']:.1f} | {100*st['raw_residual']:+.1f}p | {st['brier']:.4f} |"
        )

    corp = report.get("corp_calibration")
    if isinstance(corp, Mapping) and corp.get("n", 0) > 0:
        lines += [
            "",
            "## 6. CORP Kutusuz Kalibrasyon Ayrıştırması (Dimitriadis et al. 2021)",
            "",
            f"- **Brier:** `{corp['brier']:.5f}` = **MCB (Yanlış Kalibrasyon):** `{corp['mcb']:.5f}` "
            f"− **DSC (Ayırt Etme):** `{corp['dsc']:.5f}` + **UNC (Belirsizlik):** `{corp['unc']:.5f}` "
            f"· **CORP ECE:** `{corp['corp_ece']:.5f}` · **Beceri (DSC − MCB):** `{corp['skill_vs_climo']:+.5f}` "
            f"(`{corp['n_isotonic_levels']}` PAVA düzeyi)",
        ]

    clv = report.get("clv_summary")
    if isinstance(clv, Mapping) and clv.get("n_with_closing_clv", 0) > 0:
        clv_rep = clv.get("clv_report") or {}
        lines += [
            "",
            "## 7. Kapanış Çizgisi Değeri (CLV Defteri)",
            "",
            f"- **CLV ölçülen seçim:** {clv['n_with_closing_clv']} · "
            f"**Ortalama CLV:** `%{100*float(clv_rep.get('mean_clv', 0.0)):+.2f}` · "
            f"**Pozitif CLV oranı:** `%{100*float(clv_rep.get('positive_rate', 0.0)):.1f}`",
        ]
    lines.append("")
    return "\n".join(lines)


def write_self_audit(
    ai_dir: Path,
    *,
    dates: Sequence[str] | None = None,
    results_by_code: Mapping[int, Mapping[str, Any]] | None = None,
    min_p: float = DEFAULT_MIN_P,
    min_odds: float = DEFAULT_MIN_ODDS,
    prior_n: float = DEFAULT_PRIOR_N,
    min_n: int = DEFAULT_MIN_N,
) -> tuple[dict[str, Any], Path, Path]:
    """Öz-geliştirme denetimini çalıştır ve kendi klasörüne .md / .json yaz."""
    report = run_self_audit(
        ai_dir,
        dates=dates,
        results_by_code=results_by_code,
        min_p=min_p,
        min_odds=min_odds,
        prior_n=prior_n,
        min_n=min_n,
    )
    ai_path = Path(ai_dir).resolve()
    ai_path.mkdir(parents=True, exist_ok=True)
    md_path = ai_path / "oz_gelistirme_raporu.md"
    json_path = ai_path / "oz_gelistirme_raporu.json"
    md_path.write_text(render_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report, md_path, json_path

"""Empirical-Bayes self-learning & live calibration loop over settled daily predictions.

Reads all settled days in ``reports/daily/*/takip_kayit.json`` + ``takip_sonuc.json`` (plus
``kupon_*.json``) and measures realized accuracy vs. predicted probability across:

- Price reference sources (Pinnacle, Smarkets, Matchbook, OddsMath BetInAsia, Marathonbet, 1XBET, Nesine)
- Market families (Maç sonucu, Çifte şans, Alt/Üst, KG, İlk yarı, İkinci yarı, İY/MS, Gol aralığı, Kombine…)
- Leagues / competitions
- Probability calibration bands (0–20%, ..., 80–100%)

Outputs:
- ``data/calibration/live_calibration.json`` — machine-readable ``sigma`` adjustments consumed
  automatically by ``scripts/nesine_kupon.py`` (strictly regularized via Empirical Bayes shrinkage
  ``n / (n + prior_n)`` with ``min_samples=30`` so small-sample luck never destabilizes parameters).
- ``reports/takip/ogrenme_raporu.md`` — human-readable Turkish daily self-audit & learning log.
"""

from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

from quantfoot.paths import ai_area

TSI = dt.timezone(dt.timedelta(hours=3))

MIN_SAMPLES_SOURCE = 30
MIN_SAMPLES_FAMILY = 40
MIN_SAMPLES_LEAGUE = 25
SHRINKAGE_PRIOR_N = 60.0
AUTO_BLOCK_MIN_N = 50
AUTO_BLOCK_BIAS_THRESHOLD = -0.075  # realized hit rate >= 7.5 pts below predicted
# Probability calibration of coupon-zone legs (odds >= 1.20, p >= 50 %), per price kind (direct / model) and band:
# the measured bias, shrunk by n / (n + PRIOR) and clipped; a shift lowering p may go further than one raising it.
PROB_SHIFT_MIN_N = 30
PROB_SHIFT_PRIOR_N = 150.0
PROB_SHIFT_CLIP = (-0.08, 0.03)
PROB_BANDS = ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01))


def _prob_band(p: float) -> str | None:
    for lo, hi in PROB_BANDS:
        if lo <= p < hi:
            return f"{lo:.1f}-{min(hi, 1.0):.1f}"
    return None


def market_family(name: str) -> str:
    """Map a canonical Turkish selection name to its market family."""
    n = str(name).replace("DEĞİL(", "").strip()
    if not n:
        return "Diğer"
    if n.startswith("İY/MS"):
        return "İY/MS"
    if "&" in n:
        return "Kombine (A & B)"
    for prefix, fam in (
        ("MS ", "Maç sonucu"),
        ("ÇŞ ", "Çifte şans"),
        ("KG", "Karşılıklı gol"),
        ("İY KG", "İY karşılıklı gol"),
        ("2Y KG", "2Y karşılıklı gol"),
        ("İY Korner", "İY korner"),
        ("Korner", "Korner"),
        ("İY ", "İlk yarı"),
        ("2Y ", "İkinci yarı"),
        ("Ev ", "Ev sahibi golleri"),
        ("Dep ", "Deplasman golleri"),
        ("Hnd", "Handikap"),
        ("İlk Gol", "İlk gol"),
        ("Tek", "Tek/Çift"),
        ("Çift", "Tek/Çift"),
    ):
        if n.startswith(prefix):
            return fam
    if n[0].isdigit() and ("Üst" in n or "Alt" in n):
        return "Alt/Üst"
    if "Gol" in n:
        return "Gol aralığı"
    return "Diğer"


def _canonical_source(ref: str | None) -> str:
    if not ref:
        return "Bilinmeyen"
    s = str(ref).strip()
    if s.startswith("Matchbook + Smarkets"):
        return "Matchbook + Smarkets"
    if s.startswith("OddsMath (BetInAsia"):
        return "OddsMath (BetInAsia/Pinnacle)"
    if s.startswith("OddsMath (Borsa"):
        return "OddsMath (Borsa)"
    if s.startswith("OddsMath ("):
        return s
    if s.startswith("Nesine"):
        return "Nesine (düşük güven)"
    return s.split(" (")[0]


def _bucket_stats(rows: list[tuple[float, bool]]) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {"n": 0, "mean_pred": None, "realized": None, "bias": None, "brier": None}
    mean_p = sum(p for p, _ in rows) / n
    real = sum(1.0 for _, w in rows if w) / n
    brier = sum((p - (1.0 if w else 0.0)) ** 2 for p, w in rows) / n
    return {
        "n": n,
        "mean_pred": round(mean_p, 4),
        "realized": round(real, 4),
        "bias": round(real - mean_p, 4),
        "brier": round(brier, 4),
    }


def _sigma_delta_from_group(
    stats: dict[str, Any],
    *,
    min_samples: int,
    max_bonus: float = -0.006,
    max_penalty: float = 0.035,
) -> float:
    """Compute an Empirical-Bayes shrunk sigma adjustment from realized calibration error.

    Negative ``bias`` (overconfident predictions: realized < predicted) widens ``sigma`` (+delta).
    Well-calibrated large samples (``|bias| <= 0.015`` and ``n >= 100``) earn a modest bonus (negative delta).
    """
    n = int(stats.get("n") or 0)
    if n < min_samples or stats.get("bias") is None:
        return 0.0
    bias = float(stats["bias"])
    weight = n / (n + SHRINKAGE_PRIOR_N)
    if bias < -0.015:
        # Overconfident -> widen sigma proportionally to excess overconfidence
        raw = min(max_penalty, (-bias - 0.01) * 0.65)
        return round(raw * weight, 4)
    if abs(bias) <= 0.015 and n >= max(min_samples * 2, 80):
        # Consistently well-calibrated at scale -> small confidence bonus
        return round(max_bonus * weight, 4)
    return 0.0


def analyze_settled_history(daily_dir: Path) -> dict[str, Any]:
    """Scan all settled days under ``daily_dir`` and build a full calibration & learning snapshot."""
    # the AI's own folder (tahminler/<ai>) plus the old shared archive (reports/daily, days up to 19 Nov)
    found: dict[str, Path] = {}
    for base in (daily_dir.parents[1] / "reports" / "daily", daily_dir):
        if base.exists():
            for p in base.iterdir():
                if p.is_dir() and (p / "takip_sonuc.json").exists() and (p / "takip_kayit.json").exists():
                    found[p.name] = p  # the own folder wins for the same day
    day_dirs = [found[k] for k in sorted(found)]

    all_rows: list[tuple[float, bool]] = []
    bettable_rows: list[tuple[float, bool]] = []  # odds >= 1.20 and p >= 0.50 (coupon-relevant zone)
    by_source: dict[str, list[tuple[float, bool]]] = {}
    by_source_high: dict[str, list[tuple[float, bool]]] = {}
    by_family: dict[str, list[tuple[float, bool]]] = {}
    by_family_high: dict[str, list[tuple[float, bool]]] = {}
    by_league: dict[str, list[tuple[float, bool]]] = {}
    by_direct: dict[str, list[tuple[float, bool]]] = {"doğrudan": [], "model": []}
    by_kind_band: dict[str, list[tuple[float, bool]]] = {}  # coupon zone, "doğrudan|0.6-0.7"
    by_day: list[dict[str, Any]] = []
    coupons_settled: list[dict[str, Any]] = []

    bands_def = [
        ("0–20%", 0.0, 0.2),
        ("20–40%", 0.2, 0.4),
        ("40–50%", 0.4, 0.5),
        ("50–60%", 0.5, 0.6),
        ("60–70%", 0.6, 0.7),
        ("70–80%", 0.7, 0.8),
        ("80–100%", 0.8, 1.01),
    ]
    by_band: dict[str, list[tuple[float, bool]]] = {lbl: [] for lbl, _, _ in bands_def}

    days_used: list[str] = []
    total_matches_settled = 0

    for d in day_dirs:
        day_name = d.name
        try:
            store = json.loads((d / "takip_kayit.json").read_text(encoding="utf-8"))
            results = json.loads((d / "takip_sonuc.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        day_rows: list[tuple[float, bool]] = []
        day_matches = 0
        day_safest: list[tuple[float, bool]] = []

        for code, res in results.items():
            if not res.get("completed") or code not in store:
                continue
            rec = store[code]
            sels = rec.get("s") or {}
            won_map = res.get("won") or {}
            if not won_map:
                continue
            day_matches += 1
            total_matches_settled += 1
            src = _canonical_source(rec.get("reference"))
            lg = str(rec.get("league") or "Bilinmeyen")

            eligible_safest = [(float(v[0]), n) for n, v in sels.items() if float(v[1]) >= 1.20 and n in won_map]
            safest_name = max(eligible_safest)[1] if eligible_safest else None

            for sel_name, won in won_map.items():
                if sel_name not in sels:
                    continue
                p_val, odds_val, direct_flag = float(sels[sel_name][0]), float(sels[sel_name][1]), bool(sels[sel_name][2])
                w_bool = bool(won)
                pair = (p_val, w_bool)

                all_rows.append(pair)
                day_rows.append(pair)
                by_source.setdefault(src, []).append(pair)
                fam = market_family(sel_name)
                by_family.setdefault(fam, []).append(pair)
                by_direct["doğrudan" if direct_flag else "model"].append(pair)

                for lbl, lo, hi in bands_def:
                    if lo <= p_val < hi:
                        by_band[lbl].append(pair)
                        break

                if odds_val >= 1.20 and p_val >= 0.50:
                    bettable_rows.append(pair)
                    band = _prob_band(p_val)
                    if band:
                        by_kind_band.setdefault(f"{'doğrudan' if direct_flag else 'model'}|{band}", []).append(pair)
                    by_source_high.setdefault(src, []).append(pair)
                    by_family_high.setdefault(fam, []).append(pair)
                    by_league.setdefault(lg, []).append(pair)

                if sel_name == safest_name:
                    day_safest.append(pair)

        if day_matches > 0:
            days_used.append(day_name)
            st_day = _bucket_stats(day_rows)
            st_safe = _bucket_stats(day_safest)
            by_day.append(
                {
                    "date": day_name,
                    "matches": day_matches,
                    "selections": st_day["n"],
                    "brier": st_day["brier"],
                    "safest_n": st_safe["n"],
                    "safest_pred": st_safe["mean_pred"],
                    "safest_hit": st_safe["realized"],
                }
            )

        claude_dir = daily_dir / day_name  # the AI's own coupons (20 Nov+)
        for kf in sorted([*d.glob("kupon_*.json"), *claude_dir.glob("kupon_*x_*.json")]):
            try:
                kdata = json.loads(kf.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for c in kdata.get("coupons", []):
                statuses = []
                for leg in c.get("legs", []):
                    nm = leg.get("name") or (leg.get("key") or "||").split("|")[1]
                    r_m = results.get(str(leg.get("code"))) or {}
                    statuses.append(r_m.get("won", {}).get(nm) if r_m.get("completed") else None)
                if statuses and all(x is not None for x in statuses):
                    coupons_settled.append(
                        {
                            "date": day_name,
                            "file": kf.name,
                            "odds": round(float(c.get("nesine_odds") or 0.0), 2),
                            "prob": round(float(c.get("probability") or 0.0), 4),
                            "won": all(statuses),
                            "legs_won": sum(1 for x in statuses if x),
                            "legs_total": len(statuses),
                        }
                    )

    source_summary: dict[str, dict[str, Any]] = {}
    source_sigma_delta: dict[str, float] = {}
    for src, rows in sorted(by_source.items(), key=lambda kv: -len(kv[1])):
        st_all = _bucket_stats(rows)
        st_hi = _bucket_stats(by_source_high.get(src, []))
        # Always calibrate sigma ONLY on the coupon-relevant >=50% odds>=1.20 band (never on all-outcome complements)
        delta = _sigma_delta_from_group(st_hi, min_samples=MIN_SAMPLES_SOURCE)
        source_summary[src] = {**st_all, "bettable": st_hi, "sigma_delta": delta}
        if abs(delta) > 1e-6:
            source_sigma_delta[src] = delta

    family_summary: dict[str, dict[str, Any]] = {}
    family_sigma_delta: dict[str, float] = {}
    auto_blocked_families: list[str] = []
    for fam, rows in sorted(by_family.items(), key=lambda kv: -len(kv[1])):
        st_all = _bucket_stats(rows)
        st_hi = _bucket_stats(by_family_high.get(fam, []))
        delta = _sigma_delta_from_group(st_hi, min_samples=MIN_SAMPLES_FAMILY)
        blocked = (
            st_hi["n"] >= AUTO_BLOCK_MIN_N
            and st_hi["bias"] is not None
            and st_hi["bias"] <= AUTO_BLOCK_BIAS_THRESHOLD
        )
        family_summary[fam] = {**st_all, "bettable": st_hi, "sigma_delta": delta, "auto_block_warn": blocked}
        if abs(delta) > 1e-6:
            family_sigma_delta[fam] = delta
        if blocked:
            auto_blocked_families.append(fam)

    prob_shift: dict[str, float] = {}
    kind_band_summary: dict[str, dict[str, Any]] = {}
    for key, rows in sorted(by_kind_band.items()):
        st = _bucket_stats(rows)
        kind_band_summary[key] = st
        if st["n"] >= PROB_SHIFT_MIN_N:
            shift = st["bias"] * st["n"] / (st["n"] + PROB_SHIFT_PRIOR_N)
            prob_shift[key] = round(max(PROB_SHIFT_CLIP[0], min(PROB_SHIFT_CLIP[1], shift)), 4)

    league_summary: dict[str, dict[str, Any]] = {}
    for lg, rows in sorted(by_league.items(), key=lambda kv: -len(kv[1])):
        st = _bucket_stats(rows)
        if st["n"] >= MIN_SAMPLES_LEAGUE and st["bias"] is not None:
            tier = "dalgalı" if st["bias"] <= -0.06 else ("yüksek" if abs(st["bias"]) <= 0.03 else "orta")
        else:
            tier = "yetersiz örneklem"
        league_summary[lg] = {**st, "stability": tier}

    return {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "generated_tsi": dt.datetime.now(TSI).isoformat(timespec="seconds"),
        "days": days_used,
        "total_matches_settled": total_matches_settled,
        "overall": _bucket_stats(all_rows),
        "bettable_overall": _bucket_stats(bettable_rows),
        "direct_vs_model": {k: _bucket_stats(v) for k, v in by_direct.items()},
        "kind_bands": kind_band_summary,
        "bands": {lbl: _bucket_stats(by_band[lbl]) for lbl, _, _ in bands_def},
        "sources": source_summary,
        "families": family_summary,
        "leagues": league_summary,
        "by_day": by_day,
        "coupons": coupons_settled,
        "adjustments": {
            "min_samples_source": MIN_SAMPLES_SOURCE,
            "min_samples_family": MIN_SAMPLES_FAMILY,
            "source_sigma_delta": source_sigma_delta,
            "family_sigma_delta": family_sigma_delta,
            "auto_blocked_families": auto_blocked_families,
            "prob_shift": prob_shift,
        },
    }


def load_live_calibration(path: Path | None = None) -> dict[str, Any]:
    """Load persisted live calibration adjustments (empty dict if missing/corrupt)."""
    target = path or (Path(__file__).resolve().parents[3] / "data" / "calibration" / "live_calibration.json")
    if not target.exists():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def calibration_sigma_adjustment(
    reference: str,
    selection_name: str,
    calibration: dict[str, Any] | None = None,
) -> float:
    """Return learned Empirical-Bayes ``sigma`` adjustment (clamped to ``[-0.008, +0.045]``)."""
    if not calibration:
        return 0.0
    adj = calibration.get("adjustments") or {}
    src_deltas = adj.get("source_sigma_delta") or {}
    fam_deltas = adj.get("family_sigma_delta") or {}

    src_key = _canonical_source(reference)
    fam_key = market_family(selection_name)
    delta = float(src_deltas.get(src_key, 0.0)) + float(fam_deltas.get(fam_key, 0.0))
    if not math.isfinite(delta):
        return 0.0
    return max(-0.008, min(0.045, round(delta, 4)))


def calibrated_probability(p: float, direct: bool, calibration: dict[str, Any] | None = None) -> float:
    """Global probability corrected by what settled coupon-zone legs of the same kind and band realised."""
    band = _prob_band(p)
    if not calibration or band is None:
        return p
    shift = float(((calibration.get("adjustments") or {}).get("prob_shift") or {}).get(
        f"{'doğrudan' if direct else 'model'}|{band}", 0.0))
    return min(0.99, max(0.01, p + shift)) if math.isfinite(shift) else p


def render_learning_report(snapshot: dict[str, Any]) -> str:
    """Render the Turkish self-audit & calibration learning Markdown report."""
    ov = snapshot["overall"]
    bo = snapshot["bettable_overall"]
    days = snapshot.get("days") or []
    adj = snapshot.get("adjustments") or {}

    lines = [
        "# QuantFoot Öz-Öğrenme ve Canlı Kalibrasyon Raporu",
        "",
        f"- Güncelleme: `{snapshot['generated_tsi'][:16].replace('T', ' ')} TSİ`",
        f"- Değerlendirilen günler ({len(days)}): {', '.join(days) if days else 'henüz yok'}",
        f"- Sonuçlanan maç: **{snapshot['total_matches_settled']}** · Toplam seçim: **{ov['n']}** · "
        f"Brier skoru: **{ov['brier'] if ov['brier'] is not None else '-'}**",
    ]
    if bo["n"]:
        lines.append(
            f"- Kupon bandı (oran ≥ 1,20 & tahmin ≥ %50): **{bo['n']}** seçim · "
            f"Ortalama tahmin **%{bo['mean_pred'] * 100:.1f}** · Gerçekleşen **%{bo['realized'] * 100:.1f}** "
            f"({bo['bias'] * 100:+.1f} puan)"
        )
    lines += [
        "",
        "> Bu dosya her gece sonuçlar işlendikten sonra `scripts/auto_learn.py` tarafından otomatik üretilir. "
        "Empirical Bayes daraltması sayesinde 30–40 seçimin altındaki küçük örneklemler parametrelere dokunmaz; "
        "yeterli veri biriktiğinde sistematik sapma gösteren kaynak ve pazarların belirsizlik payı (`sigma`) "
        "`data/calibration/live_calibration.json` üzerinden kupon motoruna otomatik yansıtılır.",
        "",
        "## Aktif Öğrenilmiş Parametre Düzeltmeleri (`live_calibration.json`)",
        "",
    ]

    src_d = adj.get("source_sigma_delta") or {}
    fam_d = adj.get("family_sigma_delta") or {}
    blk = adj.get("auto_blocked_families") or []
    if not src_d and not fam_d and not blk:
        lines.append("_Henüz minimum örneklem eşiğini aşan sistematik sapma yok — varsayılan kalibrasyon korunuyor._")
    else:
        for k, v in sorted(src_d.items()):
            lines.append(f"- **Kaynak `{k}`**: `sigma {v:+.4f}`")
        for k, v in sorted(fam_d.items()):
            lines.append(f"- **Pazar ailesi `{k}`**: `sigma {v:+.4f}`")
        if blk:
            lines.append(f"- **⚠ Yüksek Sapma Uyarılı Pazarlar**: {', '.join(blk)}")

    lines += [
        "",
        "## Kaynak Bazlı Gerçek Performans",
        "",
        "| Kaynak | Tüm Seçim | Ortalama Tahmin | Gerçekleşen | Brier | Kupon Bandı (n) | Kupon Sapması | Öğrenilen Δσ |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for src, st in (snapshot.get("sources") or {}).items():
        bt = st.get("bettable") or {}
        bt_bias = f"{bt['bias'] * 100:+.1f}p" if bt.get("bias") is not None else "-"
        lines.append(
            f"| {src} | {st['n']} | %{st['mean_pred'] * 100:.1f} | %{st['realized'] * 100:.1f} | "
            f"{st['brier']:.4f} | {bt.get('n', 0)} | {bt_bias} | {st['sigma_delta']:+.4f} |"
        )

    lines += [
        "",
        "## Pazar Ailesi Bazlı Kalibrasyon",
        "",
        "| Pazar Ailesi | Seçim | Tahmin | Gerçekleşen | Fark | Brier | Kupon Bandı Sapma | Öğrenilen Δσ |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for fam, st in (snapshot.get("families") or {}).items():
        bt = st.get("bettable") or {}
        bt_s = f"{bt['bias'] * 100:+.1f}p (n={bt['n']})" if bt.get("bias") is not None else "-"
        warn = " ⚠" if st.get("auto_block_warn") else ""
        lines.append(
            f"| {fam}{warn} | {st['n']} | %{st['mean_pred'] * 100:.1f} | %{st['realized'] * 100:.1f} | "
            f"{st['bias'] * 100:+.1f}p | {st['brier']:.4f} | {bt_s} | {st['sigma_delta']:+.4f} |"
        )

    if snapshot.get("by_day"):
        lines += [
            "",
            "## Günlük Trend",
            "",
            "| Gün | Sonuçlanan Maç | Seçim | Brier | En Güvenilir Tercih (Tahmin → Tutan) |",
            "|---|---|---|---|---|",
        ]
        for row in snapshot["by_day"]:
            safe_s = (
                f"%{row['safest_pred'] * 100:.1f} → %{row['safest_hit'] * 100:.1f} ({row['safest_n']} maç)"
                if row["safest_n"]
                else "-"
            )
            lines.append(f"| {row['date']} | {row['matches']} | {row['selections']} | {row['brier']:.4f} | {safe_s} |")

    return "\n".join(lines) + "\n"


def run_auto_learn(
    *,
    root: Path | None = None,
    daily_dir: Path | None = None,
    calibration_path: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Run the end-to-end self-learning pass and persist JSON + Markdown outputs."""
    repo = root or Path(__file__).resolve().parents[3]
    d_dir = daily_dir or ai_area(repo)
    cal_out = calibration_path or (repo / "data" / "calibration" / "live_calibration.json")
    rep_out = report_path or (d_dir / "takip" / "ogrenme_raporu.md")

    snapshot = analyze_settled_history(d_dir)
    cal_out.parent.mkdir(parents=True, exist_ok=True)
    cal_out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    rep_out.parent.mkdir(parents=True, exist_ok=True)
    rep_out.write_text(render_learning_report(snapshot), encoding="utf-8")
    return snapshot

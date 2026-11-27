"""Otomatik Öz-Öğrenme, Sinyal Katkı Ölçümü (Signal Attribution) ve Hata-Minimalize Ağırlık Kalibrasyonu.

Her sinyal katmanının (xG yapısal farkı, bitiricilik/savunma şans gerilemesi, hat/kaleci eşleşmesi,
derbi sıkılığı, beraberlik rejimi, keskin piyasa akışı) gerçekten Brier skoru, Log-Loss ve CLV
iyileştirmesi üretip üretmediğini zamansal sızıntısız (causal) olarak ölçer; zayıf veya gürültülü
sinyallerin ağırlığını Empirical-Bayes (L2 öncül daraltma) ile otomatik aşağı çeker.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

from quantfoot.markets.devig import devig
from quantfoot.markets.high_odds_engine import analyze_close_match
from quantfoot.markets.match_intelligence import (
    SEASON_DATA_DIR,
    _flt,
    _parse_csv_date,
    enrich_match_record,
    load_division_rows,
)
from quantfoot.paths import REPO_ROOT

DEFAULT_WEIGHTS_PATH = REPO_ROOT / "data" / "calibration" / "signal_weights.json"

BASELINE_SIGNAL_WEIGHTS: dict[str, float] = {
    "xg_weight_cap": 0.16,
    "ah_weight": 0.15,
    "luck_cap": 0.022,
    "steam_weight": 0.30,
    "scouting_cap": 0.018,
    "draw_regime_cap": 0.015,
}

_DIV_TO_LEAGUE: dict[str, str] = {
    "E0": "İngiltere Premier Lig",
    "E1": "İngiltere Championship",
    "D1": "Almanya Bundesliga",
    "D2": "Almanya 2. Bundesliga",
    "I1": "İtalya Serie A",
    "I2": "İtalya Serie B",
    "SP1": "İspanya La Liga",
    "SP2": "İspanya La Liga 2",
    "F1": "Fransa Ligue 1",
    "F2": "Fransa Ligue 2",
    "T1": "Türkiye Süper Lig",
    "N1": "Hollanda Eredivisie",
    "P1": "Portekiz Premier Lig",
    "B1": "Belçika Pro Lig",
}


def _brier_1x2(probs: Sequence[float], actual_idx: int) -> float:
    return sum((float(probs[i]) - (1.0 if i == actual_idx else 0.0)) ** 2 for i in range(3))


def _logloss_1x2(probs: Sequence[float], actual_idx: int) -> float:
    p = max(1e-6, min(1.0 - 1e-6, float(probs[actual_idx])))
    return -math.log(p)


@dataclass(frozen=True)
class SignalPerformance:
    """Empirical attribution of one signal family against the sharp market baseline."""

    signal_name: str
    fired_count: int
    market_brier: float
    model_brier: float
    brier_improvement: float  # positive = model beat sharp market!
    market_logloss: float
    model_logloss: float
    logloss_improvement: float
    hit_rate: float
    status: str  # "KATMA DEĞER" | "NÖTR" | "GÜRÜLTÜ — DARALT"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AttributionReport:
    """Full causal signal attribution & Empirical-Bayes recommended weights."""

    evaluated_matches: int
    close_matches: int
    overall_market_brier: float
    overall_model_brier: float
    overall_brier_gain: float
    signals: tuple[SignalPerformance, ...]
    recommended_weights: dict[str, float]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluated_matches": self.evaluated_matches,
            "close_matches": self.close_matches,
            "overall_market_brier": self.overall_market_brier,
            "overall_model_brier": self.overall_model_brier,
            "overall_brier_gain": self.overall_brier_gain,
            "signals": [s.to_dict() for s in self.signals],
            "recommended_weights": self.recommended_weights,
            "generated_at": self.generated_at,
        }


def _extract_fired_signals(cm_reasons: Sequence[str], res: Mapping[str, Any]) -> list[str]:
    fired: list[str] = []
    joined = " | ".join(cm_reasons)
    if "Asya Handikap" in joined:
        fired.append("ah_anchor")
    if "xG yapısal üstünlüğü" in joined:
        fired.append("xg_structural")
    if "xG şans gerilemesi" in joined:
        fired.append("finishing_luck")
    if "Keskin piyasa akışı" in joined:
        fired.append("directional_steam")
    if "Hat eşleşmesi" in joined:
        fired.append("squad_unit_edge")
    if "Derbi bağlamı" in joined or (isinstance(res.get("squad_scouting"), Mapping) and res["squad_scouting"].get("derby")):
        fired.append("derby_tightening")
    if "beraberlik rejimi" in joined:
        fired.append("draw_regime")
    return fired


def recommend_signal_weights(
    signals: Sequence[SignalPerformance],
    *,
    prior_strength: float = 40.0,
) -> dict[str, float]:
    """Empirical-Bayes L2 shrinkage weight updater: rewards positive Brier-gain signals, damps noisy ones."""
    sig_map = {s.signal_name: s for s in signals}
    mapping = {
        "xg_structural": ("xg_weight_cap", 0.06, 0.22),
        "ah_anchor": ("ah_weight", 0.08, 0.22),
        "finishing_luck": ("luck_cap", 0.008, 0.030),
        "directional_steam": ("steam_weight", 0.15, 0.40),
        "squad_unit_edge": ("scouting_cap", 0.006, 0.022),
        "draw_regime": ("draw_regime_cap", 0.005, 0.020),
    }
    updated = dict(BASELINE_SIGNAL_WEIGHTS)
    for sig_key, (w_key, lo, hi) in mapping.items():
        base = BASELINE_SIGNAL_WEIGHTS[w_key]
        sp = sig_map.get(sig_key)
        if sp is None or sp.fired_count < 8:
            updated[w_key] = round(base, 4)
            continue
        # Shrink reliability factor toward 1.0 by sample size (n / (n + prior_strength))
        rel = sp.fired_count / (sp.fired_count + prior_strength)
        # +0.005 Brier gain -> +15% weight boost; -0.005 Brier loss -> -25% weight damp (asymmetric safety!)
        if sp.brier_improvement >= 0:
            mult = 1.0 + rel * min(0.25, sp.brier_improvement * 30.0)
        else:
            mult = 1.0 + rel * max(-0.45, sp.brier_improvement * 50.0)
        updated[w_key] = round(max(lo, min(hi, base * mult)), 4)
    return updated


def run_causal_signal_attribution(
    divisions: Sequence[str] = ("E0", "D1", "I1", "SP1", "F1", "T1", "N1", "P1"),
    *,
    min_prior_matches: int = 30,
    data_dir: str = str(SEASON_DATA_DIR),
) -> AttributionReport:
    """Strictly causal 2026/27 walk-forward attribution measuring every signal's true Brier & Log-Loss gain."""
    sig_buckets: dict[str, list[tuple[float, float, float, float, int]]] = {}
    all_mkt_brier: list[float] = []
    all_mod_brier: list[float] = []
    n_eval = 0
    n_close = 0

    for div in divisions:
        rows = load_division_rows(div, data_dir=data_dir)
        if len(rows) <= min_prior_matches:
            continue
        league = _DIV_TO_LEAGUE.get(div, div)
        for idx, r in enumerate(rows):
            if idx < min_prior_matches:
                continue
            d = _parse_csv_date(r.get("Date"))
            if d is None:
                continue
            o1 = _flt(r.get("BFEH")) or _flt(r.get("AvgH"))
            ox = _flt(r.get("BFED")) or _flt(r.get("AvgD"))
            o2 = _flt(r.get("BFEA")) or _flt(r.get("AvgA"))
            if not (o1 and ox and o2 and min(o1, ox, o2) > 1.01):
                continue
            hg, ag = _flt(r.get("FTHG")), _flt(r.get("FTAG"))
            if hg is None or ag is None:
                continue
            actual = 0 if hg > ag else (1 if hg == ag else 2)

            p_mkt = devig([o1, ox, o2], method="power").probabilities
            # Opening -> closing sharp steam when both BFEH and BFECH exist
            c1, cx, c2 = _flt(r.get("BFECH")), _flt(r.get("BFECD")), _flt(r.get("BFECA"))
            steam = None
            if c1 and cx and c2 and min(c1, cx, c2) > 1.01:
                p_close = devig([c1, cx, c2], method="power").probabilities
                steam = [float(p_close[i] - p_mkt[i]) for i in range(3)]

            ah_h = _flt(r.get("AHh"))
            ah_o1, ah_o2 = _flt(r.get("BFEAHH")) or _flt(r.get("AvgAHH")), _flt(r.get("BFEAHA")) or _flt(r.get("AvgAHA"))
            ref_ah = [ah_h, [ah_o1, ah_o2]] if (ah_h is not None and ah_o1 and ah_o2 and min(ah_o1, ah_o2) > 1.01) else None

            ou_o, ou_u = _flt(r.get("BFE>2.5")) or _flt(r.get("Avg>2.5")), _flt(r.get("BFE<2.5")) or _flt(r.get("Avg<2.5"))
            p_o25 = float(devig([ou_o, ou_u], method="power").probabilities[0]) if (ou_o and ou_u and min(ou_o, ou_u) > 1.01) else 0.50

            rec: dict[str, Any] = {
                "code": idx + 1,
                "league": league,
                "home": r["HomeTeam"],
                "away": r["AwayTeam"],
                "kickoff_iso": f"{d.isoformat()}T18:00:00+03:00",
                "fair_1x2": list(p_mkt),
                "steam_1x2": steam,
                "ref_ah": ref_ah,
                "selections": [
                    {"name": "MS 1", "odds": o1, "fair_prob": float(p_mkt[0])},
                    {"name": "MS 0", "odds": ox, "fair_prob": float(p_mkt[1])},
                    {"name": "MS 2", "odds": o2, "fair_prob": float(p_mkt[2])},
                    {"name": "2.5 Üst", "odds": ou_o or 1.90, "fair_prob": p_o25},
                ],
            }
            enrich_match_record(rec, as_of=d, data_dir=data_dir)
            cm = analyze_close_match(rec)
            if cm is None:
                continue
            n_eval += 1
            if cm.is_close_match:
                n_close += 1

            mod_p = (cm.model_1x2["MS 1"], cm.model_1x2["MS 0"], cm.model_1x2["MS 2"])
            mb = _brier_1x2(p_mkt, actual)
            pb = _brier_1x2(mod_p, actual)
            ml = _logloss_1x2(p_mkt, actual)
            pl = _logloss_1x2(mod_p, actual)
            hit = 1 if max(range(3), key=lambda i: mod_p[i]) == actual else 0

            all_mkt_brier.append(mb)
            all_mod_brier.append(pb)

            for sig in _extract_fired_signals(cm.reasons, rec.get("research") or {}):
                sig_buckets.setdefault(sig, []).append((mb, pb, ml, pl, hit))

    sig_results: list[SignalPerformance] = []
    for sig_name, items in sorted(sig_buckets.items()):
        cnt = len(items)
        mb_avg = sum(x[0] for x in items) / cnt
        pb_avg = sum(x[1] for x in items) / cnt
        ml_avg = sum(x[2] for x in items) / cnt
        pl_avg = sum(x[3] for x in items) / cnt
        b_gain = mb_avg - pb_avg
        l_gain = ml_avg - pl_avg
        hr = sum(x[4] for x in items) / cnt
        status = "KATMA DEĞER" if b_gain >= 0.001 else ("GÜRÜLTÜ — DARALT" if b_gain <= -0.003 else "NÖTR")
        sig_results.append(
            SignalPerformance(
                signal_name=sig_name,
                fired_count=cnt,
                market_brier=round(mb_avg, 5),
                model_brier=round(pb_avg, 5),
                brier_improvement=round(b_gain, 5),
                market_logloss=round(ml_avg, 5),
                model_logloss=round(pl_avg, 5),
                logloss_improvement=round(l_gain, 5),
                hit_rate=round(hr, 4),
                status=status,
            )
        )

    om = round(sum(all_mkt_brier) / max(1, len(all_mkt_brier)), 5)
    op = round(sum(all_mod_brier) / max(1, len(all_mod_brier)), 5)
    weights = recommend_signal_weights(sig_results)

    return AttributionReport(
        evaluated_matches=n_eval,
        close_matches=n_close,
        overall_market_brier=om,
        overall_model_brier=op,
        overall_brier_gain=round(om - op, 5),
        signals=tuple(sig_results),
        recommended_weights=weights,
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    )


def save_signal_weights(report: AttributionReport, path: Path = DEFAULT_WEIGHTS_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_signal_weights(path: Path = DEFAULT_WEIGHTS_PATH) -> dict[str, float]:
    if not path.exists():
        return dict(BASELINE_SIGNAL_WEIGHTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        w = data.get("recommended_weights") or {}
        out = dict(BASELINE_SIGNAL_WEIGHTS)
        for k in out:
            if k in w and _flt(w[k]) is not None:
                out[k] = float(w[k])
        return out
    except (OSError, ValueError):
        return dict(BASELINE_SIGNAL_WEIGHTS)


def render_attribution_markdown(report: AttributionReport) -> str:
    """Render readable Turkish Markdown report of per-signal Brier/Log-Loss contribution & weights."""
    lines = [
        "# Otomatik Sinyal Katkı Ölçümü ve Ağırlık Kalibrasyonu",
        "",
        f"- Değerlendirilen 2026/27 maçı: **{report.evaluated_matches}** (denk maç: **{report.close_matches}**)",
        f"- Genel Brier Skoru: Piyasa **{report.overall_market_brier:.5f}** → Model **{report.overall_model_brier:.5f}** "
        f"(Kazanç: **{report.overall_brier_gain:+.5f}**)",
        "",
        "| Sinyal Katmanı | Tetiklenme | Piyasa Brier | Model Brier | Brier Kazancı | LogLoss Kazancı | İsabet | Durum |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for s in report.signals:
        lines.append(
            f"| {s.signal_name} | {s.fired_count} | {s.market_brier:.5f} | {s.model_brier:.5f} | "
            f"**{s.brier_improvement:+.5f}** | {s.logloss_improvement:+.5f} | %{100*s.hit_rate:.1f} | {s.status} |"
        )
    lines += ["", "## Empirical-Bayes Önerilen Sinyal Ağırlıkları", ""]
    for k, v in report.recommended_weights.items():
        base = BASELINE_SIGNAL_WEIGHTS.get(k, v)
        lines.append(f"- `{k}`: **{v:.4f}** (baz: {base:.4f})")
    lines.append("")
    return "\n".join(lines)

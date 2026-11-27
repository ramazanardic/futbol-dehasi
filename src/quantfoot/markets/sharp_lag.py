"""Sharp-Lag / Steam Hız Algoritması: keskin borsa akışı karşısında gecikmiş Nesine oranlarını yakalar.

Üç bağımsız sinyal kaynağı:
  1. `history_lag`: `nesine_history.jsonl` anlık görüntülerinde borsa olasılığı ≥+2.5p yükselmişken
     Nesine oranının değişmediği durumlar (saat başına akış hızı `velocity_pp_per_h` ile ölçülür).
  2. `pre_ko_steam`: Açılıştan canlıya `steam_1x2` ≥+3.5p kaymış, maça kısa süre kalmış ve Nesine
     oranı hâlâ değer (`EV >= -0.05`) sunan `MS 1/0/2` fırsatları.
  3. `score_lag`: Keskin para `MS 1` veya `MS 2` yönünde ≥+5.0p kaymışken o tarafın 6 Altın
     Skorlarından (`1-0, 2-0, 2-1` veya `0-1, 0-2, 1-2`) canlı MTID 777 oranı görece yüksek kalanlar.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import datetime as dt
import json
from pathlib import Path
from typing import Any

GOLDEN_HOME = frozenset({"Skor 1-0", "Skor 2-0", "Skor 2-1"})
GOLDEN_AWAY = frozenset({"Skor 0-1", "Skor 0-2", "Skor 1-2"})
TSI = dt.timezone(dt.timedelta(hours=3))


@dataclass(frozen=True)
class SharpLagSignal:
    code: int
    kickoff: str
    league: str
    match: str
    selection: str
    source_kind: str  # "history_lag" | "pre_ko_steam" | "score_lag"
    nesine_odds: float
    fair_prob: float
    ev: float
    steam_pp: float
    velocity_pp_per_h: float | None
    hours_to_ko: float | None
    urgency_score: float
    reason: str


def _flt(v: Any) -> float | None:
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _parse_iso(ts: str | None) -> dt.datetime | None:
    if not ts:
        return None
    try:
        d = dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=TSI)
    except ValueError:
        return None


def load_history_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def scan_sharp_lag(
    matches: Sequence[Mapping[str, Any]],
    history_rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    now: dt.datetime | None = None,
    min_history_move: float = 0.025,
    min_steam_move: float = 0.035,
) -> list[SharpLagSignal]:
    """Bültendeki keskin akış hızı ve gecikmiş Nesine oranı sinyallerini tara."""
    ref_now = now or dt.datetime.now(TSI)
    if ref_now.tzinfo is None:
        ref_now = ref_now.replace(tzinfo=TSI)

    out: list[SharpLagSignal] = []
    hist = list(history_rows or [])

    for m in matches:
        if m.get("status") != "fiyatlandı":
            continue
        code = int(m["code"])
        ko_dt = _parse_iso(m.get("kickoff_iso"))
        hours_to_ko = None
        if ko_dt is not None:
            hours_to_ko = (ko_dt - ref_now).total_seconds() / 3600.0
            if hours_to_ko < -0.1:
                continue  # başlamış maç
        time_mult = 1.45 if (hours_to_ko is not None and hours_to_ko <= 3.0) else (1.18 if (hours_to_ko is not None and hours_to_ko <= 8.0) else 0.90)
        is_sharp = str(m.get("price_tier")) == "keskin"
        tier_bonus = 12.0 if is_sharp else 0.0
        mname = f"{m.get('home', '')} - {m.get('away', '')}"
        ko_str = str(m.get("kickoff") or "")[:16]
        lg = str(m.get("league") or "")
        sels = {s.get("name"): s for s in (m.get("selections") or [])}

        # 1. Geçmiş anlık görüntülere göre oran sabitken artan borsa olasılığı (velocity_pp_per_h)
        if hist:
            for s_name, s in sels.items():
                if not s.get("direct"):
                    continue
                cur_o = _flt(s.get("odds"))
                cur_p = _flt(s.get("fair_prob"))
                cur_ev = _flt(s.get("ev"))
                if cur_o is None or cur_p is None or cur_ev is None:
                    continue
                best_move = 0.0
                best_vel = None
                for snap in hist:
                    snap_ts = _parse_iso(snap.get("ts"))
                    if snap_ts is None:
                        continue
                    dt_h = (ref_now - snap_ts).total_seconds() / 3600.0
                    if dt_h < 0.05 or dt_h > 12.0:
                        continue
                    rec = (snap.get("m") or {}).get(str(code))
                    if not rec or rec.get("ref_t") == m.get("ref_fetched_utc"):
                        continue
                    prev = (rec.get("s") or {}).get(s_name)
                    if not prev or len(prev) < 2:
                        continue
                    prev_o, prev_p = _flt(prev[0]), _flt(prev[1])
                    if prev_o is None or prev_p is None or abs(prev_o - cur_o) > 1e-6:
                        continue
                    mv = cur_p - prev_p
                    if mv >= min_history_move and mv > best_move:
                        best_move = mv
                        best_vel = round((mv * 100.0) / max(dt_h, 0.25), 2)
                if best_move >= min_history_move:
                    urg = min(100.0, (best_move * 100.0 * 7.5 + max(0.0, cur_ev) * 120.0 + tier_bonus) * time_mult)
                    out.append(
                        SharpLagSignal(
                            code=code,
                            kickoff=ko_str,
                            league=lg,
                            match=mname,
                            selection=str(s_name),
                            source_kind="history_lag",
                            nesine_odds=cur_o,
                            fair_prob=cur_p,
                            ev=cur_ev,
                            steam_pp=round(best_move * 100.0, 2),
                            velocity_pp_per_h=best_vel,
                            hours_to_ko=round(hours_to_ko, 2) if hours_to_ko is not None else None,
                            urgency_score=round(urg, 1),
                            reason=f"Nesine @{cur_o:.2f} sabit kaldı, borsa +{best_move*100:.1f}p (hız {best_vel:.1f}p/sa)",
                        )
                    )

        # 2. Açılıştan canlıya güçlü 1X2 steam + gecikmeli taraf/skor
        steam = m.get("steam_1x2")
        if isinstance(steam, (list, tuple)) and len(steam) == 3:
            side_map = ((0, "MS 1"), (1, "MS 0"), (2, "MS 2"))
            for idx, nm in side_map:
                sv = _flt(steam[idx]) or 0.0
                if sv < min_steam_move:
                    continue
                s = sels.get(nm)
                if not s:
                    continue
                cur_o, cur_p, cur_ev = _flt(s.get("odds")), _flt(s.get("fair_prob")), _flt(s.get("ev"))
                if cur_o is None or cur_p is None or cur_ev is None:
                    continue
                if cur_ev >= -0.05:
                    urg = min(100.0, (sv * 100.0 * 5.0 + max(0.0, cur_ev + 0.05) * 180.0 + tier_bonus) * time_mult)
                    out.append(
                        SharpLagSignal(
                            code=code,
                            kickoff=ko_str,
                            league=lg,
                            match=mname,
                            selection=nm,
                            source_kind="pre_ko_steam",
                            nesine_odds=cur_o,
                            fair_prob=cur_p,
                            ev=cur_ev,
                            steam_pp=round(sv * 100.0, 2),
                            velocity_pp_per_h=None,
                            hours_to_ko=round(hours_to_ko, 2) if hours_to_ko is not None else None,
                            urgency_score=round(urg, 1),
                            reason=f"Keskin açılış->canlı akış {nm} +{sv*100:.1f}p (EV {cur_ev*100:+.1f}%)",
                        )
                    )

            # 3. Skor tarafı gecikme sinyali (≥ +5p steam varken canlı MTID 777 skor EV kontrolü)
            s0 = _flt(steam[0]) or 0.0
            s2 = _flt(steam[2]) or 0.0
            target_set = GOLDEN_HOME if s0 >= 0.05 else (GOLDEN_AWAY if s2 >= 0.05 else None)
            sv_dir = s0 if s0 >= 0.05 else s2
            if target_set:
                best_sc = None
                for sc_nm in target_set:
                    s = sels.get(sc_nm)
                    if not s:
                        continue
                    cur_o, cur_p, cur_ev = _flt(s.get("odds")), _flt(s.get("fair_prob")), _flt(s.get("ev"))
                    if cur_o is None or cur_p is None or cur_ev is None or cur_ev < -0.15:
                        continue
                    if best_sc is None or cur_ev > best_sc[3]:
                        best_sc = (sc_nm, cur_o, cur_p, cur_ev)
                if best_sc is not None:
                    sc_nm, cur_o, cur_p, cur_ev = best_sc
                    urg = min(100.0, (sv_dir * 100.0 * 4.0 + (cur_ev + 0.15) * 100.0 + tier_bonus) * time_mult)
                    out.append(
                        SharpLagSignal(
                            code=code,
                            kickoff=ko_str,
                            league=lg,
                            match=mname,
                            selection=sc_nm,
                            source_kind="score_lag",
                            nesine_odds=cur_o,
                            fair_prob=cur_p,
                            ev=cur_ev,
                            steam_pp=round(sv_dir * 100.0, 2),
                            velocity_pp_per_h=None,
                            hours_to_ko=round(hours_to_ko, 2) if hours_to_ko is not None else None,
                            urgency_score=round(urg, 1),
                            reason=f"Taraf steam (+{sv_dir*100:.1f}p) ile uyumlu canlı skor @{cur_o:.2f} (EV {cur_ev*100:+.1f}%)",
                        )
                    )

    out.sort(key=lambda x: (-x.urgency_score, -x.ev))
    return out

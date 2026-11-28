"""Son-120-gün takım formu (ESPN + Open Matchday + Nesine havuzu) -> gol-toplamı seçimleri için öncül.

``gfi_priors.blend`` ile aynı sözleşme: yalnız gol aileleri (Alt/Üst, İY Alt/Üst, KG), iki takımın da formu varsa,
``MODEL_WEIGHT·P + (1-MODEL_WEIGHT)·öncül``. Form YALNIZ maç gününden önceki maçlardan okunur (sızıntı yok).
Varsayılan KAPALI (``settings.RECENT_FORM_ENABLED``, ortam ``QF_RECENT_FORM=1``): 18–28 Kas ölçümünde gol
ailelerinde log-loss farkı −0.0068 ama %95 aralığı sıfırı kapsıyor (reports/research/kaynak_etki_2026-11-28.md).
``QF_RECENT_FORM_XG=1`` form yerine şut tabanlı xG vekilini kullanır (o da anlamlı kazanç vermedi).
"""

from __future__ import annotations

import datetime as dt
import os

from quantfoot.data import recent_form as rf
from quantfoot.markets import gfi_priors as gp
from quantfoot.markets import league_halves as lh

_STATE: dict = {}


def enabled() -> bool:
    from quantfoot import settings

    env = os.environ.get("QF_RECENT_FORM")
    return env == "1" if env is not None else bool(getattr(settings, "RECENT_FORM_ENABLED", False))


def _state(asof: str) -> dict:
    s = _STATE.get(asof)
    if s is None:
        from quantfoot.data import web_research as wr

        pool, _ = wr.refresh_pool(asof, wr.Http())
        use_xg = os.environ.get("QF_RECENT_FORM_XG") == "1"
        if use_xg:
            predict, _n = rf.fit_shot_xg()
            rf.attach_xg_proxy(pool, predict)
        s = {"idx": rf.build_index(pool), "means": rf.pool_means(pool, asof), "cache": {}, "xg": use_xg}
        _STATE.clear()
        _STATE[asof] = s
    return s


def prior(name: str, league: str | None, home: str, away: str, asof: str, state: dict | None = None) -> float | None:
    if not gp.GOAL_FAMILY.match(name) or not home or not away:
        return None
    s = state or _state(asof)
    lam = rf.lambdas(home, away, s["idx"], asof, s["means"], s["cache"], use_xg=s["xg"])
    if lam is None:
        return None
    return gp.selection_probability(name, lam[0], lam[1], gp.first_half_share(league))


def blend(name: str, p_model: float, league: str | None, home: str, away: str, kickoff: dt.datetime | dt.date | None,
          weight: float = lh.MODEL_WEIGHT) -> float:
    """Kapalıyken ya da öncül yokken ``p_model`` aynen döner."""
    if not enabled() or kickoff is None or not gp.GOAL_FAMILY.match(name):
        return p_model
    asof = (kickoff.date() if isinstance(kickoff, dt.datetime) else kickoff).isoformat()
    try:
        pr = prior(name, league, home, away, asof)
    except Exception:  # noqa: BLE001 — ağ/format hatası fiyatlamayı bozmasın
        return p_model
    return p_model if pr is None else weight * p_model + (1.0 - weight) * pr

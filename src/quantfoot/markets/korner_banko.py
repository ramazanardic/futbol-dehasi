"""Toplam korner Alt/Üst — banko kupon ailesi için kalibre model (28 Kas 2026, t179u).

Korner yüksek oran katmanından çıkarıldı; normal banko kurallarıyla (düzeltilmiş P ≥ 0,70, oran 1,20–1,80, maç
başına tek bacak) kupona girebilir. Model:

1. Takım korner beklentisi: zaman ağırlıklı Maher (``yuksek_oran_modeli.fit_maher``; son 3 yıl, yarı ömür 240 gün,
   k = 25), lig bazında, ``data/matches.csv`` HomeCorners/AwayCorners.
2. Toplam beklenti doğrusal düzeltilir: ``a + b · (ev + dep)`` (b < 1 = takım farklarını büzme); katsayılar yalnız
   geçmiş örneklem-dışı satırlarla, aylık ileri-yürüyen (``scripts/korner_olcum.py``).
3. Dağılım: negatif binom, Var/Ort oranı geçmiş artıklardan.

Dosya: ``data/calibration/korner_kalibrasyon.json`` (``scripts/korner_olcum.py`` üretir). Yalnız ileri-yürüyen testte
P ≥ 0,70 diliminde gerçekleşmesi tahminden en çok 5 puan düşük olan (çizgi, yön) çiftleri ``gecerli`` listesindedir;
başka hiçbiri kupona girmez. Takım adı o ligdeki bir takımla eşleşmezse ya da Nesine o seçimi sunmuyorsa bacak çıkmaz.
Korner oranı arşivde yok: kalibrasyon sonuç frekansıyla ölçülür, kâr (ROI) ölçülmedi.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import nbinom, poisson

from quantfoot.data.oddsmath import _norm_team, _team_sim
from quantfoot.markets import yuksek_oran_modeli as ym
from quantfoot.paths import REPO_ROOT

PARAMS_PATH = REPO_ROOT / "data" / "calibration" / "korner_kalibrasyon.json"
MATCHES_PATH = REPO_ROOT / "data" / "matches.csv"

LINES = (6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5)
WINDOW_DAYS = 3 * 365
HALF_LIFE = 240.0
K_CORNER = 25.0
MIN_DIV_ROWS = 150
MIN_TEAM_SIM = 0.86
MAX_TOTAL = 20.0
MIN_TOTAL = 3.0


def nb_over(mean: np.ndarray | float, var_mean: np.ndarray | float, line: float) -> np.ndarray:
    """P(T > line), T ~ NB(ort, Var/Ort oranı); oran <= 1 ise Poisson."""
    mean = np.atleast_1d(np.asarray(mean, float))
    vm = np.broadcast_to(np.asarray(var_mean, float), mean.shape)
    k = math.floor(line)
    out = np.empty_like(mean)
    nbm = vm > 1.0 + 1e-6
    if nbm.any():
        r = mean[nbm] / (vm[nbm] - 1.0)
        out[nbm] = nbinom.sf(k, r, r / (r + mean[nbm]))
    if (~nbm).any():
        out[~nbm] = poisson.sf(k, mean[~nbm])
    return out


def selection_name(line: float, side: str) -> str:
    return f"Korner {line:.1f} {side}"


def parse_selection(name: str) -> tuple[float, str] | None:
    """"Korner 9.5 Üst" -> (9.5, "Üst"). İlk yarı ("İY Korner ...") ve başka adlar None."""
    parts = (name or "").split()
    if len(parts) != 3 or parts[0] != "Korner" or parts[2] not in ("Üst", "Alt"):
        return None
    try:
        line = float(parts[1])
    except ValueError:
        return None
    return (line, parts[2]) if abs(line % 1 - 0.5) < 1e-9 else None


def load_params(path: Path | None = None) -> dict[str, Any]:
    p = path or PARAMS_PATH
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def valid_selections(params: dict[str, Any] | None = None) -> frozenset[str]:
    """Ölçümle doğrulanmış seçimler. Dosya yok ya da ``etkin`` yanlışsa boş."""
    p = params if params is not None else load_params()
    if not p.get("etkin"):
        return frozenset()
    return frozenset(p.get("gecerli") or [])


def flag_on() -> bool:
    """settings.KORNER_BANKO_ENABLED; ortam değişkeni QF_KORNER_BANKO=0/1 ayarı geçersiz kılar."""
    from quantfoot import settings as S

    env = os.environ.get("QF_KORNER_BANKO")
    return env == "1" if env is not None else bool(getattr(S, "KORNER_BANKO_ENABLED", False))


def banko_enabled() -> bool:
    """Bayrak açık ve kalibrasyon dosyası geçerli çizgi içeriyor mu?"""
    return flag_on() and bool(valid_selections())


def banko_name_allowed(name: str) -> bool:
    """Kupon kuralı: yalnız toplam korner Alt/Üst ve yalnız ölçümle doğrulanmış (çizgi, yön)."""
    return parse_selection(name) is not None and flag_on() and name in valid_selections()


@dataclass
class DivisionFit:
    fit: ym.MaherFit
    teams: dict[str, str] = field(default_factory=dict)  # normalize ad -> matches.csv adı
    last: dict[str, pd.Timestamp] = field(default_factory=dict)  # matches.csv adı -> son maç tarihi (bu ligde)


class CornerBankoModel:
    """Maç günü için lig bazlı korner beklentisi ve Alt/Üst olasılığı."""

    def __init__(self, divisions: dict[str, DivisionFit], params: dict[str, Any], asof: date) -> None:
        self.divisions = divisions
        self.params = params
        self.asof = asof
        self._cache: dict[tuple[str, str], tuple[str, str, str] | None] = {}
        self._by_team: dict[str, list[str]] = {}
        for div, d in divisions.items():
            for nt in d.teams:
                self._by_team.setdefault(nt, []).append(div)

    # -- kurulum -----------------------------------------------------------------
    @classmethod
    def from_matches(cls, df: pd.DataFrame, asof: date | datetime | str, params: dict[str, Any] | None = None) -> "CornerBankoModel":
        asof_ts = pd.Timestamp(asof).normalize()
        d = df[(df.MatchDate < asof_ts) & (df.MatchDate >= asof_ts - pd.Timedelta(days=WINDOW_DAYS))]
        d = d[d.HomeCorners.notna() & d.AwayCorners.notna()]
        divisions: dict[str, DivisionFit] = {}
        for div, g in d.groupby("Division"):
            if len(g) < MIN_DIV_ROWS:
                continue
            age = (asof_ts - g.MatchDate).dt.days.to_numpy(float)
            w = 0.5 ** (age / HALF_LIFE)
            fit = ym.fit_maher(g.HomeTeam.to_numpy(), g.AwayTeam.to_numpy(), g.HomeCorners.to_numpy(float),
                               g.AwayCorners.to_numpy(float), w, K_CORNER)
            recent = g[g.MatchDate >= asof_ts - pd.Timedelta(days=400)]  # yalnız güncel kadro takımları eşleşir
            teams = {_norm_team(t): t for t in set(recent.HomeTeam) | set(recent.AwayTeam)}
            last = pd.concat([recent.groupby("HomeTeam").MatchDate.max(), recent.groupby("AwayTeam").MatchDate.max()])
            divisions[div] = DivisionFit(fit, teams, last.groupby(level=0).max().to_dict())
        return cls(divisions, params if params is not None else load_params(), asof_ts.date())

    @classmethod
    def from_repo(cls, asof: date | datetime | str | None = None) -> "CornerBankoModel":
        cols = ["Division", "MatchDate", "HomeTeam", "AwayTeam", "HomeCorners", "AwayCorners"]
        df = pd.read_csv(MATCHES_PATH, usecols=cols, low_memory=False)
        df["MatchDate"] = pd.to_datetime(df["MatchDate"], errors="coerce")
        df = df.dropna(subset=["MatchDate", "HomeTeam", "AwayTeam"])
        return cls.from_matches(df, asof or date.today())

    # -- takım eşleme ------------------------------------------------------------
    def _resolve_one(self, name: str, div: str) -> str | None:
        teams = self.divisions[div].teams
        key = _norm_team(name)
        if key in teams:
            return teams[key]
        best, score, runner = None, 0.0, 0.0
        for nt, raw in teams.items():
            s = _team_sim(name, raw)
            if s > score:
                best, score, runner = raw, s, score
            elif s > runner:
                runner = s
        # güvenli eşleşme: yeterince benzer ve ikinci adaydan belirgin ayrışıyor
        return best if score >= MIN_TEAM_SIM and score - runner >= 0.05 else None

    def resolve(self, home: str, away: str) -> tuple[str, str, str] | None:
        """İki takım da AYNI ligde (matches.csv) bulunursa (lig, ev, dep); yoksa None."""
        key = (home, away)
        if key in self._cache:
            return self._cache[key]
        out, best = None, None
        for div, d in self.divisions.items():
            h = self._resolve_one(home, div)
            if h is None:
                continue
            a = self._resolve_one(away, div)
            if a is None or a == h:
                continue
            # terfi/düşme: iki takımın da EN GÜNCEL oynadığı lig (son maçların en eskisi en yeni olan)
            recency = min(d.last.get(h, pd.Timestamp.min), d.last.get(a, pd.Timestamp.min))
            if best is None or recency > best:
                out, best = (div, h, a), recency
        self._cache[key] = out
        return out

    # -- olasılık ----------------------------------------------------------------
    def expected_total(self, home: str, away: str) -> tuple[str, float] | None:
        r = self.resolve(home, away)
        coef = self.params.get("katsayi")
        if r is None or not coef:
            return None
        div, h, a = r
        eh, ea = self.divisions[div].fit.expect(h, a)
        return div, float(np.clip(coef[0] + coef[1] * (eh + ea), MIN_TOTAL, MAX_TOTAL))

    def probability(self, home: str, away: str, name: str) -> float | None:
        """P(seçim) ya da None (seçim tanınmıyor, takım eşleşmiyor, kalibrasyon yok)."""
        sel = parse_selection(name)
        if sel is None or name not in valid_selections(self.params):
            return None
        et = self.expected_total(home, away)
        if et is None:
            return None
        line, side = sel
        p_over = float(nb_over(et[1], float(self.params.get("var_ort", 1.15)), line)[0])
        return p_over if side == "Üst" else 1.0 - p_over


# -- derin kontrol için takımın gerçek korner geçmişi ------------------------------------------------------------
N_HISTORY = 10          # takım başına bakılan son maç
MIN_HISTORY = 6         # derin kontrolün kanıt saydığı en az maç (derin_arastirma.verdict ile aynı)
HISTORY_MAX_AGE_DAYS = 120


def _load_corner_games(path: Path | None = None) -> pd.DataFrame:
    cols = ["Division", "MatchDate", "HomeTeam", "AwayTeam", "HomeCorners", "AwayCorners"]
    df = pd.read_csv(path or MATCHES_PATH, usecols=cols, low_memory=False)
    df["MatchDate"] = pd.to_datetime(df["MatchDate"], errors="coerce")
    df = df.dropna(subset=["MatchDate", "HomeTeam", "AwayTeam", "HomeCorners", "AwayCorners"])
    return df


def team_corner_totals(df: pd.DataFrame, team: str, division: str, asof: date | datetime | str,
                       n: int = N_HISTORY, max_age_days: int = HISTORY_MAX_AGE_DAYS) -> list[float]:
    """Takımın o ligdeki son ``n`` maçının TOPLAM korner sayısı (kendi + rakip), ``asof`` öncesi ve en çok
    ``max_age_days`` gün eski. Korner verisi olmayan maç sayılmaz; veri yoksa liste kısa/boş kalır."""
    asof_ts = pd.Timestamp(asof).normalize()
    g = df[(df.Division == division) & (df.MatchDate < asof_ts) & (df.MatchDate >= asof_ts - pd.Timedelta(days=max_age_days))
           & ((df.HomeTeam == team) | (df.AwayTeam == team))].sort_values("MatchDate").tail(n)
    return [float(h) + float(a) for h, a in zip(g.HomeCorners, g.AwayCorners)]


def leg_history(model: CornerBankoModel, df: pd.DataFrame, home: str, away: str, name: str,
                asof: date | datetime | str) -> dict | None:
    """``derin_arastirma.leg_history`` ile aynı şemada geçmiş özeti, ama takımların GERÇEK toplam korner sayılarından:
    ``home_rate`` / ``away_rate`` = seçimin o takımın son maçlarında tutma oranı. Seçim tanınmıyor ya da takımlar
    ligde eşleşmiyorsa None (bacak kanıtsız sayılır)."""
    sel = parse_selection(name)
    r = model.resolve(home, away)
    if sel is None or r is None:
        return None
    line, side = sel
    div, h, a = r
    out: dict = {"division": div, "home_team": h, "away_team": a}
    rates = []
    for key, team in (("home", h), ("away", a)):
        tot = team_corner_totals(df, team, div, asof)
        hits = [(t > line) if side == "Üst" else (t < line) for t in tot]
        out[f"{key}_n"] = len(tot)
        out[f"{key}_rate"] = sum(hits) / len(hits) if hits else None
        out[f"{key}_avg_corners"] = sum(tot) / len(tot) if tot else None
        out[f"{key}_venue_rate"], out[f"{key}_venue_n"] = None, 0
        rates.append(out[f"{key}_rate"])
    vals = [x for x in rates if x is not None]
    out["mean"] = sum(vals) / len(vals) if vals else None
    out["min_side"] = min(rates) if len(vals) == 2 else None
    return out


@lru_cache(maxsize=1)
def default_model() -> CornerBankoModel | None:
    """Günlük akış için tek örnek; kapalıysa / veri yoksa None."""
    if not banko_enabled() or not MATCHES_PATH.exists():
        return None
    return CornerBankoModel.from_repo()

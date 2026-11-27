"""Kulüp bazlı 1. yarı / 2. yarı temposu ve geri dönüş DNA katsayıları (Empirical Bayes).

Zaman-ağırlıklı tarihsel arşiv (data/matches.csv + güncel sezon CSV'leri) üzerinden her kulüp
için 5 davranışsal oran ölçer:
  1. first_half_share: Takımın toplam gollerinin 1. yarıdaki payı (prior 0.440)
  2. early_score_rate: 1. yarıda en az 1 gol bulma oranı (prior 0.470)
  3. lead_hold_vuln:   1. yarıyı önde kapattığı maçlarda 2. yarı gol yeme / avantaj kaybetme riski (prior 0.450)
  4. comeback_rate:    1. yarıyı geride kapattığı maçlarda 2. yarı puan/galibiyet çevirme gücü (prior 0.340)
  5. both_halves_rate: Hem 1. hem 2. yarıda gol atma/yeme temposu (prior 0.190)

Bu katsayılar omni_markets.compute_omni_markets içindeki 1Y/2Y paylaşımını ve devre-arası
oyun durumu tepki çarpanlarını (`GAME_STATE_MULTS`) kulübe özel ince ayarlar.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import difflib
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata

from quantfoot.paths import REPO_ROOT

CALIBRATION_PATH = REPO_ROOT / "data" / "calibration" / "club_half_dna.json"

PRIOR_1H_SHARE = 0.440
PRIOR_EARLY_SCORE = 0.470
PRIOR_LEAD_HOLD_VULN = 0.450
PRIOR_COMEBACK = 0.340
PRIOR_BOTH_HALVES = 0.190

# omni_markets.GAME_STATE_MULTS varsayılan tabanı (bağımsız kopya, döngüsel import yok)
_BASE_STATE_MULTS: dict[str, tuple[float, float]] = {
    "00": (0.965, 0.955),
    "tied_g": (1.025, 1.025),
    "h_plus1": (0.960, 1.095),
    "a_plus1": (1.105, 0.955),
    "h_plus2": (1.030, 0.990),
    "a_plus2": (0.990, 1.040),
}

_STOP_RE = re.compile(
    r"\b(fc|cf|sc|ac|sk|fk|nk|cd|ca|club|de|da|the|utd|united|sv|vfb|tsg|rc|ud|ad|sd|sp|bk|"
    r"if|ik|afc|ssc|as|us|ss|uc|cs|cr|al|el|gnk|hnk|pfc|cska|bsc|tsv|sg|fsv)\b"
)
_TEAM_ALIASES = {
    "man utd": "manchester united",
    "man city": "manchester city",
    "spurs": "tottenham",
    "wolves": "wolverhampton",
    "psg": "paris saint germain",
    "bayern": "bayern munich",
    "m gladbach": "monchengladbach",
    "gladbach": "monchengladbach",
    "inter": "inter milan",
    "gs": "galatasaray",
    "fb": "fenerbahce",
    "bjk": "besiktas",
}


def normalize_club_name(name: str | None) -> str:
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"\(k\)|\(kol\)|\(w\)|\(u\d+\)", " ", s)
    raw = " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())
    if raw in _TEAM_ALIASES:
        raw = _TEAM_ALIASES[raw]
    cleaned = " ".join(re.sub(_STOP_RE, " ", raw).split())
    return _TEAM_ALIASES.get(cleaned, cleaned)


@dataclass(frozen=True)
class ClubHalfDNA:
    club: str
    n_eff: float
    first_half_share: float = PRIOR_1H_SHARE
    early_score_rate: float = PRIOR_EARLY_SCORE
    lead_hold_vuln: float = PRIOR_LEAD_HOLD_VULN
    comeback_rate: float = PRIOR_COMEBACK
    both_halves_rate: float = PRIOR_BOTH_HALVES


@lru_cache(maxsize=1)
def load_club_half_dna(path: Path | None = None) -> dict[str, ClubHalfDNA]:
    """Kalibre kulüp 1Y/2Y DNA tablosunu yükle; dosya yoksa boş dict döndür."""
    p = path or CALIBRATION_PATH
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    clubs = raw.get("clubs") if isinstance(raw, dict) else raw
    if not isinstance(clubs, dict):
        return {}
    out: dict[str, ClubHalfDNA] = {}
    for k, v in clubs.items():
        if not isinstance(v, dict):
            continue
        key = normalize_club_name(k)
        if not key:
            continue
        out[key] = ClubHalfDNA(
            club=str(v.get("club") or k),
            n_eff=float(v.get("n_eff", 0.0)),
            first_half_share=float(v.get("first_half_share", PRIOR_1H_SHARE)),
            early_score_rate=float(v.get("early_score_rate", PRIOR_EARLY_SCORE)),
            lead_hold_vuln=float(v.get("lead_hold_vuln", PRIOR_LEAD_HOLD_VULN)),
            comeback_rate=float(v.get("comeback_rate", PRIOR_COMEBACK)),
            both_halves_rate=float(v.get("both_halves_rate", PRIOR_BOTH_HALVES)),
        )
    return out


@lru_cache(maxsize=4096)
def _lookup_cached(norm_q: str) -> ClubHalfDNA | None:
    table = load_club_half_dna()
    if not norm_q or not table:
        return None
    if norm_q in table:
        return table[norm_q]
    q_tokens = set(norm_q.split())
    best_k = None
    best_score = 0.0
    for k in table:
        ratio = difflib.SequenceMatcher(None, norm_q, k).ratio()
        kt = set(k.split())
        jacc = len(q_tokens & kt) / max(1, len(q_tokens | kt))
        sub = 0.86 if (min(len(norm_q), len(k)) >= 5 and (norm_q in k or k in norm_q)) else 0.0
        sc = max(ratio, jacc, sub)
        if sc > best_score:
            best_score = sc
            best_k = k
    return table[best_k] if (best_k is not None and best_score >= 0.84) else None


def lookup_club_dna(
    team_name: str | None,
    table: Mapping[str, ClubHalfDNA] | None = None,
) -> ClubHalfDNA | None:
    """Kulüp adından ClubHalfDNA kaydını bul (normalize + fuzzy eşleme)."""
    nq = normalize_club_name(team_name)
    if not nq:
        return None
    if table is None:
        return _lookup_cached(nq)
    if nq in table:
        return table[nq]
    best_v: ClubHalfDNA | None = None
    best_sc = 0.0
    for k, v in table.items():
        nk = normalize_club_name(k)
        sc = difflib.SequenceMatcher(None, nq, nk).ratio()
        if min(len(nq), len(nk)) >= 5 and (nq in nk or nk in nq):
            sc = max(sc, 0.86)
        if sc > best_sc:
            best_sc = sc
            best_v = v
    return best_v if best_sc >= 0.84 else None


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def club_omni_adjustments(
    home: str | None,
    away: str | None,
    table: Mapping[str, ClubHalfDNA] | None = None,
) -> tuple[float, float, dict[str, tuple[float, float]] | None]:
    """omni_markets.compute_omni_markets için (home_1h_shift, away_1h_shift, state_mults) üret."""
    hd = lookup_club_dna(home, table)
    ad = lookup_club_dna(away, table)
    if hd is None and ad is None:
        return 0.0, 0.0, None

    h_shift = _clip((hd.first_half_share - PRIOR_1H_SHARE) * 0.65, -0.045, 0.045) if (hd and hd.n_eff >= 6.0) else 0.0
    a_shift = _clip((ad.first_half_share - PRIOR_1H_SHARE) * 0.65, -0.045, 0.045) if (ad and ad.n_eff >= 6.0) else 0.0

    mults = dict(_BASE_STATE_MULTS)
    h_vuln = hd.lead_hold_vuln if (hd and hd.n_eff >= 6.0) else PRIOR_LEAD_HOLD_VULN
    a_vuln = ad.lead_hold_vuln if (ad and ad.n_eff >= 6.0) else PRIOR_LEAD_HOLD_VULN
    h_cb = hd.comeback_rate if (hd and hd.n_eff >= 6.0) else PRIOR_COMEBACK
    a_cb = ad.comeback_rate if (ad and ad.n_eff >= 6.0) else PRIOR_COMEBACK

    # Ev 1Y +1 önde -> Dep 2Y baskısı & Ev 2Y koruma zaafı
    hp1_away = _clip(1.095 + (h_vuln - PRIOR_LEAD_HOLD_VULN) * 0.12 + (a_cb - PRIOR_COMEBACK) * 0.15, 0.85, 1.25)
    hp1_home = _clip(0.960 + (h_vuln - PRIOR_LEAD_HOLD_VULN) * 0.05, 0.85, 1.25)
    mults["h_plus1"] = (round(hp1_home, 4), round(hp1_away, 4))

    # Dep 1Y +1 önde -> Ev 2Y baskısı & Dep 2Y koruma zaafı
    ap1_home = _clip(1.105 + (a_vuln - PRIOR_LEAD_HOLD_VULN) * 0.12 + (h_cb - PRIOR_COMEBACK) * 0.15, 0.85, 1.25)
    ap1_away = _clip(0.955 + (a_vuln - PRIOR_LEAD_HOLD_VULN) * 0.05, 0.85, 1.25)
    mults["a_plus1"] = (round(ap1_home, 4), round(ap1_away, 4))

    return round(h_shift, 5), round(a_shift, 5), mults

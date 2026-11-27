"""Oyuncu Bazlı Gol Atar / Kart Görür (Player Props) ve Avrupa Kupası / Seyahat Bağlam Motoru.

1. **Oyuncu Gol Atar (Anytime Goalscorer):**
   Takımın beklenen gol oranını (``team_mu``), kadrodaki oyuncuların sezonluk gol/asist/şut payı ve
   son 5 maçlık sıcak form payına Empirical-Bayes düzeltmesiyle dağıtır:
   ``P(oyuncu >= 1 gol) = 1 - exp(-lambda_player)`` -> adil oran ve gol olasılığı üretir.
2. **Oyuncu Kart Görür (Anytime Card Prop):**
   Oyuncunun maç başı sarı/kırmızı kart oranını, maçın hakem kart z-skoru ve derbi sertlik
   katsayısıyla ölçekler -> en yüksek kart riskli oyuncuları adil oranlarıyla çıkarır.
3. **Avrupa Kupası Yorgunluğu (UCL/UEL/UECL Hangover) & Deplasman Seyahat Mesafesi:**
   Son maçında Avrupa kupası oynayıp <= 4 gün dinlenen takımlarda ampirik yorgunluk uyarısı ve
   bilinen şehir koordinatlarından Haversine uçuş mesafesi (km) hesaplar.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
import math
import re
from typing import Any
import unicodedata


def _flt(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        v = float(val)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _norm(text: str) -> str:
    tr = str.maketrans("İIıŞşĞğÜüÖöÇç", "iiissgguuoocc")
    s = unicodedata.normalize("NFKD", (text or "").translate(tr)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# --------------------------------------------------------------------------- #
# 1. Oyuncu Gol Atar & Kart Görür (Anytime Goalscorer & Card Props)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PlayerGoalProp:
    name: str
    team: str
    position: str
    expected_goals: float
    prob_anytime_goal: float
    fair_odds: float
    season_goals: int
    recent_goals: int
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlayerCardProp:
    name: str
    team: str
    position: str
    prob_card: float
    fair_odds: float
    season_yellows: int
    season_reds: int
    apps: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def predict_team_goalscorers(
    team_name: str,
    team_mu: float,
    team_rec: Mapping[str, Any] | None,
    *,
    tm_side: Mapping[str, Any] | None = None,
    top_k: int = 4,
) -> list[PlayerGoalProp]:
    """Estimate anytime goalscorer probabilities by distributing team_mu across active attackers/midfielders."""
    mu = max(0.20, float(team_mu))
    t = team_rec or {}
    prof = t.get("profile") or {}
    recent = t.get("recent_player_form") or {}
    tm = tm_side or {}

    # Collect unavailable players to exclude from goalscorer pool
    absent_names: set[str] = set()
    for p in (t.get("missing_regulars") or []) + (t.get("likely_absent") or []):
        if isinstance(p, Mapping) and p.get("name"):
            if "rotasyon" not in str(p.get("reason") or "").lower():
                absent_names.add(_norm(str(p["name"])))
    for p in tm.get("critical_absences") or tm.get("injuries") or []:
        if isinstance(p, Mapping) and (p.get("name") or p.get("player")):
            absent_names.add(_norm(str(p.get("name") or p.get("player"))))

    # Gather candidate scorers from season profile + recent 5-match form + TM top scorers
    candidates: dict[str, dict[str, Any]] = {}

    def _upsert(name: str, pos: str = "", goals: int = 0, assists: int = 0, apps: int = 0, shots: int = 0) -> dict[str, Any]:
        nk = _norm(name)
        rec = candidates.setdefault(
            nk,
            {
                "name": name,
                "pos": pos,
                "season_goals": 0,
                "season_assists": 0,
                "apps": 0,
                "shots": 0,
                "recent_goals": 0,
                "recent_sot": 0,
            },
        )
        if pos and not rec["pos"]:
            rec["pos"] = pos
        rec["season_goals"] = max(rec["season_goals"], int(goals or 0))
        rec["season_assists"] = max(rec["season_assists"], int(assists or 0))
        rec["apps"] = max(rec["apps"], int(apps or 0))
        rec["shots"] = max(rec["shots"], int(shots or 0))
        return rec

    for p in prof.get("top_scorers") or []:
        if p.get("name"):
            _upsert(p["name"], p.get("pos", "F"), p.get("goals", 0), p.get("assists", 0), p.get("apps", 0), p.get("shots", 0))
    for ln in ("F", "M"):
        for p in ((prof.get("by_position") or {}).get(ln) or {}).get("top_players") or []:
            if p.get("name"):
                _upsert(p["name"], p.get("pos", ln), p.get("goals", 0), p.get("assists", 0), p.get("apps", 0), p.get("shots", 0))
    for p in tm.get("top_scorers") or []:
        if p.get("name"):
            _upsert(p["name"], p.get("pos", "F"), p.get("goals", 0), p.get("assists", 0), p.get("apps", 0))

    for p in recent.get("hot_players") or []:
        if p.get("name"):
            rec = _upsert(p["name"], p.get("pos", ""))
            rec["recent_goals"] = max(rec["recent_goals"], int(p.get("goals") or 0))
            rec["recent_sot"] = max(rec["recent_sot"], int(p.get("sot") or 0))

    # Remove confirmed/likely absent players
    active = [c for nk, c in candidates.items() if nk and nk not in absent_names and (c["season_goals"] > 0 or c["recent_goals"] > 0 or c["recent_sot"] >= 3)]
    if not active:
        return []

    # Team total season goals (denominator for empirical share; falls back safely)
    sea = t.get("season") or {}
    team_sea_goals = _flt(sea.get("goals_for"))
    sum_cand_goals = sum(c["season_goals"] for c in active)
    denom_goals = max(float(team_sea_goals or 0.0), sum_cand_goals * 1.35, 10.0)

    out: list[PlayerGoalProp] = []
    for c in active:
        # Season goal share with Bayesian shrinkage
        sea_share = (c["season_goals"] + 0.8) / (denom_goals + 3.5)
        # Recent 5-match momentum multiplier (bounded [0.85, 1.30])
        hot_mult = _clip(1.0 + 0.09 * c["recent_goals"] + 0.02 * c["recent_sot"], 0.88, 1.32)
        # Cap individual share at realistic club-football ceiling (0.48 even for Haaland/Osimhen)
        eff_share = _clip(sea_share * hot_mult, 0.04, 0.48)
        lam = round(mu * eff_share, 3)
        p_any = round(_clip(1.0 - math.exp(-lam), 0.03, 0.78), 4)
        note = "sıcak form" if c["recent_goals"] >= 2 else ("ana golcü" if c["season_goals"] >= 6 else "ikincil tehdit")
        out.append(
            PlayerGoalProp(
                name=c["name"],
                team=team_name,
                position=c["pos"] or "F",
                expected_goals=lam,
                prob_anytime_goal=p_any,
                fair_odds=round(1.0 / p_any, 2),
                season_goals=c["season_goals"],
                recent_goals=c["recent_goals"],
                note=note,
            )
        )
    out.sort(key=lambda x: (-x.prob_anytime_goal, -x.season_goals))
    return out[:top_k]


def predict_team_card_risks(
    team_name: str,
    team_rec: Mapping[str, Any] | None,
    *,
    referee_card_zscore: float = 0.0,
    derby_card_boost: float = 1.0,
    top_k: int = 3,
) -> list[PlayerCardProp]:
    """Estimate anytime yellow/red card probabilities for key aggressive players."""
    t = team_rec or {}
    prof = t.get("profile") or {}
    cards = prof.get("cards") or []
    if not cards:
        return []

    ref_mult = _clip(1.0 + 0.14 * float(referee_card_zscore), 0.75, 1.40)
    env_mult = ref_mult * _clip(float(derby_card_boost), 1.0, 1.35)

    out: list[PlayerCardProp] = []
    for p in cards:
        name = p.get("name")
        if not name:
            continue
        apps = max(1, int(p.get("apps") or 10))
        y = int(p.get("yellow") or 0)
        r = int(p.get("red") or 0)
        # Empirical-Bayes shrunk card rate per match (prior: 0.18 cards/match over 5 virtual games)
        base_rate = (y + 1.5 * r + 5.0 * 0.18) / (apps + 5.0)
        lam = _clip(base_rate * env_mult, 0.06, 0.75)
        p_card = round(_clip(1.0 - math.exp(-lam), 0.06, 0.58), 4)
        out.append(
            PlayerCardProp(
                name=str(name),
                team=team_name,
                position=str(p.get("pos") or "M"),
                prob_card=p_card,
                fair_odds=round(1.0 / p_card, 2),
                season_yellows=y,
                season_reds=r,
                apps=apps,
            )
        )
    out.sort(key=lambda x: (-x.prob_card, -(x.season_yellows + 2 * x.season_reds)))
    return out[:top_k]


# --------------------------------------------------------------------------- #
# 2. Avrupa Kupası Yorgunluğu (Hangover) & Deplasman Seyahat Mesafesi
# --------------------------------------------------------------------------- #

# Coordinates (lat, lon) for major Turkish & European club cities (Haversine distance km)
_CLUB_COORDS: dict[str, tuple[float, float]] = {
    "besiktas": (41.04, 29.00), "galatasaray": (41.10, 28.99), "fenerbahce": (40.99, 29.04),
    "basaksehir": (41.12, 28.81), "kasimpasa": (41.03, 28.97), "eyupspor": (41.05, 28.93),
    "trabzonspor": (41.00, 39.72), "samsunspor": (41.29, 36.33), "goztepe": (38.40, 27.08),
    "antalyaspor": (36.88, 30.70), "alanyaspor": (36.54, 32.00), "konyaspor": (37.94, 32.49),
    "kayserispor": (38.74, 35.42), "sivasspor": (39.73, 36.98), "gaziantep": (37.12, 37.38),
    "hatayspor": (36.20, 36.16), "rizespor": (41.02, 40.52), "adana demirspor": (37.06, 35.35),
    "bodrum": (37.04, 27.43), "ankaragucu": (39.94, 32.85),
    "arsenal": (51.55, -0.11), "chelsea": (51.48, -0.19), "tottenham": (51.60, -0.07),
    "liverpool": (53.43, -2.96), "everton": (53.44, -2.97), "manchester city": (53.48, -2.20),
    "manchester united": (53.46, -2.29), "newcastle": (54.98, -1.62), "aston villa": (52.51, -1.88),
    "real madrid": (40.45, -3.69), "atletico madrid": (40.44, -3.60), "barcelona": (41.38, 2.12),
    "sevilla": (37.38, -5.97), "real betis": (37.36, -5.98), "athletic bilbao": (43.26, -2.95),
    "valencia": (39.47, -0.36), "villarreal": (39.94, -0.10),
    "inter": (45.48, 9.12), "milan": (45.48, 9.12), "juventus": (45.11, 7.64),
    "napoli": (40.83, 14.19), "roma": (41.93, 12.45), "lazio": (41.93, 12.45), "atalanta": (45.71, 9.68),
    "bayern": (48.22, 11.62), "dortmund": (51.49, 7.45), "leverkusen": (51.04, 7.00), "leipzig": (51.35, 12.35),
    "psg": (48.84, 2.25), "marseille": (43.27, 5.40), "lyon": (45.77, 4.98), "monaco": (43.73, 7.42),
    "ajax": (52.31, 4.94), "psv": (51.44, 5.47), "feyenoord": (51.89, 4.52),
    "benfica": (38.75, -9.18), "sporting": (38.76, -9.16), "porto": (41.16, -8.58),
    "celtic": (55.85, -4.21), "rangers": (55.85, -4.31),
    "olympiacos": (37.95, 23.66), "panathinaikos": (37.99, 23.75),
}

_EURO_KEYWORDS = re.compile(
    r"champions|europa|conference|ucl|uel|uecl|şampiyonlar|avrupa ligi|konferans", re.I
)


def _haversine_km(c1: tuple[float, float], c2: tuple[float, float]) -> float:
    r = 6371.0
    lat1, lon1 = math.radians(c1[0]), math.radians(c1[1])
    lat2, lon2 = math.radians(c2[0]), math.radians(c2[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(min(1.0, a))), 1)


def _lookup_coords(team: str) -> tuple[float, float] | None:
    nt = _norm(team)
    if nt in _CLUB_COORDS:
        return _CLUB_COORDS[nt]
    for tok, coord in _CLUB_COORDS.items():
        if tok in nt:
            return coord
    return None


def assess_match_props_and_context(rec: Mapping[str, Any]) -> dict[str, Any]:
    """Compute player anytime-goal/card props + European cup hangover + travel distance for a match record."""
    home = str(rec.get("home") or "")
    away = str(rec.get("away") or "")
    league = str(rec.get("league") or "")
    mu_h = _flt(rec.get("mu_home")) or 1.40
    mu_a = _flt(rec.get("mu_away")) or 1.15
    res = rec.get("research") or {}
    teams = res.get("teams") or {}
    tm = res.get("tm_absences") or {}
    ref_prof = res.get("referee_profile") or {}
    ref_z = _flt(ref_prof.get("card_zscore")) if isinstance(ref_prof, Mapping) else 0.0
    scout = res.get("squad_scouting") or {}
    derby = scout.get("derby") if isinstance(scout, Mapping) else None
    derby_boost = float(derby.get("card_intensity_boost", 1.0)) if isinstance(derby, Mapping) else 1.0

    h_scorers = predict_team_goalscorers(home, mu_h, teams.get("home"), tm_side=tm.get("home"))
    a_scorers = predict_team_goalscorers(away, mu_a, teams.get("away"), tm_side=tm.get("away"))
    h_cards = predict_team_card_risks(home, teams.get("home"), referee_card_zscore=ref_z or 0.0, derby_card_boost=derby_boost)
    a_cards = predict_team_card_risks(away, teams.get("away"), referee_card_zscore=ref_z or 0.0, derby_card_boost=derby_boost)

    # Travel distance between clubs
    ch, ca = _lookup_coords(home), _lookup_coords(away)
    dist_km = _haversine_km(ch, ca) if (ch and ca) else None

    # European hangover detection (domestic league match <= 4.0 days after a continental game)
    context_flags: list[str] = []
    is_domestic = not bool(_EURO_KEYWORDS.search(league))
    hangover_side: str | None = None
    if is_domestic:
        for side, name in (("home", home), ("away", away)):
            t = teams.get(side) or {}
            rest = _flt(t.get("rest_days"))
            last5 = t.get("last5") or []
            news = " ".join(str(x) for x in (t.get("news_flags") or []) + (res.get("news") or []))
            had_euro_clue = bool(_EURO_KEYWORDS.search(news)) or (
                rest is not None and rest <= 3.5 and any("vs" in str(x).lower() or "@" in str(x).lower() for x in last5[:1])
            )
            if rest is not None and rest <= 3.8 and had_euro_clue:
                hangover_side = side if hangover_side is None else "both"
                context_flags.append(f"Avrupa / sıkışık fikstür yorgunluğu ({name}: {rest:.1f} gün dinlenme)")

    if dist_km is not None and dist_km >= 1000.0:
        context_flags.append(f"Uzun deplasman yolculuğu ({away}: ~{dist_km:.0f} km)")

    return {
        "home_goalscorers": [p.to_dict() for p in h_scorers],
        "away_goalscorers": [p.to_dict() for p in a_scorers],
        "home_card_risks": [p.to_dict() for p in h_cards],
        "away_card_risks": [p.to_dict() for p in a_cards],
        "travel_distance_km": dist_km,
        "hangover_side": hangover_side,
        "context_flags": context_flags,
    }


def render_player_props_markdown(props: Mapping[str, Any], home: str, away: str) -> list[str]:
    """Render Turkish Markdown section for Anytime Goalscorer / Card Props & Travel Context."""
    hs = props.get("home_goalscorers") or []
    as_ = props.get("away_goalscorers") or []
    hc = props.get("home_card_risks") or []
    ac = props.get("away_card_risks") or []
    flags = props.get("context_flags") or []
    dist = props.get("travel_distance_km")
    if not (hs or as_ or hc or ac or flags or dist):
        return []

    lines = ["## Oyuncu Gol/Kart Tahminleri ve Seyahat Bağlamı", ""]
    if hs or as_:
        lines += [
            "| Takım | Gol Adayı | Beklenen Gol | Gol Atar P | Adil Oran | Sezon / Son 5M | Not |",
            "|---|---|---:|---:|---:|---|---|",
        ]
        for p in (hs[:3] + as_[:3]):
            lines.append(
                f"| {p['team']} | **{p['name']}** ({p['position']}) | {p['expected_goals']:.2f} | "
                f"**%{100*p['prob_anytime_goal']:.1f}** | {p['fair_odds']:.2f} | "
                f"{p['season_goals']}G / {p['recent_goals']}G | {p['note']} |"
            )
        lines.append("")
    if hc or ac:
        c_str = " · ".join(
            f"{p['name']} ({p['team']}: %{100*p['prob_card']:.0f}, adil {p['fair_odds']:.2f})"
            for p in (hc[:2] + ac[:2])
        )
        lines.append(f"- **Kart görme riski en yüksek oyuncular:** {c_str}")
    if dist is not None:
        lines.append(f"- **Deplasman seyahat mesafesi:** ~{dist:.0f} km")
    for fl in flags:
        lines.append(f"- **Bağlam uyarısı:** {fl}")
    lines.append("")
    return lines

"""Derin Kadro Hatları (Kaleci / Defans / Orta Saha / Forvet), Oyuncu Formu ve Taktik Eşleşme Motoru.

Herhangi bir futbol maçında (ör. Beşiktaş - Galatasaray derbisi veya günün tüm bülteni):
1. **Kaleci Hattı (0–100):** Sezon kurtarış %, maç başı yenen gol, xGA − GA (PSxG-benzeri kurtarış katkısı),
   son 5 maç kaleci formu ve 1. kaleci eksikliğinde yedek kaleci kalite düşüşü.
2. **Defans Hattı (0–100):** Sezonluk xGA, rakibe verilen şut & isabetli şut, gol yemeden biten maç oranı,
   top kapma başarısı ve defans hattındaki düzenli eksik/sakat/cezalı oyuncular.
3. **Orta Saha Hattı (0–100):** Topa sahip olma, pas isabeti, şut/korner hakimiyeti (saha kontrolü),
   orta saha oyuncularının gol + asist üretimi, faul/kart disiplini ve orta saha eksikleri.
4. **Forvet / Hücum Hattı (0–100):** Sezonluk xGF, maç başı gol, net pozisyon üretimi, isabetli şut
   dönüşümü, golcü/asistçilerin sezon + son 5 maç form ivmesi ve gol kralı/forvet eksikleri.
5. **Taktik Eşleşme Matrisi & Derbi / Bağlam Zekâsı:**
   - Ev Hücum vs Dep Defans+Kaleci, Dep Hücum vs Ev Defans+Kaleci, Orta Saha Kontrolü, Kaleci Farkı,
     Duran Top/Korner Üstünlüğü, Maç Tempo Endeksi (0–100), Oyun Stili profili.
   - Türkiye ve dünya derbileri (BJK–GS, FB–GS, BJK–FB, El Clásico, Kuzey Londra, Milano, Old Firm vb.)
     için otomatik derbi yoğunluk & kart/marj sıkılaşma katsayısı.
6. **Sınırlı & Kalibrasyon-Güvenli Algoritma Entegrasyonu:**
   Keskin piyasa ile çifte sayım yapmamak için ``scouting_edge_1x2`` maks ±%2.2,
   ``scouting_goal_mult`` maks [0.95, 1.05] aralığında güvenli ve veri kapsamına göre ölçekli tutulur.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
import math
import re
from typing import Any
import unicodedata


def _flt(val: Any) -> float | None:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        v = float(val)
        return v if math.isfinite(v) else None
    s = str(val).strip().replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        v = float(m.group(0))
        return v if math.isfinite(v) else None
    except ValueError:
        return None


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _norm(text: str) -> str:
    tr = str.maketrans("İIıŞşĞğÜüÖöÇç", "iiissgguuoocc")
    s = unicodedata.normalize("NFKD", (text or "").translate(tr)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _pos_group(pos: str) -> str:
    p = (pos or "").strip().upper()
    if not p:
        return "U"
    if p.startswith(("G", "KAL")):
        return "G"
    if p.startswith(("D", "CB", "LB", "RB", "WB", "SW", "FB", "DEF", "STOPER", "BEK")):
        return "D"
    if p.startswith(("M", "CM", "DM", "AM", "LM", "RM", "ORTA", "MID")):
        return "M"
    if p.startswith(("F", "ST", "CF", "LW", "RW", "SS", "W", "FORV", "KANAT", "ATT", "STR")):
        return "F"
    return "U"


# --------------------------------------------------------------------------- #
# 1. Derbi & Büyük Rekabet Tespiti (Türkiye + Dünya)
# --------------------------------------------------------------------------- #

_RIVALRY_PAIRS: tuple[tuple[str, str, str, str], ...] = (
    # Türkiye — Süper Lig & tarihi derbiler
    ("besiktas", "galatasaray", "mega_derbi", "İstanbul Mega Derbisi (BJK–GS)"),
    ("fenerbahce", "galatasaray", "mega_derbi", "Kıtalararası Derbi (FB–GS)"),
    ("besiktas", "fenerbahce", "mega_derbi", "İstanbul Mega Derbisi (BJK–FB)"),
    ("trabzonspor", "fenerbahce", "derbi", "Büyük Rekabet (TS–FB)"),
    ("trabzonspor", "galatasaray", "derbi", "Büyük Rekabet (TS–GS)"),
    ("trabzonspor", "besiktas", "derbi", "Büyük Rekabet (TS–BJK)"),
    ("goztepe", "altay", "derbi", "İzmir Derbisi"),
    ("goztepe", "karsiyaka", "derbi", "İzmir Derbisi"),
    ("ankaragucu", "genclerbirligi", "derbi", "Ankara Derbisi"),
    ("adana demirspor", "adanaspor", "derbi", "Adana Derbisi"),
    # Avrupa & Dünya mega derbileri
    ("real madrid", "barcelona", "mega_derbi", "El Clásico"),
    ("real madrid", "atletico madrid", "derbi", "Madrid Derbisi"),
    ("sevilla", "real betis", "derbi", "El Gran Derbi (Sevilla)"),
    ("athletic bilbao", "real sociedad", "derbi", "Bask Derbisi"),
    ("inter", "milan", "mega_derbi", "Derby della Madonnina (Milano)"),
    ("roma", "lazio", "mega_derbi", "Derby della Capitale (Roma)"),
    ("juventus", "inter", "derbi", "Derby d'Italia"),
    ("juventus", "torino", "derbi", "Derby della Mole (Torino)"),
    ("arsenal", "tottenham", "mega_derbi", "Kuzey Londra Derbisi"),
    ("liverpool", "everton", "derbi", "Merseyside Derbisi"),
    ("liverpool", "manchester united", "mega_derbi", "North West Derbisi"),
    ("manchester city", "manchester united", "mega_derbi", "Manchester Derbisi"),
    ("chelsea", "arsenal", "derbi", "Londra Derbisi"),
    ("celtic", "rangers", "mega_derbi", "Old Firm Derbisi"),
    ("bayern", "dortmund", "mega_derbi", "Der Klassiker"),
    ("dortmund", "schalke", "mega_derbi", "Revierderby"),
    ("psg", "marseille", "mega_derbi", "Le Classique"),
    ("lyon", "saint etienne", "derbi", "Rhône Derbisi"),
    ("ajax", "feyenoord", "mega_derbi", "De Klassieker"),
    ("ajax", "psv", "derbi", "De Topper"),
    ("benfica", "porto", "mega_derbi", "O Clássico"),
    ("benfica", "sporting", "mega_derbi", "Lizbon Derbisi"),
    ("olympiacos", "panathinaikos", "mega_derbi", "Ebedi Düşmanlar Derbisi"),
    ("boca juniors", "river plate", "mega_derbi", "Superclásico"),
    ("flamengo", "fluminense", "derbi", "Fla–Flu Derbisi"),
    ("palmeiras", "corinthians", "mega_derbi", "Derby Paulista"),
    ("gremio", "internacional", "mega_derbi", "Gre–Nal Derbisi"),
    ("partizan", "red star", "mega_derbi", "Belgrad Ebedi Derbisi"),
    ("crvena zvezda", "partizan", "mega_derbi", "Belgrad Ebedi Derbisi"),
)


def _team_matches_token(norm_team: str, token: str) -> bool:
    if not norm_team or not token:
        return False
    if norm_team == token:
        return True
    # Boundary-aware match so "inter" does not match "internacional" falsely
    if token == "inter":
        return "inter" in norm_team.split() and "internacional" not in norm_team and "miami" not in norm_team
    if token == "milan":
        return "milan" in norm_team.split() and "inter" not in norm_team.split()
    return token in norm_team


def detect_derby_rivalry(home: str, away: str) -> dict[str, Any] | None:
    """Detect whether a fixture is a famous domestic/continental derby or mega-rivalry."""
    nh, na = _norm(home), _norm(away)
    if not nh or not na:
        return None
    for a, b, tier, label in _RIVALRY_PAIRS:
        if (_team_matches_token(nh, a) and _team_matches_token(na, b)) or (
            _team_matches_token(nh, b) and _team_matches_token(na, a)
        ):
            is_mega = tier == "mega_derbi"
            return {
                "is_derby": True,
                "tier": tier,
                "label": label,
                "card_intensity_boost": 1.25 if is_mega else 1.15,
                "draw_boost": 0.012 if is_mega else 0.007,
                "margin_tighten": 0.96 if is_mega else 0.98,
            }
    return None


# --------------------------------------------------------------------------- #
# 2. Hat Bazlı Takım Değerlendirmesi (Kaleci / Defans / Orta Saha / Forvet)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TeamUnitRatings:
    """0–100 hat puanları, kaleci/oyuncu formu, eksikler ve oyun stili."""

    team: str
    goalkeeper: float
    defense: float
    midfield: float
    attack: float
    overall: float
    coverage: float  # 0..1 data completeness
    tactical_style: str
    goalkeeper_note: str
    attack_note: str
    midfield_note: str
    defense_note: str
    hot_players: tuple[str, ...] = ()
    missing_by_line: dict[str, list[str]] = field(default_factory=lambda: {"G": [], "D": [], "M": [], "F": []})
    recent_form_pts_per_game: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MatchScoutingReport:
    """Maçın eksiksiz oyuncu + hat + taktik eşleşme + derbi scouting raporu."""

    home: TeamUnitRatings
    away: TeamUnitRatings
    home_attack_vs_away_def_gk: float  # positive => Home attack dominates Away defense+GK
    away_attack_vs_home_def_gk: float  # positive => Away attack dominates Home defense+GK
    midfield_control_edge: float       # positive => Home controls midfield
    goalkeeper_edge: float             # positive => Home has stronger GK form
    set_piece_edge: float              # positive => Home has stronger set-piece/corner threat
    tempo_index: float                 # 0..100 (high = open shootout, low = tight tactical chess)
    derby: dict[str, Any] | None
    scouting_edge_1x2: dict[str, float]  # strictly bounded MS 1 / MS 0 / MS 2 adjustments (sum=0)
    scouting_goal_mult: dict[str, float]  # strictly bounded home / away multipliers [0.95, 1.05]
    confidence: float  # 0..1
    key_edges: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_pct(val: Any) -> float | None:
    """Normalize a percentage string/number like '%58', '58.4', or '0.58' into 0..100."""
    v = _flt(val)
    if v is None:
        return None
    if 0.0 <= v <= 1.0 and "%" not in str(val):
        return v * 100.0
    return v


def _form_ppg(form_str: str | None) -> float | None:
    if not form_str:
        return None
    pts = 0.0
    n = 0
    for ch in str(form_str).upper():
        if ch in ("W", "G"):
            pts += 3.0
            n += 1
        elif ch in ("D", "B"):
            pts += 1.0
            n += 1
        elif ch in ("L", "M"):
            n += 1
    return round(pts / n, 2) if n >= 3 else None


def _collect_missing_by_line(
    team_rec: Mapping[str, Any],
    tm_side: Mapping[str, Any],
    ua_side: Mapping[str, Any],
    fotmob_side: Mapping[str, Any] | None = None,
) -> tuple[dict[str, list[str]], bool, bool]:
    """Group confirmed/likely absences into G / D / M / F lines + flag #1 GK & top-scorer out."""
    lines: dict[str, list[str]] = {"G": [], "D": [], "M": [], "F": []}
    seen: set[str] = set()

    def _add(name: str | None, pos: str = "") -> None:
        if not name:
            return
        nk = _norm(name)
        if not nk or nk in seen:
            return
        seen.add(nk)
        grp = _pos_group(pos)
        if grp in lines:
            lines[grp].append(str(name))
        else:
            lines["M"].append(str(name))  # conservative outfield default

    for p in team_rec.get("missing_regulars") or []:
        _add(p.get("name"), p.get("pos", ""))
    for p in team_rec.get("likely_absent") or []:
        reason = str(p.get("reason") or "")
        if "rotasyon" not in reason.lower():
            _add(p.get("name"), p.get("pos", ""))
    for p in tm_side.get("critical_absences") or tm_side.get("injuries") or []:
        if isinstance(p, Mapping):
            _add(p.get("name") or p.get("player"), p.get("pos") or p.get("position") or "")
    for p in (ua_side.get("injuries") or []) + (ua_side.get("cards") or []):
        if isinstance(p, Mapping):
            _add(p.get("player") or p.get("name"), p.get("pos") or "")
    if isinstance(fotmob_side, Mapping):
        for p in fotmob_side.get("unavailable") or []:
            if isinstance(p, Mapping) and p.get("name"):
                _add(p.get("name"), "")

    gk_out = bool(
        team_rec.get("goalkeeper_changed")
        or tm_side.get("gk1_out")
        or ua_side.get("gk_out")
        or len(lines["G"]) > 0
    )
    ts_out = bool(team_rec.get("top_scorer_missing") or tm_side.get("top_scorer_out"))
    return lines, gk_out, ts_out


def build_team_unit_ratings(
    team_name: str,
    *,
    team_rec: Mapping[str, Any] | None = None,
    xg_side: Mapping[str, Any] | None = None,
    box_side: Mapping[str, Any] | None = None,
    half_side: Mapping[str, Any] | None = None,
    tm_side: Mapping[str, Any] | None = None,
    ua_side: Mapping[str, Any] | None = None,
    fotmob_side: Mapping[str, Any] | None = None,
) -> TeamUnitRatings:
    """Compute calibrated 0–100 ratings for Kaleci, Defans, Orta Saha, and Forvet units."""
    t = team_rec or {}
    xg = xg_side or {}
    bx = box_side or {}
    tm = tm_side or {}
    ua = ua_side or {}
    prof = t.get("profile") or {}
    tstats = t.get("team_stats") or {}
    recent = t.get("recent_player_form") or {}

    missing_by_line, gk_out, ts_out = _collect_missing_by_line(t, tm, ua, fotmob_side)

    # Track data coverage (0..1)
    signals = 0
    if xg:
        signals += 2
    if bx:
        signals += 2
    if prof:
        signals += 2
    if tstats:
        signals += 1
    if recent.get("matches", 0) >= 3:
        signals += 1
    if t.get("form"):
        signals += 1
    coverage = round(_clip(signals / 7.0, 0.0, 1.0), 2)

    # ---- 1. KALECİ HATTI (Goalkeeper 0..100) ----
    gk_score = 55.0
    gk_parts: list[str] = []
    gk = prof.get("goalkeeper") or {}
    rec_gk = recent.get("recent_gk") or {}
    backup_gk = prof.get("backup_goalkeeper") or {}

    save_pct = _flt(gk.get("save_pct"))
    if save_pct is None:
        save_pct = _flt(bx.get("gk_save_rate"))
    conceded_pg = _flt(gk.get("conceded_per_game"))
    if conceded_pg is None:
        conceded_pg = _flt(xg.get("goals_against")) or _flt(bx.get("goals_against"))
    def_luck = _flt(xg.get("defensive_luck"))  # xGA - GA (positive = GK saving above xGA)

    if save_pct is not None:
        # Typical club GK save% is ~0.68..0.72; >=0.78 elite, <=0.62 weak
        gk_score += _clip((save_pct - 0.70) * 160.0, -18.0, 22.0)
        gk_parts.append(f"kurtarış %{100 * save_pct:.0f}")
    if conceded_pg is not None:
        gk_score += _clip((1.30 - conceded_pg) * 14.0, -14.0, 14.0)
        gk_parts.append(f"{conceded_pg:.2f} gol/maç")
    if def_luck is not None:
        # PSxG-GA style overperformance: positive = strong shot-stopping (bounded to avoid pure luck chase)
        gk_score += _clip(def_luck * 14.0, -8.0, 10.0)
    if rec_gk.get("save_pct") is not None and (rec_gk.get("starts") or 0) >= 3:
        r_sp = float(rec_gk["save_pct"])
        gk_score += _clip((r_sp - 0.70) * 70.0, -9.0, 10.0)
        gk_parts.append(f"son {rec_gk['starts']}M %{100 * r_sp:.0f}")
    if gk.get("name"):
        gk_parts.insert(0, str(gk["name"]))
    elif rec_gk.get("name"):
        gk_parts.insert(0, str(rec_gk["name"]))

    if gk_out:
        drop = 14.0
        if backup_gk.get("save_pct") is not None and save_pct is not None:
            drop = _clip(8.0 + max(0.0, (save_pct - float(backup_gk["save_pct"])) * 90.0), 7.0, 18.0)
        gk_score -= drop
        gk_parts.append("⚠ 1. kaleci eksik")
    gk_score = round(_clip(gk_score, 20.0, 96.0), 1)
    gk_note = ", ".join(gk_parts) if gk_parts else "standart lig ortalaması"

    # ---- 2. DEFANS HATTI (Defense 0..100) ----
    def_score = 55.0
    def_parts: list[str] = []
    xga = _flt(xg.get("xg_against")) or _flt(tstats.get("xGA (beklenen yenen gol)"))
    ga = _flt(xg.get("goals_against")) or _flt(tstats.get("Yenen gol")) or _flt(bx.get("goals_against"))
    shots_ag = _flt(bx.get("shots_against")) or _flt(tstats.get("Rakip şutu"))
    sot_ag = _flt(bx.get("sot_against"))
    cs_rate = _flt(bx.get("clean_sheet_rate"))
    tackle_pct = _parse_pct(tstats.get("Top kapma başarısı"))

    if xga is not None:
        def_score += _clip((1.35 - xga) * 32.0, -22.0, 24.0)
        def_parts.append(f"xGA {xga:.2f}")
    elif ga is not None:
        def_score += _clip((1.35 - ga) * 24.0, -18.0, 18.0)
        def_parts.append(f"yenen {ga:.2f}/M")
    if shots_ag is not None:
        def_score += _clip((12.0 - shots_ag) * 1.8, -10.0, 10.0)
        def_parts.append(f"rakip şut {shots_ag:.1f}")
    if sot_ag is not None:
        def_score += _clip((4.2 - sot_ag) * 3.5, -8.0, 8.0)
    if cs_rate is not None:
        def_score += _clip((cs_rate - 0.28) * 32.0, -8.0, 10.0)
        def_parts.append(f"CS %{100 * cs_rate:.0f}")
    if tackle_pct is not None:
        def_score += _clip((tackle_pct - 60.0) * 0.4, -5.0, 5.0)
    if missing_by_line["D"]:
        def_pen = min(16.0, 5.5 * len(missing_by_line["D"]))
        def_score -= def_pen
        def_parts.append(f"⚠ {len(missing_by_line['D'])} defans eksik")
    def_score = round(_clip(def_score, 20.0, 96.0), 1)
    def_note = ", ".join(def_parts) if def_parts else "standart lig ortalaması"

    # ---- 3. ORTA SAHA HATTI (Midfield 0..100) ----
    mid_score = 55.0
    mid_parts: list[str] = []
    poss = _parse_pct(tstats.get("Topla oynama"))
    pass_pct = _parse_pct(tstats.get("Pas isabeti"))
    shot_share = _flt(bx.get("shot_share"))
    corner_share = _flt(bx.get("corner_share"))
    fouls_pg = _flt(bx.get("fouls_for")) or _flt(tstats.get("Faul"))
    cards_pg = _flt(bx.get("cards_for")) or _flt(tstats.get("Sarı kart"))
    by_pos = prof.get("by_position") or {}
    mid_prod = by_pos.get("M") or {}
    mid_ga_prod = int(mid_prod.get("goals") or 0) + int(mid_prod.get("assists") or 0)

    if poss is not None:
        mid_score += _clip((poss - 50.0) * 1.05, -14.0, 16.0)
        mid_parts.append(f"top %{poss:.0f}")
    if pass_pct is not None:
        mid_score += _clip((pass_pct - 80.0) * 1.1, -8.0, 10.0)
        mid_parts.append(f"pas %{pass_pct:.0f}")
    if shot_share is not None:
        mid_score += _clip((shot_share - 0.50) * 65.0, -14.0, 16.0)
        mid_parts.append(f"şut payı %{100 * shot_share:.0f}")
    if corner_share is not None:
        mid_score += _clip((corner_share - 0.50) * 35.0, -8.0, 9.0)
    if mid_ga_prod > 0:
        mid_score += _clip((mid_ga_prod - 6.0) * 0.7, -4.0, 9.0)
        mid_parts.append(f"OS katkı {mid_prod.get('goals', 0)}G {mid_prod.get('assists', 0)}A")
    if cards_pg is not None and cards_pg >= 2.8:
        mid_score -= min(5.0, (cards_pg - 2.6) * 3.0)
        mid_parts.append(f"kart {cards_pg:.1f}/M")
    if missing_by_line["M"]:
        mid_score -= min(15.0, 5.0 * len(missing_by_line["M"]))
        mid_parts.append(f"⚠ {len(missing_by_line['M'])} orta saha eksik")
    mid_score = round(_clip(mid_score, 20.0, 96.0), 1)
    mid_note = ", ".join(mid_parts) if mid_parts else "standart lig ortalaması"

    # ---- 4. FORVET / HÜCUM HATTI (Attack 0..100) ----
    att_score = 55.0
    att_parts: list[str] = []
    xgf = _flt(xg.get("xg_for")) or _flt(tstats.get("xG (beklenen gol)"))
    gf = _flt(xg.get("goals_for")) or _flt(tstats.get("Gol")) or _flt(bx.get("goals_for"))
    shots_for = _flt(bx.get("shots_for")) or _flt(tstats.get("Şut"))
    sot_for = _flt(bx.get("sot_for")) or _flt(tstats.get("İsabetli şut"))
    big_ch = _flt(tstats.get("Net pozisyon"))
    sot_conv = _flt(bx.get("sot_conversion"))

    if xgf is not None:
        att_score += _clip((xgf - 1.35) * 30.0, -20.0, 24.0)
        att_parts.append(f"xG {xgf:.2f}")
    elif gf is not None:
        att_score += _clip((gf - 1.35) * 24.0, -18.0, 18.0)
        att_parts.append(f"gol {gf:.2f}/M")
    if shots_for is not None:
        att_score += _clip((shots_for - 12.0) * 1.4, -8.0, 9.0)
        att_parts.append(f"şut {shots_for:.1f}")
    if sot_for is not None:
        att_score += _clip((sot_for - 4.2) * 3.0, -7.0, 8.0)
    if big_ch is not None:
        att_score += _clip((big_ch - 2.0) * 4.5, -6.0, 8.0)
    if sot_conv is not None:
        att_score += _clip((sot_conv - 0.31) * 35.0, -6.0, 7.0)

    # Recent 5-match hot attacker momentum
    hot_list: list[str] = []
    hot_players = recent.get("hot_players") or []
    recent_ga_total = 0
    for p in hot_players[:3]:
        g_n, a_n = int(p.get("goals") or 0), int(p.get("assists") or 0)
        recent_ga_total += g_n + a_n
        if g_n or a_n:
            hot_list.append(f"{p['name']} ({g_n}G {a_n}A / son {recent.get('matches', 5)}M)")
    if not hot_list:
        for p in (prof.get("top_scorers") or [])[:3]:
            hot_list.append(f"{p['name']} ({p['goals']}G {p['assists']}A)")
        if not hot_list:
            for p in (tm.get("top_scorers") or [])[:3]:
                hot_list.append(f"{p['name']} ({p['goals']}G {p['assists']}A)")
    if recent_ga_total >= 5:
        att_score += min(7.0, (recent_ga_total - 4) * 1.5)

    if ts_out:
        att_score -= 10.0
        att_parts.append("⚠ gol kralı eksik")
    if missing_by_line["F"]:
        extra_f = max(0, len(missing_by_line["F"]) - int(ts_out))
        if extra_f > 0:
            att_score -= min(10.0, 4.5 * extra_f)
            att_parts.append(f"⚠ {len(missing_by_line['F'])} forvet eksik")
    att_score = round(_clip(att_score, 20.0, 96.0), 1)
    att_note = ", ".join(att_parts) if att_parts else "standart lig ortalaması"

    # Optional FotMob starter rating nudge (tiny, bounded)
    if isinstance(fotmob_side, Mapping) and _flt(fotmob_side.get("rating")) is not None:
        fm_r = float(fotmob_side["rating"])
        nudge = _clip((fm_r - 6.85) * 8.0, -4.0, 4.0)
        att_score = round(_clip(att_score + 0.5 * nudge, 20.0, 96.0), 1)
        mid_score = round(_clip(mid_score + 0.5 * nudge, 20.0, 96.0), 1)
        def_score = round(_clip(def_score + 0.5 * nudge, 20.0, 96.0), 1)

    # Recent form PPG
    form_ppg = _form_ppg(t.get("form"))
    if form_ppg is None:
        form_ppg = _flt(bx.get("recent5_ppg"))

    overall = round(0.30 * att_score + 0.25 * mid_score + 0.27 * def_score + 0.18 * gk_score, 1)

    # Tactical Style Classification
    corners_for = _flt(bx.get("corners_for")) or _flt(tstats.get("Korner"))
    if (poss is not None and poss >= 56.0) or (shot_share is not None and shot_share >= 0.57 and (xgf or 0) >= 1.55):
        style = "topa_sahip_hücum"
    elif (xgf is not None and xgf >= 1.55) and (xga is not None and xga >= 1.35):
        style = "yüksek_tempo_açık"
    elif (corners_for is not None and corners_for >= 6.0) and (fouls_pg is not None and fouls_pg >= 12.5):
        style = "duran_top_fiziksel"
    elif (xga is not None and xga <= 1.05) and (poss is None or poss <= 50.0):
        style = "savunma_kontra"
    else:
        style = "dengeli"

    return TeamUnitRatings(
        team=team_name,
        goalkeeper=gk_score,
        defense=def_score,
        midfield=mid_score,
        attack=att_score,
        overall=overall,
        coverage=coverage,
        tactical_style=style,
        goalkeeper_note=gk_note,
        attack_note=att_note,
        midfield_note=mid_note,
        defense_note=def_note,
        hot_players=tuple(hot_list[:4]),
        missing_by_line=missing_by_line,
        recent_form_pts_per_game=form_ppg,
    )


# --------------------------------------------------------------------------- #
# 3. Maç Seviyesi Taktik Eşleşme & Sınırlı Algoritma Sinyali
# --------------------------------------------------------------------------- #


def build_match_scouting_report(rec: Mapping[str, Any]) -> MatchScoutingReport | None:
    """Build full unit-by-unit scouting report & bounded tactical edge for any match record."""
    home_name = str(rec.get("home") or "").strip()
    away_name = str(rec.get("away") or "").strip()
    if not home_name or not away_name:
        return None

    res = rec.get("research") or {}
    teams = res.get("teams") or {}
    xg = res.get("xg_intelligence") or {}
    bx = res.get("boxscore_profile") or {}
    hs = res.get("half_split") or {}
    tm = res.get("tm_absences") or {}
    ua = res.get("user_absences") or {}
    fm = res.get("fotmob") or {}

    h_units = build_team_unit_ratings(
        home_name,
        team_rec=teams.get("home"),
        xg_side=xg.get("home") if isinstance(xg, Mapping) else None,
        box_side=bx.get("home") if isinstance(bx, Mapping) else None,
        half_side=hs.get("home") if isinstance(hs, Mapping) else None,
        tm_side=tm.get("home") if isinstance(tm, Mapping) else None,
        ua_side=ua.get("home") if isinstance(ua, Mapping) else None,
        fotmob_side=fm.get("home_lineup") if isinstance(fm, Mapping) else None,
    )
    a_units = build_team_unit_ratings(
        away_name,
        team_rec=teams.get("away"),
        xg_side=xg.get("away") if isinstance(xg, Mapping) else None,
        box_side=bx.get("away") if isinstance(bx, Mapping) else None,
        half_side=hs.get("away") if isinstance(hs, Mapping) else None,
        tm_side=tm.get("away") if isinstance(tm, Mapping) else None,
        ua_side=ua.get("away") if isinstance(ua, Mapping) else None,
        fotmob_side=fm.get("away_lineup") if isinstance(fm, Mapping) else None,
    )

    # Unit-vs-Unit Matchups (in rating points, typically -35..+35)
    away_def_gk = 0.62 * a_units.defense + 0.38 * a_units.goalkeeper
    home_def_gk = 0.62 * h_units.defense + 0.38 * h_units.goalkeeper
    h_att_edge = round(h_units.attack - away_def_gk, 1)
    a_att_edge = round(a_units.attack - home_def_gk, 1)
    mid_edge = round(h_units.midfield - a_units.midfield, 1)
    gk_edge = round(h_units.goalkeeper - a_units.goalkeeper, 1)

    # Set-piece / corner pressure differential
    hb = bx.get("home") if isinstance(bx, Mapping) else {}
    ab = bx.get("away") if isinstance(bx, Mapping) else {}
    hc = _flt((hb or {}).get("corners_for"))
    ac_con = _flt((ab or {}).get("corners_against"))
    ac = _flt((ab or {}).get("corners_for"))
    hc_con = _flt((hb or {}).get("corners_against"))
    if hc is not None and ac is not None:
        sp_h = 0.6 * hc + 0.4 * (ac_con if ac_con is not None else 5.0)
        sp_a = 0.6 * ac + 0.4 * (hc_con if hc_con is not None else 5.0)
        set_piece_edge = round((sp_h - sp_a) * 4.5, 1)
    else:
        set_piece_edge = 0.0

    # Match Tempo Index (0..100)
    mu_h = _flt(rec.get("mu_home"))
    mu_a = _flt(rec.get("mu_away"))
    tempo = 50.0
    if mu_h is not None and mu_a is not None:
        tempo += _clip((mu_h + mu_a - 2.55) * 18.0, -22.0, 26.0)
    tempo += _clip(((h_att_edge + a_att_edge) / 2.0) * 0.75, -14.0, 16.0)
    if h_units.tactical_style == "yüksek_tempo_açık" or a_units.tactical_style == "yüksek_tempo_açık":
        tempo += 8.0
    if h_units.tactical_style == "savunma_kontra" and a_units.tactical_style == "savunma_kontra":
        tempo -= 10.0

    derby = detect_derby_rivalry(home_name, away_name)
    if derby:
        tempo -= 4.0  # derbies tend to be cagey & physical
    tempo = round(_clip(tempo, 15.0, 95.0), 1)

    # Confidence scaled by average data completeness of both teams
    conf = round(0.5 * (h_units.coverage + a_units.coverage), 2)

    # Strictly bounded algorithmic signals (anti-double-counting with sharp markets!)
    # Net unit edge: combines Attack-vs-Def+GK mismatch (55%), Midfield control (25%), GK edge (20%)
    net_unit = 0.55 * (h_att_edge - a_att_edge) + 0.25 * mid_edge + 0.20 * gk_edge
    # Scale gently by confidence; max 1X2 shift is ±0.020 (2.0 pp)
    raw_shift = _clip((net_unit / 100.0) * 0.075 * conf, -0.020, 0.020)
    draw_adj = 0.0
    if derby:
        draw_adj += float(derby["draw_boost"]) * max(0.5, conf)
        # Derbies slightly compress directional blowouts
        raw_shift *= float(derby["margin_tighten"])
    # Ensure zero-sum 1X2 adjustment
    d1 = round(raw_shift - 0.5 * draw_adj, 5)
    dx = round(draw_adj, 5)
    d2 = round(-raw_shift - 0.5 * draw_adj, 5)

    # Bounded scoring-rate multipliers for simulation / goal projection ([0.95, 1.05])
    h_mult = _clip(1.0 + (h_att_edge / 100.0) * 0.14 * conf, 0.95, 1.05)
    a_mult = _clip(1.0 + (a_att_edge / 100.0) * 0.14 * conf, 0.95, 1.05)
    if derby:
        # Slight physical tightening in mega-derbies
        h_mult = _clip(h_mult * 0.985, 0.95, 1.05)
        a_mult = _clip(a_mult * 0.985, 0.95, 1.05)

    # Key human-readable tactical edges & risk flags (Turkish)
    key_edges: list[str] = []
    risk_flags: list[str] = []

    if derby:
        risk_flags.append(f"🔥 {derby['label']}: yüksek kart/sertlik ve sıkı skor varyansı riski")
    if abs(gk_edge) >= 8.0:
        who = home_name if gk_edge > 0 else away_name
        key_edges.append(f"Kaleci üstünlüğü {who} lehine ({h_units.goalkeeper:.0f} vs {a_units.goalkeeper:.0f})")
    if h_att_edge >= 8.0:
        key_edges.append(f"{home_name} hücumu ({h_units.attack:.0f}), {away_name} savunma+kalecisine ({away_def_gk:.0f}) üstün (+{h_att_edge:.1f})")
    if a_att_edge >= 8.0:
        key_edges.append(f"{away_name} hücumu ({a_units.attack:.0f}), {home_name} savunma+kalecisine ({home_def_gk:.0f}) üstün (+{a_att_edge:.1f})")
    if abs(mid_edge) >= 8.0:
        who = home_name if mid_edge > 0 else away_name
        key_edges.append(f"Orta saha kontrolü {who} lehine ({h_units.midfield:.0f} vs {a_units.midfield:.0f})")
    if abs(set_piece_edge) >= 8.0:
        who = home_name if set_piece_edge > 0 else away_name
        key_edges.append(f"Duran top / korner baskısı {who} lehine ({set_piece_edge:+.1f})")
    if h_units.missing_by_line["G"]:
        risk_flags.append(f"{home_name} 1. kaleci hattı eksik: {', '.join(h_units.missing_by_line['G'])}")
    if a_units.missing_by_line["G"]:
        risk_flags.append(f"{away_name} 1. kaleci hattı eksik: {', '.join(a_units.missing_by_line['G'])}")
    if len(h_units.missing_by_line["D"]) >= 2:
        risk_flags.append(f"{home_name} defans hattında {len(h_units.missing_by_line['D'])} eksik")
    if len(a_units.missing_by_line["D"]) >= 2:
        risk_flags.append(f"{away_name} defans hattında {len(a_units.missing_by_line['D'])} eksik")

    return MatchScoutingReport(
        home=h_units,
        away=a_units,
        home_attack_vs_away_def_gk=h_att_edge,
        away_attack_vs_home_def_gk=a_att_edge,
        midfield_control_edge=mid_edge,
        goalkeeper_edge=gk_edge,
        set_piece_edge=set_piece_edge,
        tempo_index=tempo,
        derby=derby,
        scouting_edge_1x2={"MS 1": d1, "MS 0": dx, "MS 2": d2},
        scouting_goal_mult={"home": round(h_mult, 4), "away": round(a_mult, 4)},
        confidence=conf,
        key_edges=tuple(key_edges),
        risk_flags=tuple(risk_flags),
    )


def render_scouting_markdown(report: MatchScoutingReport | Mapping[str, Any]) -> list[str]:
    """Render a clear Turkish line-by-line squad scouting & tactical matchup Markdown section."""
    data = report.to_dict() if isinstance(report, MatchScoutingReport) else dict(report)
    h = data["home"]
    a = data["away"]

    style_labels = {
        "topa_sahip_hücum": "Topa sahip hücum",
        "yüksek_tempo_açık": "Yüksek tempo / açık oyun",
        "duran_top_fiziksel": "Duran top & fiziksel pres",
        "savunma_kontra": "Savunma & kontra",
        "dengeli": "Dengeli",
    }

    lines = [
        "## Kadro Hatları, Kaleci/Oyuncu Formu ve Taktik Eşleşme",
        "",
        f"Veri kapsamı: **%{100 * data['confidence']:.0f}** · "
        f"Maç Tempo Endeksi: **{data['tempo_index']:.0f}/100** · "
        f"Oyun Stili: **{h['team']}** ({style_labels.get(h['tactical_style'], h['tactical_style'])}) vs "
        f"**{a['team']}** ({style_labels.get(a['tactical_style'], a['tactical_style'])})",
        "",
        f"| Hat (0–100) | {h['team']} | Detay ({h['team']}) | {a['team']} | Detay ({a['team']}) | Fark |",
        "|---|---:|---|---:|---|---:|",
        f"| **Kaleci** | **{h['goalkeeper']:.1f}** | {h['goalkeeper_note']} | **{a['goalkeeper']:.1f}** | {a['goalkeeper_note']} | {h['goalkeeper'] - a['goalkeeper']:+.1f} |",
        f"| **Defans** | **{h['defense']:.1f}** | {h['defense_note']} | **{a['defense']:.1f}** | {a['defense_note']} | {h['defense'] - a['defense']:+.1f} |",
        f"| **Orta Saha** | **{h['midfield']:.1f}** | {h['midfield_note']} | **{a['midfield']:.1f}** | {a['midfield_note']} | {h['midfield'] - a['midfield']:+.1f} |",
        f"| **Forvet / Hücum** | **{h['attack']:.1f}** | {h['attack_note']} | **{a['attack']:.1f}** | {a['attack_note']} | {h['attack'] - a['attack']:+.1f} |",
        f"| **Genel Hat Gücü** | **{h['overall']:.1f}** | Form PPG: {h.get('recent_form_pts_per_game') or '-'} | **{a['overall']:.1f}** | Form PPG: {a.get('recent_form_pts_per_game') or '-'} | {h['overall'] - a['overall']:+.1f} |",
        "",
    ]

    if h.get("hot_players") or a.get("hot_players"):
        lines += [
            f"- **Formda oyuncular ({h['team']}):** {', '.join(h.get('hot_players') or []) or '-'}",
            f"- **Formda oyuncular ({a['team']}):** {', '.join(a.get('hot_players') or []) or '-'}",
        ]

    # Missing starters by line
    def _fmt_miss(m_dict: Mapping[str, list[str]]) -> str:
        parts = []
        for code, lbl in (("G", "Kaleci"), ("D", "Defans"), ("M", "Orta Saha"), ("F", "Forvet")):
            if m_dict.get(code):
                parts.append(f"{lbl}: {', '.join(m_dict[code])}")
        return " · ".join(parts) if parts else "kritik eksik yok"

    lines += [
        f"- **Hat eksikleri ({h['team']}):** {_fmt_miss(h.get('missing_by_line') or {})}",
        f"- **Hat eksikleri ({a['team']}):** {_fmt_miss(a.get('missing_by_line') or {})}",
        f"- **Taktik eşleşme:** Ev Hücum vs Dep Def+Kaleci `{data['home_attack_vs_away_def_gk']:+.1f}` · "
        f"Dep Hücum vs Ev Def+Kaleci `{data['away_attack_vs_home_def_gk']:+.1f}` · "
        f"Orta Saha `{data['midfield_control_edge']:+.1f}` · Kaleci `{data['goalkeeper_edge']:+.1f}`",
    ]
    for edge in data.get("key_edges") or []:
        lines.append(f"- **Öne çıkan üstünlük:** {edge}")
    for rf in data.get("risk_flags") or []:
        lines.append(f"- **⚠ Scouting uyarısı:** {rf}")
    lines.append("")
    return lines

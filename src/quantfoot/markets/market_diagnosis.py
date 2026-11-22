"""Pazar teşhis ve rehabilitasyon motoru — 'yasaklama yerine kök hatayı bul ve geliştir' (22 Kasım 2026).

18–21 Kasım 2026 denetiminde (4.192 sonuçlanmış seçim, 5 yapay zekâ) 'kupon katili' görünen bahis ailelerinin
neden yattığı alt kırılımlarla ölçüldü:

1. **Karşılıklı Gol (KG Var / KG Yok):**
   - ``KG Var`` genel %59,8 (P≥%65'te %48,0) kaldı çünkü tek taraflı maçlarda (``min(mu_ev, mu_dep) < 0.90`` → %25,0)
     ve 2. kademe kısır maçlarda oynandı. Oysa **iki takımın da gol beklentisi dengeli (``min(mu_ev, mu_dep) >= 1.10``)**
     olduğunda **125/201 (%62,2 vs P %62,1, +0,1p)** ile birebir kalibre çıktı.
   - ``KG Yok`` genel %50,9 kaldı çünkü 35/53 seçim keskin olmayan orta bürolardan (%45,7) veya yüksek toplamlı
     fark maçlarından (teselli golü tuzağı: Vihren 6-1, Galatasaray 2-1) geldi. Oysa **keskin referanslı (``sharp``),
     düşük toplamlı (``mu_toplam <= 2.45``) ve zayıf tarafın ``min(mu) <= 0.75``** olduğu maçlarda **11/18 (%61,1 vs %60,3)** tuttu.

2. **Deplasman Golleri ve Ev Sahibi Golleri:**
   - Bütün aile yasaklanmıştı; oysa aileyi aşağı çeken **İlk Yarı Takım Golleri** (``Ev İY 0.5 Üst``: 39/90 = %43,3,
     **-17,2p** kapanan savunma tuzağı; ``Dep İY 0.5 Alt`` dengeli maçlarda 27/64 = %42,2) ve yüksek rakip xG'li
     ``Dep 1.5 Alt`` (%56,2) idi.
   - Buna karşılık ``P >= %65 & sharp`` diliminde:
     * ``Dep 0.5 Üst``: **33/47 (%70,2 vs P %67,6, +2,6p)**
     * ``Dep 2.5 Alt``: **8/8 (%100,0; tümü 15/20 = %75,0)**
     * ``Dep 1.5 Üst``: **5/7 (%71,4 vs P %68,1)**
     * ``Ev 1.5 Alt``: **23/34 (%67,6 vs P %67,3)**
     * ``Ev 2.5 Alt``: **36/48 (%75,0 vs P %63,7, +11,3p)**
     * ``Dep İY 0.5 Alt`` yalnız ``mu_dep < 0.85`` + yetişkin keskin ligde: **24/35 (%68,6 vs P %68,3, +0,2p)**!

3. **İlk Yarı 1.5 Alt (İY 1.5 Alt) ve Yarı Özel İçindeki Gizli Tuzaklar:**
   - ``İY 1.5 Alt`` izinli ailede olduğu için sorgusuz geçiyordu; oysa ``P >= %65`` diliminde iki takımın da gol
     beklentisi yüksekken (``min(mu_ev, mu_dep) >= 1.05``) 2. lig / diğer liglerde **11/25 (%44,0 vs P %67,0, -23,0p)**
     ile çöktü! Büyük liglerde (5/5 = %100) veya düşük toplamlı maçlarda (``mu_toplam <= 2.35``, ``min(mu) < 0.90``) ise çalıştı.
   - ``Yarı özel`` ailesinde ``DEĞİL(Dep İki Yarıda Gol)`` **18/21 (%85,7)** ve ``DEĞİL(Ev İki Yarıda Gol)`` **45/63 (%71,4)**
     tutarken, aynı ailedeki ``Ev En Az Bir Yarıyı Kazanır`` **13/27 (%48,1 vs P %62,4, -14,3p)** ile gizli kupon katiliydi.

4. **Çifte Şans, Handikap, İlk Gol ve Maç Sonucu (MS 1 / MS 2):**
   - ``ÇŞ 12`` (``P >= %65 & sharp`` ve düşük beraberlik riski ``p_draw < 0.24``, ``mu_toplam >= 2.75``): **13/17 (%76,5)**
   - ``Hnd(+1) 1`` (``P >= %65 & sharp``): **9/12 (%75,0)**; ``Hnd(-2) 2``: **7/10 (%70,0)**
   - ``Hnd(-1) 2`` / ``ÇŞ X2`` ise güçlü ev favorisine karşı (``p_draw < 0.25``) veya çok gollü maçlarda (%42,3–%51,0) çöktü.
   - ``İlk Gol 1/2`` dengeli maçlarda (``min(mu) >= 1.00``) yazı-tura (%44,0) iken, net favorili asimetrik maçlarda
     (``min(mu) < 0.85``, ``p_draw < 0.24``, Üst/Orta lig) **7/10 (%70,0)** tuttu.
   - ``MS 1 / MS 2``: ``P >= %65 & sharp`` + beraberlik süzgeciyle **25/33 (%75,8)** tuttu.

Bu modül her aday seçimi maçın gol beklentisi (``mu_home``, ``mu_away``), marjsız 1X2 olasılıkları (``p_draw``),
kaynak kalitesi (``sharp``, ``direct``, ``league_tier``), her iki takımın ayrı ayrı geçmiş uyumu (``home_rate``,
``away_rate``, ``min_side_rate``) ve kadro/sakatlık bayrakları (``gk1_out``, ``top_scorer_out``) ile teşhis eder.
Kök hatası temiz olan seçimleri ``rehabilitated=True`` ile rehabilite eder; izinli ailelerin içindeki gizli tuzakları
ise ``ok=False`` ile yakalar.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
import re
from typing import Any

from quantfoot.evaluation.auto_learn import market_family

_NAMEFIX = {
    "MS 0 (beraberlik)": "MS 0",
    "X": "MS 0",
    "0": "MS 0",
    "1": "MS 1",
    "2": "MS 2",
}


def canonical_name(name: str | None) -> str:
    n = (name or "").strip()
    n = _NAMEFIX.get(n, n)
    n = n.replace(",", ".")
    if re.fullmatch(r"[12X0]", n):
        n = "MS " + ("0" if n in "X0" else n)
    return n


def classify_family(name: str | None) -> str:
    return market_family(canonical_name(name))
from quantfoot.markets import market_reliability as MR
from quantfoot.strategy.banko_guard import league_tier


@dataclass(frozen=True)
class MarketDiagnosis:
    ok: bool
    rehabilitated: bool
    name: str
    family: str
    p_adj: float
    residual_adjustment: float = 0.0
    reasons: tuple[str, ...] = ()
    strengths: tuple[str, ...] = ()


def _flt(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        v = float(val)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _get(ctx: Mapping[str, Any] | Any, *keys: str, default: Any = None) -> Any:
    if ctx is None:
        return default
    for k in keys:
        if isinstance(ctx, Mapping) and k in ctx and ctx[k] is not None:
            return ctx[k]
        v = getattr(ctx, k, None)
        if v is not None:
            return v
    return default


def parse_steam_pp(ctx: Mapping[str, Any] | Any, extra_flags: Any = None) -> float:
    """Keskin borsa steam büyüklüğünü (puan, mutlak değer) ctx/maç sözlüğünden çıkar."""
    res = _get(ctx, "research") if isinstance(ctx, Mapping) else None
    direct = _flt(_get(ctx, "steam_pp", "sharp_steam_pp"))
    if direct is None and isinstance(res, Mapping):
        direct = _flt(res.get("steam_pp") or res.get("sharp_steam_pp"))
    if direct is not None:
        return abs(direct)
    raw_flags = _get(ctx, "flags")
    if not raw_flags and isinstance(res, Mapping):
        raw_flags = res.get("flags")
    if not raw_flags:
        raw_flags = extra_flags
    flag_text = " ".join(str(x) for x in raw_flags) if isinstance(raw_flags, (list, tuple)) else str(raw_flags or "")
    if "steam" not in flag_text.lower():
        return 0.0
    mags = [abs(float(x.replace(",", "."))) for x in re.findall(r"([+-]?\d+(?:[.,]\d+)?)p\b", flag_text)]
    return max(mags) if mags else 0.0


def diagnose_selection(
    name: str | None,
    p: float,
    ctx: Mapping[str, Any] | Any = None,
    *,
    for_coupon: bool = True,
) -> MarketDiagnosis:
    """Seçimi kök-hata teşhisinden geçir.

    ``ctx`` içinde olabilecek alanlar (hepsi isteğe bağlı; yoksa yalnız bilinen alanlar denetlenir):
      - ``mu_home`` / ``mu_h``, ``mu_away`` / ``mu_a``: beklenen goller
      - ``p_draw``, ``p_over25``, ``p1``, ``p2``: marjsız 1X2 / 2.5 Üst olasılıkları
      - ``sharp`` (bool) veya ``tier`` ('keskin' / 'orta'), ``direct`` (bool), ``league`` (str)
      - ``home_rate``, ``away_rate``, ``mean``: takım geçmişinde bu bahsin tutma oranları
      - ``home_n``, ``away_n``: takım geçmişi maç sayıları
      - ``home_gk1_out``, ``away_gk1_out``, ``home_top_scorer_out``, ``away_top_scorer_out`` (veya ``teams`` sözlüğü)
      - ``home_gf``, ``away_gf``, ``home_ga``, ``away_ga``, ``home_score1H``, ``away_score1H``, ``home_concede1H``, ``away_concede1H``
      - ``sim_verdict`` ('üçlü onay', 'kısmi onay', 'çelişki')
    """
    cname = canonical_name(name)
    family = classify_family(cname)
    reasons: list[str] = []
    strengths: list[str] = []
    p_adj = float(p)

    if ctx is None:
        return MarketDiagnosis(ok=True, rehabilitated=False, name=cname, family=family, p_adj=p_adj)

    mu_h = _flt(_get(ctx, "mu_home", "mu_h"))
    mu_a = _flt(_get(ctx, "mu_away", "mu_a"))
    mu = _get(ctx, "mu")
    if (mu_h is None or mu_a is None) and isinstance(mu, (list, tuple)) and len(mu) == 2:
        mu_h = _flt(mu[0]) if mu_h is None else mu_h
        mu_a = _flt(mu[1]) if mu_a is None else mu_a
    mu_tot = (mu_h + mu_a) if (mu_h is not None and mu_a is not None) else None
    min_mu = min(mu_h, mu_a) if (mu_h is not None and mu_a is not None) else None
    max_mu = max(mu_h, mu_a) if (mu_h is not None and mu_a is not None) else None

    f1x2 = _get(ctx, "fair_1x2")
    p1 = _flt(_get(ctx, "p1"))
    p_draw = _flt(_get(ctx, "p_draw"))
    p2 = _flt(_get(ctx, "p2"))
    if isinstance(f1x2, (list, tuple)) and len(f1x2) == 3:
        p1 = _flt(f1x2[0]) if p1 is None else p1
        p_draw = _flt(f1x2[1]) if p_draw is None else p_draw
        p2 = _flt(f1x2[2]) if p2 is None else p2
    p_over25 = _flt(_get(ctx, "p_over25"))

    sharp_v = _get(ctx, "sharp")
    tier_s = str(_get(ctx, "tier", default="") or "")
    ref_s = str(_get(ctx, "reference", default="") or "")
    if sharp_v is not None:
        sharp = bool(sharp_v)
    elif tier_s:
        sharp = tier_s == "keskin"
    elif ref_s:
        sharp = ref_s.startswith(("Pinnacle", "Smarkets", "Matchbook", "Betfair", "OddsMath (BetInAsia", "OddsMath (Borsa"))
    else:
        sharp = True  # bağlamda kaynak belirtilmemişse kaynak engeli koyma

    direct_v = _get(ctx, "direct")
    direct = bool(direct_v) if direct_v is not None else False
    lg_name = _get(ctx, "league")
    lg_tier = league_tier(lg_name) if lg_name else None

    # Takım geçmişi: tek taraf maskelemesini yakala (bir takım %85, öteki %40 ise ortalama %62.5 yanıltır)
    hr = _flt(_get(ctx, "home_rate"))
    ar = _flt(_get(ctx, "away_rate"))
    hn = int(_flt(_get(ctx, "home_n")) or 0)
    an = int(_flt(_get(ctx, "away_n")) or 0)
    side_rates = [r for r, n in ((hr, hn), (ar, an)) if r is not None and (n >= 5 or (hn == 0 and an == 0))]
    min_side = min(side_rates) if side_rates else None
    mean_hist = _flt(_get(ctx, "mean", "hist"))
    if mean_hist is None and side_rates:
        mean_hist = sum(side_rates) / len(side_rates)

    # Takım profilleri ve eksikler
    teams = _get(ctx, "teams") or {}
    th = (teams.get("home") if isinstance(teams, Mapping) else None) or {}
    ta = (teams.get("away") if isinstance(teams, Mapping) else None) or {}
    h_gk_out = bool(_get(ctx, "home_gk1_out") or th.get("gk1_out"))
    a_gk_out = bool(_get(ctx, "away_gk1_out") or ta.get("gk1_out"))
    h_sc_out = bool(_get(ctx, "home_top_scorer_out") or th.get("top_scorer_out"))
    a_sc_out = bool(_get(ctx, "away_top_scorer_out") or ta.get("top_scorer_out"))
    h_gf = _flt(_get(ctx, "home_gf") or th.get("gf"))
    a_gf = _flt(_get(ctx, "away_gf") or ta.get("gf"))
    h_ga = _flt(_get(ctx, "home_ga") or th.get("ga"))
    a_ga = _flt(_get(ctx, "away_ga") or ta.get("ga"))
    h_s1 = _flt(_get(ctx, "home_score1H") or th.get("score1H"))
    a_s1 = _flt(_get(ctx, "away_score1H") or ta.get("score1H"))
    h_c1 = _flt(_get(ctx, "home_concede1H") or th.get("concede1H"))
    a_c1 = _flt(_get(ctx, "away_concede1H") or ta.get("concede1H"))

    sim_verdict = str(_get(ctx, "sim_verdict", default="") or "")

    # Keskin borsa steam büyüklüğü (puan): 22 Kas 427 maç denetiminde ≥6p sert steam varken
    # MS 1/2 %43,8 (-20,6p; steam yokken %68,6) ve Alt bahisleri %58,6 (-3,0p; Getafe İY 0-2, Huancayo İY 3-0) çöktü!
    steam_pp = parse_steam_pp(ctx)

    # Genel kural 1: Tek taraf geçmiş çelişkisi (bir takımın son maçlarında bu bahis <%45 veya modelin >20p altında)
    if min_side is not None and len(side_rates) == 2:
        if min_side < 0.45 or min_side < p - 0.22:
            reasons.append(f"tek taraf geçmiş çelişkisi: zayıf taraf %{100 * min_side:.0f} (ortalama %{100 * (mean_hist or 0):.0f} maskeliyor)")
        elif min_side >= p - 0.05:
            strengths.append(f"iki takım geçmişi de ayrı ayrı destekliyor (en düşük %{100 * min_side:.0f})")

    if sim_verdict == "çelişki":
        reasons.append("simülasyon çelişkisi: bağımsız gol simülasyonu piyasa fiyatını desteklemiyor")
    elif sim_verdict == "üçlü onay":
        strengths.append("piyasa + simülasyon + geçmiş üçlü onaylı")

    rehabilitated = False

    # ------------------------------------------------------------------ 0. Tek/Çift (Parite Gürültüsü — İY Çift dahil!)
    # Not: market_family("İY Çift") "İlk yarı" döndürdüğü için aileye değil isme göre en başta yakalanır!
    if family == "Tek/Çift" or cname in ("Tek", "Çift", "İY Tek", "İY Çift", "2Y Tek", "2Y Çift"):
        # 22 Kas: İY Çift 26/58 (%44,8 vs P %56,4 = -11,6p); parite pazarları yüksek varyanslı gürültüdür
        p_adj = max(0.0, p_adj - 0.06)
        reasons.append(f"{cname}: Tek/Çift yüksek varyanslı parite gürültüsüdür (22 Kas: İY Çift %44,8 vs P %56,4, -11,6p)")

    # ------------------------------------------------------------------ 1. Karşılıklı Gol (KG Var / KG Yok)
    elif family == "Karşılıklı gol":
        if not sharp:
            reasons.append("KG ailesinde keskin referans zorunlu (21 Kas: orta bürolarda KG Yok %45,7'de kaldı)")
        if cname == "KG Var":
            if min_mu is not None and min_mu < 1.12:
                reasons.append(f"KG Var tek taraflı xG tuzağı: zayıf taraf xG {min_mu:.2f} < 1.12 (21-22 Kas: dengesiz maçta çöküyor)")
            if mu_tot is not None and mu_tot < 2.75:
                reasons.append(f"KG Var düşük toplam gol riski: toplam xG {mu_tot:.2f} < 2.75")
            if h_sc_out or a_sc_out:
                reasons.append("KG Var riskli: takımlardan birinin 1. golcüsü eksik")
            if (h_gf is not None and h_gf < 1.05) or (a_gf is not None and a_gf < 1.05):
                reasons.append("KG Var riskli: takımlardan birinin maç başı gol ortalaması < 1.05")
            if lg_tier in ("2", "other") and not direct and (min_side is None or min_side < 0.60):
                reasons.append("KG Var 2. kademe/diğer ligde doğrudan borsa kotasyonu veya ≥%60 çift taraflı geçmiş şart")
            if not reasons and (min_mu is not None and min_mu >= 1.12) and (mu_tot is None or mu_tot >= 2.75) and (min_side is None or min_side >= 0.60):
                rehabilitated = True
                strengths.append("KG Var rehabilite: dengeli çift taraflı xG (≥1.12), tempo ≥2.75 ve geçmiş uyumlu")
        elif cname == "KG Yok":
            if mu_tot is not None and mu_tot > 2.45:
                reasons.append(f"KG Yok yüksek toplam gol tuzağı: toplam xG {mu_tot:.2f} > 2.45 (fark maçlarında teselli golü riski)")
            if min_mu is not None and min_mu > 0.75:
                reasons.append(f"KG Yok riskli: zayıf tarafın gol beklentisi {min_mu:.2f} > 0.75")
            if h_gk_out or a_gk_out:
                reasons.append("KG Yok riskli: 1. kaleci eksikliği temiz çarşaf olasılığını düşürüyor")
            if not reasons and sharp and (mu_tot is not None and mu_tot <= 2.45) and (min_mu is not None and min_mu <= 0.75):
                rehabilitated = True
                strengths.append("KG Yok rehabilite: keskin referans + düşük toplam xG (≤2.45) + kısır zayıf taraf (≤0.75)")

    # ------------------------------------------------------------------ 2. Ev Sahibi / Deplasman Takım Golleri
    elif family in ("Ev sahibi golleri", "Deplasman golleri"):
        is_home_team = family == "Ev sahibi golleri"
        team_mu = mu_h if is_home_team else mu_a
        opp_gk_out = a_gk_out if is_home_team else h_gk_out
        my_gk_out = h_gk_out if is_home_team else a_gk_out
        my_sc_out = h_sc_out if is_home_team else a_sc_out
        my_gf = h_gf if is_home_team else a_gf
        opp_ga = a_ga if is_home_team else h_ga
        my_s1 = h_s1 if is_home_team else a_s1
        opp_c1 = a_c1 if is_home_team else h_c1
        is_half_team_market = (" İY " in cname) or (" 2Y " in cname)

        if cname in ("Ev İY 0.5 Üst", "Dep İY 0.5 Üst"):
            # 21 Kas Ev İY 0.5 Üst: %43,3 (-17,2p); 22 Kas Dep İY 0.5 Üst: %37,5 (-21,5p, kuponda 0/4).
            # Deplasman takımları gollerinin yalnız ~%41,7'sini 1. yarıda atıyor; asla tam-maç kuralına düşmemeli!
            p_adj = max(0.0, p_adj - 0.08)
            need_mu_1h = 1.90 if is_home_team else 1.95
            need_s1 = 0.70 if is_home_team else 0.68
            need_c1 = 0.60 if is_home_team else 0.58
            if lg_tier == "3":
                reasons.append(f"{cname}: alt/genç/kadın liglerinde ilk yarı takım golü varyansı aşırı yüksek")
            if my_s1 is None or my_s1 < need_s1 or opp_c1 is None or opp_c1 < need_c1 or (team_mu is not None and team_mu < need_mu_1h):
                reasons.append(f"{cname} ilk yarı düşük blok / geç açılma tuzağı (21-22 Kas: -17p ila -21p sapma)")
            elif my_sc_out or not sharp:
                reasons.append(f"{cname}: keskin referans ve 1. golcünün kadroda olması şart")
            elif not reasons:
                rehabilitated = True
                strengths.append(f"{cname} rehabilite: 1Y gol ≥%{int(100*need_s1)} ve rakip 1Y gol yeme ≥%{int(100*need_c1)}")
        elif " İY 0.5 Alt" in cname:
            # Dep İY 0.5 Alt / Ev İY 0.5 Alt: yalnız karşı takımın xG'si < 0.88, yetişkin keskin lig ve kaleci tam ise kalibre
            # (21 Kas: %68,6; 22 Kas rehabilite Dep İY 0.5 Alt: 7/10 = %70,0, +0,7p)
            if not sharp:
                reasons.append(f"{cname}: orta büroda %44,4'te kaldı, keskin referans şart")
            if lg_tier == "3":
                reasons.append(f"{cname}: alt/genç/kadın liglerinde %39,1'de kaldı (erken gol varyansı yüksek)")
            mu_cap = 0.88 if lg_tier in ("1", "2", None) else 0.80
            if team_mu is not None and team_mu >= mu_cap:
                reasons.append(f"{cname}: takımın maç gol beklentisi {team_mu:.2f} ≥ {mu_cap:.2f} (dengeli maçta %42,2'ye düşüyor)")
            if my_s1 is not None and my_s1 >= 0.42:
                reasons.append(f"{cname}: takım son maçlarının %{100 * my_s1:.0f}'inde ilk yarı gol attı")
            if opp_gk_out:
                reasons.append(f"{cname}: savunan takımın 1. kalecisi eksik")
            if not reasons and sharp and lg_tier in ("1", "2", "other", None) and (team_mu is not None and team_mu < mu_cap):
                rehabilitated = True
                strengths.append(f"{cname} rehabilite: düşük rakip xG ({team_mu:.2f} < {mu_cap:.2f}) + keskin referans")
        elif is_half_team_market:
            # Ev/Dep 2Y ... veya İY 1.5 ... gibi diğer takım-yarı pazarları yüksek varyanslı; tam-maç dalına düşmez
            p_adj = max(0.0, p_adj - 0.05)
            reasons.append(f"{cname}: takım yarı-bazlı türev pazar (yüksek varyans, kupon rehabilitasyonu kapalı)")
        elif cname.endswith("1.5 Alt"):
            # 22 Kas: Dep 1.5 Alt %66,3 (+3,6p), Ev 1.5 Alt %64,4 (+2,6p) — kaleci sağlam + xG < 1.12 iken güçlü
            if not sharp:
                reasons.append(f"{cname}: keskin referans şart")
            if team_mu is not None and team_mu >= 1.12:
                reasons.append(f"{cname}: takım gol beklentisi {team_mu:.2f} ≥ 1.12 (2+ gol sürpriz riski yüksek)")
            if my_gf is not None and my_gf >= 1.45:
                reasons.append(f"{cname}: takım maç başı {my_gf:.2f} gol atıyor")
            if opp_gk_out:
                reasons.append(f"{cname}: savunan takımın 1. kalecisi eksik")
            if is_home_team is False and lg_tier == "other" and (min_side is None or min_side < 0.68):
                reasons.append("Dep 1.5 Alt 'diğer' lig kademesinde %50,8'de kaldı; çift taraflı ≥%68 geçmiş şart")
            if not reasons and sharp and (team_mu is not None and team_mu < 1.12) and (min_side is None or min_side >= 0.65):
                rehabilitated = True
                strengths.append(f"{cname} rehabilite: takım xG {team_mu:.2f} < 1.12 ve geçmiş uyumlu")
        elif cname.endswith("2.5 Alt"):
            # Ev 2.5 Alt (21 Kas %75,0; 22 Kas 16/21 = %76,2) ve Dep 2.5 Alt (%75+): ailenin en sağlam dilimi!
            if team_mu is not None and team_mu >= 1.68:
                reasons.append(f"{cname}: takım gol beklentisi {team_mu:.2f} ≥ 1.68")
            if opp_gk_out:
                reasons.append(f"{cname}: savunan takımın 1. kalecisi eksik")
            if not reasons and sharp and (team_mu is None or team_mu < 1.68):
                rehabilitated = True
                strengths.append(f"{cname} rehabilite: 21-22 Kas denetiminde %75+ isabetli güvenli dilim")
        elif cname.endswith(("0.5 Üst", "1.5 Üst")):
            # Yalnız TAM MAÇ takım gol üstleri (İY/2Y yukarıda ayrıldı)
            if cname.endswith("0.5 Üst"):
                need_mu = 1.25
            else:
                # 22 Kas: Ev 1.5 Üst rehabilite 12/19 (%63,2, +3,3p), Dep 1.5 Üst 8/15 (%53,3, -7,3p) → Dep eşiği 2.00
                need_mu = 1.85 if is_home_team else 2.00
            if not sharp:
                reasons.append(f"{cname}: keskin referans şart")
            if not is_home_team and cname.endswith("1.5 Üst"):
                if lg_tier == "3":
                    reasons.append("Dep 1.5 Üst: alt/genç/kadın liglerinde deplasman 2+ gol varyansı yüksek")
                if not direct and (team_mu is None or team_mu < 2.15):
                    reasons.append("Dep 1.5 Üst: doğrudan borsa fiyatı yoksa deplasman xG ≥ 2.15 şart (22 Kas: türetilmiş Dep 1.5 Üst %44,4)")
            if my_sc_out:
                reasons.append(f"{cname}: gol beklenen takımın 1. golcüsü eksik")
            if team_mu is not None and team_mu < need_mu:
                reasons.append(f"{cname}: takım gol beklentisi {team_mu:.2f} < {need_mu:.2f}")
            if opp_ga is not None and opp_ga < 0.95:
                reasons.append(f"{cname}: rakip maç başı yalnız {opp_ga:.2f} gol yiyor (katı savunma)")
            if not reasons and sharp and (team_mu is not None and team_mu >= need_mu) and (min_side is None or min_side >= 0.65):
                rehabilitated = True
                strengths.append(f"{cname} rehabilite: güçlü takım xG ({team_mu:.2f} ≥ {need_mu:.2f}) ve geçmiş uyumlu")

    # ------------------------------------------------------------------ 3. İlk Gol (İlk Gol Ev / İlk Gol Dep)
    elif family == "İlk gol":
        is_home_first = "1" in cname or "Ev" in cname
        my_mu = mu_h if is_home_first else mu_a
        opp_mu = mu_a if is_home_first else mu_h
        my_sc_out = h_sc_out if is_home_first else a_sc_out
        my_s1 = h_s1 if is_home_first else a_s1
        opp_s1 = a_s1 if is_home_first else h_s1
        if not sharp or lg_tier in ("other", "3"):
            reasons.append("İlk Gol yalnız 1. ve 2. kademe keskin liglerde güvenilir (diğer/alt ligde %45,8)")
        if min_mu is not None and min_mu >= 0.90:
            reasons.append(f"İlk Gol dengeli maç tuzağı: rakip xG {min_mu:.2f} ≥ 0.90 (21 Kas: dengeli maçta %44,0 yazı-tura)")
        if my_mu is not None and opp_mu is not None and (my_mu - opp_mu) < 1.05:
            reasons.append("İlk Gol için net xG üstünlüğü (≥1.05 fark) şart")
        if p_draw is not None and p_draw >= 0.25:
            reasons.append(f"İlk Gol beraberlik/0-0 riski yüksek (P(X)={p_draw:.2f} ≥ 0.25)")
        if my_sc_out:
            reasons.append("İlk Gol beklenen takımın 1. golcüsü eksik")
        if (my_s1 is not None and my_s1 < 0.55) or (opp_s1 is not None and opp_s1 > 0.38):
            reasons.append("İlk Gol: takımın ilk yarı gol bulma hızı düşük veya rakip erken gol atıyor")
        if not reasons and sharp and (min_mu is not None and min_mu < 0.90) and (my_mu is not None and my_mu >= 1.85):
            rehabilitated = True
            strengths.append("İlk Gol rehabilite: net asimetrik favori (rakip xG < 0.90) + üst/orta kademe keskin lig")

    # ------------------------------------------------------------------ 4. Çifte Şans ve Handikap
    elif family in ("Çifte şans", "Handikap"):
        if not sharp:
            reasons.append(f"{family}: keskin referans zorunlu")
        if cname == "ÇŞ 12":
            dr_risk = MR.draw_risk(p_draw, p_over25) if p_draw is not None else None
            if (dr_risk is not None and dr_risk >= 0.24) or (p_draw is not None and p_draw >= 0.24):
                reasons.append(f"ÇŞ 12 beraberlik tuzağı: beraberlik riski yüksek ({(dr_risk or p_draw):.2f} ≥ 0.24)")
            if mu_tot is not None and mu_tot < 2.75:
                reasons.append(f"ÇŞ 12 düşük toplam gol tuzağı: toplam xG {mu_tot:.2f} < 2.75 (0-0 / 1-1 riski)")
            if not reasons and sharp and (mu_tot is not None and mu_tot >= 2.75) and (p_draw is not None and p_draw < 0.24):
                rehabilitated = True
                strengths.append("ÇŞ 12 rehabilite: yüksek tempo (xG ≥ 2.75) ve düşük beraberlik riski (<%24)")
        elif cname in ("ÇŞ 1X", "ÇŞ X2", "Hnd(+1) 1", "Hnd(-1) 2", "Hnd(-2) 2"):
            backing_home = cname in ("ÇŞ 1X", "Hnd(+1) 1")
            my_gk = h_gk_out if backing_home else a_gk_out
            my_sc = h_sc_out if backing_home else a_sc_out
            if my_gk or my_sc:
                reasons.append(f"{cname}: desteklenen tarafın 1. kalecisi veya gol kralı eksik")
            if cname in ("ÇŞ X2", "Hnd(-1) 2"):
                # 21 Kas: p_draw < 0.25 veya mu_tot >= 2.8 iken Hnd(-1) 2 / ÇŞ X2 %42–%51'e çöktü
                # 22 Kas: engellenen ÇŞ X2 %45,2 (-16p), rehabilite edilen ÇŞ X2 6/8 (%75,0, +9,2p)!
                if p1 is not None and p1 >= 0.42:
                    reasons.append(f"{cname}: ev sahibi güçlü ({p1:.2f} ≥ 0.42), deplasman çifte şans %42,3'e düşüyor")
                if mu_tot is not None and mu_tot >= 2.80 and cname == "Hnd(-1) 2":
                    reasons.append(f"{cname}: yüksek gollü maçta ({mu_tot:.2f} ≥ 2.80) +1 handikap %51,0'da kaldı")
            if cname == "ÇŞ 1X":
                # 22 Kas: rehabilite ÇŞ 1X 2/5 (%40,0) — güçlü deplasmana karşı ev çifte şans tuzağı
                if p2 is not None and p2 >= 0.36:
                    reasons.append(f"ÇŞ 1X: deplasman güçlü ({p2:.2f} ≥ 0.36), ev çifte şansı kırılgan")
                if mu_a is not None and mu_a >= 1.30:
                    reasons.append(f"ÇŞ 1X: deplasman gol beklentisi yüksek ({mu_a:.2f} ≥ 1.30)")
            if lg_tier in ("2", "other") and not direct and cname != "Hnd(-2) 2" and (min_side is None or min_side < 0.70):
                reasons.append(f"{cname}: 2. kademe/diğer ligde doğrudan borsa kotasyonu veya ≥%70 çift taraflı geçmiş şart")
            if not reasons and sharp and (direct or lg_tier == "1" or cname in ("Hnd(+1) 1", "Hnd(-2) 2")) and (min_side is None or min_side >= 0.68):
                rehabilitated = True
                strengths.append(f"{cname} rehabilite: keskin referans + sağlam savunma/geçmiş profili")
        else:
            # Hnd(-1) 1 vb. 2+ fark gerektiren handikaplar
            backing_home = "1" in cname.split()[-1]
            my_mu = mu_h if backing_home else mu_a
            opp_mu = mu_a if backing_home else mu_h
            if my_mu is None or opp_mu is None or (my_mu - opp_mu) < 1.35 or opp_mu > 0.75:
                reasons.append(f"{cname}: 2+ fark handikabı için xG farkı ≥ 1.35 ve rakip xG ≤ 0.75 şart")
            if (h_sc_out if backing_home else a_sc_out) or (h_gk_out if backing_home else a_gk_out):
                reasons.append(f"{cname}: favoride kilit kaleci/golcü eksik")
            if not reasons and sharp and (min_side is not None and min_side >= 0.68):
                rehabilitated = True
                strengths.append(f"{cname} rehabilite: baskın xG farkı (≥1.35) + çift taraflı geçmiş ≥%68")

    # ------------------------------------------------------------------ 5. İzinli Ailelerin İçindeki Gizli Tuzaklar
    elif family == "İlk yarı":
        if cname == "İY ÇŞ 12":
            # 22 Kas 427 maç: İY ÇŞ 12 [MOD] 48/99 (%48,5 vs P %62,9 = -14,4p)!
            # İlk yarıda 0-0 / 1-1 beraberlik oranı gerçek futbolda %42–48; model sistematik hafife alıyor.
            p_adj = max(0.0, p_adj - 0.08)
            diff_mu = abs(mu_h - mu_a) if (mu_h is not None and mu_a is not None) else None
            if (mu_tot is None or mu_tot < 3.20) or (diff_mu is None or diff_mu < 1.10):
                reasons.append("İY ÇŞ 12 gizli ilk-yarı beraberlik tuzağı (22 Kas: 48/99 = %48,5, -14,4p; xG≥3.20 ve fark≥1.10 şart)")
            if p_draw is not None and p_draw >= 0.22:
                reasons.append(f"İY ÇŞ 12 beraberlik riski yüksek (P(X)={p_draw:.2f} ≥ 0.22)")
        elif cname == "İY 1.5 Alt" and for_coupon:
            # 21 Kas: P>=65%'te min(mu_h, mu_a) >= 1.05 veya p_draw >= 0.27 iken 2. lig/diğer liglerde %44'e çöktü!
            if lg_tier != "1" and min_mu is not None and min_mu >= 1.05:
                reasons.append(f"İY 1.5 Alt tuzağı (çift taraflı hücum): her iki takımın xG'si ≥ 1.05 ({min_mu:.2f}; 21 Kas'ta %44,0 tuttu)")
            if mu_tot is not None and mu_tot >= 2.85:
                reasons.append(f"İY 1.5 Alt tuzağı (yüksek toplam gol): toplam xG {mu_tot:.2f} ≥ 2.85")
            if steam_pp >= 5.5:
                p_adj = max(0.0, p_adj - 0.04)
                reasons.append(f"İY 1.5 Alt sert steam tuzağı ({steam_pp:.1f}p ≥ 5.5p; 22 Kas: Getafe İY 0-2, Huancayo İY 3-0)")
            if h_gk_out or a_gk_out:
                reasons.append("İY 1.5 Alt riskli: 1. kaleci eksik")
        elif cname == "İY 0.5 Üst":
            if mu_tot is not None and mu_tot < 2.50:
                reasons.append(f"İY 0.5 Üst düşük tempo tuzağı: toplam xG {mu_tot:.2f} < 2.50")
            if h_sc_out and a_sc_out:
                reasons.append("İY 0.5 Üst riskli: iki takımın da golcüsü eksik")

    elif family == "Kombine (A & B)":
        if cname == "İY KG Yok & 2Y KG Yok":
            # 22 Kas 427 maç: 19/26 (%73,1 vs P %63,0 = +10,0p) — kaleci sağlam ve toplam xG ≤ 2.65 iken çok güçlü!
            if mu_tot is not None and mu_tot > 2.65:
                reasons.append(f"İY KG Yok & 2Y KG Yok: toplam xG {mu_tot:.2f} > 2.65 (yüksek tempo riski)")
            if h_gk_out or a_gk_out:
                reasons.append("İY KG Yok & 2Y KG Yok: 1. kaleci eksik")
            if not reasons and sharp and (mu_tot is not None and mu_tot <= 2.65):
                rehabilitated = True
                strengths.append("İY KG Yok & 2Y KG Yok rehabilite: 22 Kas 19/26 (%73,1, +10p) + düşük tempo")

    elif family == "Yarı özel":
        if cname == "Ev En Az Bir Yarıyı Kazanır":
            # 21 Kas: 13/27 (%48.1 vs P %62.4, -14.3p) — ailenin içindeki gizli kayıp dilimi
            p_adj = max(0.0, p_adj - 0.06)
            if p_draw is not None and p_draw >= 0.23:
                reasons.append("Ev En Az Bir Yarıyı Kazanır beraberlik tuzağı (21 Kas: %48,1 tuttu, -14,3p)")
            if mu_h is None or mu_a is None or (mu_h - mu_a) < 1.10:
                reasons.append("Ev En Az Bir Yarıyı Kazanır gizli tuzak dilimi (21 Kas: %48,1 tuttu; net xG farkı ≥ 1.10 şart)")
            if h_sc_out or h_gk_out:
                reasons.append("Ev En Az Bir Yarıyı Kazanır: ev sahibinde kaleci/golcü eksik")
        elif cname == "Dep En Az Bir Yarıyı Kazanır":
            p_adj = max(0.0, p_adj - 0.05)
            if p_draw is not None and p_draw >= 0.23:
                reasons.append("Dep En Az Bir Yarıyı Kazanır beraberlik tuzağı (P(X) ≥ 0.23)")
            if mu_h is None or mu_a is None or (mu_a - mu_h) < 1.10:
                reasons.append("Dep En Az Bir Yarıyı Kazanır için net deplasman xG farkı ≥ 1.10 şart")
            if a_sc_out or a_gk_out:
                reasons.append("Dep En Az Bir Yarıyı Kazanır: deplasmanda kaleci/golcü eksik")
        elif cname == "DEĞİL(Ev İki Yarıda Gol)":
            # 22 Kas 427 maç: 17/33 (%51,5 vs P %66,4 = -14,9p) — güçlü ev sahibine (mu_h ≥ 1.60) karşı atamaz almak tuzak!
            if mu_h is not None and mu_h >= 1.60:
                p_adj = max(0.0, p_adj - 0.06)
                reasons.append(f"DEĞİL(Ev İki Yarıda Gol) güçlü ev hücum tuzağı: ev xG {mu_h:.2f} ≥ 1.60 (22 Kas: %51,5 tuttu, -14,9p)")
            if h_gf is not None and h_gf >= 1.80:
                reasons.append(f"DEĞİL(Ev İki Yarıda Gol): ev sahibi maç başı {h_gf:.2f} gol atıyor")
            if a_gk_out:
                reasons.append("DEĞİL(Ev İki Yarıda Gol): deplasman 1. kalecisi eksik")
        elif cname == "DEĞİL(Dep İki Yarıda Gol)":
            if mu_a is not None and mu_a >= 1.60:
                p_adj = max(0.0, p_adj - 0.05)
                reasons.append(f"DEĞİL(Dep İki Yarıda Gol) güçlü deplasman hücum tuzağı: dep xG {mu_a:.2f} ≥ 1.60")
            if a_gf is not None and a_gf >= 1.75:
                reasons.append(f"DEĞİL(Dep İki Yarıda Gol): deplasman maç başı {a_gf:.2f} gol atıyor")
            if h_gk_out:
                reasons.append("DEĞİL(Dep İki Yarıda Gol): ev sahibi 1. kalecisi eksik")

    elif family == "Alt/Üst":
        if cname == "2.5 Üst":
            if mu_tot is not None and mu_tot < 2.80:
                reasons.append(f"2.5 Üst düşük toplam xG tuzağı: {mu_tot:.2f} < 2.80")
            if min_mu is not None and min_mu < 0.85:
                reasons.append(f"2.5 Üst tek taraflı maç tuzağı: zayıf taraf xG {min_mu:.2f} < 0.85 (1-0 / 2-0 bitme riski)")
            if h_sc_out and a_sc_out:
                reasons.append("2.5 Üst riskli: iki takımın da golcüsü eksik")
        elif cname == "3.5 Alt":
            # 21 Kas %69,7 (+6,8p), 22 Kas %66,7 (+1,8p DIR) — 3.10 dengeli tavan
            if mu_tot is not None and mu_tot > 3.10:
                reasons.append(f"3.5 Alt yüksek gol beklentisi tuzağı: toplam xG {mu_tot:.2f} > 3.10")
            if for_coupon and steam_pp >= 6.5:
                reasons.append(f"3.5 Alt sert steam volatilitesi ({steam_pp:.1f}p ≥ 6.5p)")
            if h_gk_out or a_gk_out:
                reasons.append("3.5 Alt riskli: 1. kaleci eksik (4+ gol patlama riski)")
        elif cname == "2.5 Alt":
            if mu_tot is not None and mu_tot > 2.25:
                reasons.append(f"2.5 Alt gol beklentisi yüksek: toplam xG {mu_tot:.2f} > 2.25")
            if for_coupon and steam_pp >= 5.5:
                reasons.append(f"2.5 Alt sert steam volatilitesi ({steam_pp:.1f}p ≥ 5.5p)")
            if h_gk_out or a_gk_out:
                reasons.append("2.5 Alt riskli: 1. kaleci eksik")

    elif family == "Maç sonucu":
        if cname in ("MS 1", "MS 2"):
            backing_home = cname == "MS 1"
            dr_risk = MR.draw_risk(p_draw, p_over25) if p_draw is not None else None
            if (dr_risk is not None and dr_risk >= 0.26) or (p_draw is not None and p_draw >= 0.26):
                reasons.append(f"{cname} yüksek beraberlik riski ({(dr_risk or p_draw):.2f} ≥ 0.26)")
            if mu_tot is not None and mu_tot < 2.25 and max_mu is not None and min_mu is not None and (max_mu - min_mu) < 1.00:
                reasons.append(f"{cname} kısır maç 0-0/1-1 tuzağı (toplam xG {mu_tot:.2f} < 2.25, fark < 1.00)")
            if for_coupon and steam_pp >= 6.0:
                # 22 Kas 427 maç: no_steam MS 1/2 = 48/70 (%68,6) vs strong_steam>=6p = 7/16 (%43,8, -20,6p)!
                p_adj = max(0.0, p_adj - 0.08)
                reasons.append(f"{cname} sert steam volatilite tuzağı ({steam_pp:.1f}p ≥ 6.0p; 22 Kas: %43,8 vs steam yokken %68,6)")
            if (h_gk_out if backing_home else a_gk_out) or (h_sc_out if backing_home else a_sc_out):
                reasons.append(f"{cname}: favori takımda 1. kaleci veya gol kralı eksik")

    # Alt/genç/kadın liglerinde (tier 3) türetilmiş + yüksek-P (≥%70) aşırı iyimserlik koruması
    # (yetişkin liglerde bant kırpması coupon_rules.calibrate_p ile uygulanır, çift sayım yapılmaz).
    if for_coupon and not direct and float(p or 0.0) >= 0.70 and lg_tier == "3":
        p_adj = max(0.0, p_adj - 0.025)

    p_base = float(p or 0.0)
    final_p_adj = round(min(1.0, max(0.0, p_adj)), 5)
    return MarketDiagnosis(
        ok=not reasons,
        rehabilitated=rehabilitated and not reasons,
        name=cname,
        family=family,
        p_adj=final_p_adj,
        residual_adjustment=round(final_p_adj - p_base, 5),
        reasons=tuple(reasons),
        strengths=tuple(strengths),
    )

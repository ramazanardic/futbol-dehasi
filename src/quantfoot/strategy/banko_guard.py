"""Banko/garanti kupon koruması — 21 Kasım 2026 denetiminden çıkan kurallar.

Kullanıcı kuralı (t57u): varsayılan banko kupon; her bacak yüksek olasılıklı (P ≥ %65, oran ≈1.20–1.80),
tek bir yüksek oranlı riskli bacakla toplam şişirilmez. Denetimde görülen hatalar ve karşılık gelen kural:

* Kupon 1–6 (≈20–26 oran) 2.3–4.1 oranlı beraberlik/İY bacaklarıyla kuruldu, P(kupon) %2.5–3.5 → ``LOTTERY_P_WIN``.
* Pécs "Dep 0,5 Alt" Nesine bülteninde yoktu, kupon kurulamadı → ``offered`` zorunlu.
* 1.20–1.21'lik bacaklar oynarken 1.17/1.19'a düştü → seçim anında ``BANKO_SELECT_MIN_ODDS`` tamponu.
* Canlı bacaklar doğrulanmamış canlı modelin P'siyle seçildi (piyasadan +14 puan) → canlıda piyasa P'si zorunlu.
* Aynı maç birden çok kuponda (Linfield, Catanzaro, Elche B, Coleraine) → ``BANKO_MAX_COUPONS_PER_MATCH``.

Akşam denetimi (21 Kas, ~320 bitmiş maç, tek gün — küçük örnek; ``reports/research/kalibrasyon_dersleri_21kasim.md``):

* Türetilmiş (matris) P iyimser → ``effective_prob`` 50'ye doğru büzer (``SHRINK_DERIVED``), "diğer" kademe liglerde
  ek büzme (``SHRINK_OTHER_TIER_EXTRA``). Banko P tabanı ve P(kupon) büzülmüş P ile hesaplanır.
* Ev sahibi golleri / çifte şans (``WEAK_FAMILIES``) banko modunda yalnız doğrudan keskin fiyatla ve +5 puan P ile.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from quantfoot import settings as S


@dataclass(frozen=True)
class BankoLeg:
    match_id: str | int
    label: str
    odds: float
    p: float                       # kalibre/piyasaya büzülmüş olasılık
    offered: bool = True           # seçim Nesine bülteninde birebir var mı
    sharp_ref: bool = True         # keskin (marjsız) referans fiyatı var mı
    live: bool = False
    p_market: float | None = None  # canlı bacakta marjsız piyasa P'si
    red_flags: tuple[str, ...] = ()
    direct: bool | None = None     # seçimin kendi doğrudan keskin fiyatı var mı (False = matris/gol modeli; None = bilinmiyor)
    league: str | None = None      # lig adı (kademe büzmesi için)
    family: str | None = None      # None → etiketten çıkarılır (``selection_family``)


# ---------------------------------------------------------------- aile / lig kademesi / büzme

_HOME_GOALS = re.compile(r"^(ev|ev sahibi)( iy| 1\. yarı)? \d+[.,]5 (alt|üst)$", re.I)
_DOUBLE_CHANCE = re.compile(r"^(çş|çifte şans)[: ]", re.I)


def selection_family(name: str) -> str | None:
    """Seçim adı → denetim ailesi (yalnız ders çıkarılan aileler). "Ev 1.5 Üst", "Ev İY 0,5 Alt" → ``ev_golleri``;
    "ÇŞ 1X", "Çifte Şans: 1-X" → ``cifte_sans`` (İY ÇŞ ayrı aile, denetimde ilk yarı iyi çıktı)."""
    n = " ".join((name or "").strip().split())
    if _HOME_GOALS.match(n):
        return "ev_golleri"
    if _DOUBLE_CHANCE.match(n):
        return "cifte_sans"
    return None


_TIER3 = re.compile(
    r"u1[5789]|u2\d|gençler|genç |kadın|\(k\)| kdn|rezerv|amatör|bölgesel|isthmian|güney ligi|kuzey premier|"
    r"ulusal lig|3\. lig|4\. lig|3\. federasyon|4\. federasyon|regionalliga|oberliga|play.?off", re.I)
_TIER1 = re.compile(
    r"ingiltere premier|premier league|la liga$|ispanya la liga|bundesliga$|almanya bundesliga|italya serie a|"
    r"serie a$|ligue 1|süper lig$|türkiye süper lig|eredivisie|portekiz liga|belçika pro|iskoçya prem|"
    r"şampiyonlar l|avrupa ligi|konferans lig|brazilya serie a|brezilya serie a|arjantin liga|liga mx|"
    r"mls$|major league soccer", re.I)
_TIER2 = re.compile(
    r"championship|ingiltere 1\. lig|ingiltere 2\. lig|serie b|ligue 2|2\. bundesliga|la liga 2|2\. lig|primera|"
    r"eerste|liga portugal 2", re.I)


def league_tier(league: str | None) -> str | None:
    """Lig adı → kaba kademe (denetim_aksam ile aynı sınıflama): ``1`` büyük, ``2`` ikinci/orta, ``other`` diğer,
    ``3`` alt/genç/kadın; ad yoksa None (ek büzme yok)."""
    lg = (league or "").strip().replace("İ", "i").lower()  # Türkçe "İ".lower() → "i̇" olmasın
    if not lg:
        return None
    if _TIER3.search(lg):
        return "3"
    if _TIER1.search(lg):
        return "1"
    if _TIER2.search(lg):
        return "2"
    return "other"


@dataclass(frozen=True)
class ShrinkConfig:
    derived: float = S.SHRINK_DERIVED
    direct: float = S.SHRINK_DIRECT
    other_tier_extra: float = S.SHRINK_OTHER_TIER_EXTRA
    unknown_is_derived: bool = True    # kaynağı bilinmeyen P türetilmiş sayılır (temkinli)


def shrink_toward_half(p: float, k: float) -> float:
    """p > 0.5 ise 0.5'e doğru k oranında büz; p ≤ 0.5 asla yükseltilmez (dürüst P yalnız aşağı düzeltilir)."""
    k = min(max(k, 0.0), 1.0)
    return p if p <= 0.5 else 0.5 + (p - 0.5) * (1.0 - k)


def effective_prob(leg: "BankoLeg", sc: "ShrinkConfig | None" = None) -> float:
    """Kupon kararlarında kullanılan P: canlıda piyasa tavanı, canlı dışında denetim büzmesi."""
    sc = sc or ShrinkConfig()
    p = leg.p
    if leg.live:
        return p if leg.p_market is None else min(p, leg.p_market + 0.05)
    derived = (leg.direct is False) or (leg.direct is None and sc.unknown_is_derived)
    k = sc.derived if derived else sc.direct
    if league_tier(leg.league) == "other":
        k = 1.0 - (1.0 - k) * (1.0 - (sc.other_tier_extra if derived else sc.other_tier_extra / 2))
    return shrink_toward_half(p, k)


@dataclass
class GuardConfig:
    min_prob: float = S.BANKO_MIN_PROB
    min_odds: float = S.MIN_LEG_ODDS
    select_min_odds: float = S.BANKO_SELECT_MIN_ODDS
    max_leg_odds: float = S.BANKO_MAX_LEG_ODDS
    max_coupons_per_match: int = S.BANKO_MAX_COUPONS_PER_MATCH
    lottery_p_win: float = S.LOTTERY_P_WIN
    require_sharp: bool = True
    min_legs: int = 1              # 0/1 = sınır yok (eski çağrılar); kupon modları 5/3 verir
    max_legs: int = 99
    lottery_is_error: bool = True  # risk modunda P(kupon) düşükse yalnız dürüst uyarı
    name: str = "banko"
    shrink: ShrinkConfig = field(default_factory=ShrinkConfig)
    weak_families: tuple[str, ...] = S.WEAK_FAMILIES   # boş tuple = aile kuralı kapalı (risk modu)
    weak_family_extra_min_prob: float = S.WEAK_FAMILY_EXTRA_MIN_PROB
    weak_family_require_direct: bool = S.WEAK_FAMILY_REQUIRE_DIRECT


DEFAULT = GuardConfig()


@dataclass
class GuardResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_odds: float = 1.0
    p_win: float = 1.0


def check_leg(leg: BankoLeg, cfg: GuardConfig = DEFAULT, at_selection: bool = True) -> tuple[list[str], list[str]]:
    err: list[str] = []
    warn: list[str] = []
    if not leg.offered:
        err.append(f"{leg.label}: seçim Nesine bülteninde yok (türetilmiş fiyat)")
    if leg.odds < cfg.min_odds:
        err.append(f"{leg.label}: oran {leg.odds:.2f} < {cfg.min_odds:.2f}")
    elif at_selection and leg.odds < cfg.select_min_odds:
        warn.append(f"{leg.label}: oran {leg.odds:.2f} tabana çok yakın, oynarken {cfg.min_odds:.2f} altına düşebilir")
    if leg.odds > cfg.max_leg_odds:
        err.append(f"{leg.label}: oran {leg.odds:.2f} > {cfg.max_leg_odds:.2f} (banko değil)")
    if leg.live and leg.p_market is None:
        err.append(f"{leg.label}: canlı bacakta piyasa olasılığı yok (model tek başına kullanılamaz)")
    p = effective_prob(leg, cfg.shrink)    # canlıda piyasa +5 tavanı; değilse denetim büzmesi
    min_p = cfg.min_prob
    fam = leg.family or selection_family(_sel_name(leg.label))
    if fam and fam in cfg.weak_families and not leg.live:
        if cfg.weak_family_require_direct and leg.direct is not True:
            err.append(f"{leg.label}: {fam} ailesi banko'da yalnız doğrudan keskin fiyatla (21 Kas: ana tercihte ~%50 tuttu)")
        min_p = cfg.min_prob + cfg.weak_family_extra_min_prob
    if p < min_p:
        shr = f" (büzülmüş; ham %{100 * leg.p:.1f})" if abs(p - leg.p) > 1e-9 else ""
        err.append(f"{leg.label}: P %{100 * p:.1f}{shr} < %{100 * min_p:.0f}")
    if cfg.require_sharp and not leg.sharp_ref and not leg.live:
        err.append(f"{leg.label}: keskin referans fiyatı yok")
    for f in leg.red_flags:
        err.append(f"{leg.label}: kırmızı bayrak — {f}")
    return err, warn


def check_coupon(legs: Sequence[BankoLeg], open_exposure: Mapping[str | int, int] | None = None,
                 cfg: GuardConfig = DEFAULT, at_selection: bool = True) -> GuardResult:
    """Banko modunda kupon denetimi. ``open_exposure``: maç → bu maçı içeren açık kupon sayısı."""
    res = GuardResult(ok=True)
    seen: set = set()
    for leg in legs:
        e, w = check_leg(leg, cfg, at_selection)
        res.errors += e
        res.warnings += w
        if leg.match_id in seen:
            res.errors.append(f"{leg.label}: aynı maçtan ikinci seçim (korelasyon)")
        seen.add(leg.match_id)
        n_open = (open_exposure or {}).get(leg.match_id, 0)
        if n_open + 1 > cfg.max_coupons_per_match:
            res.errors.append(f"{leg.label}: bu maç zaten {n_open} açık kuponda (en çok {cfg.max_coupons_per_match})")
    res.total_odds = math.prod(l.odds for l in legs) if legs else 1.0
    res.p_win = math.prod(effective_prob(l, cfg.shrink) for l in legs) if legs else 1.0
    if legs and len(legs) < cfg.min_legs:
        res.errors.append(f"{len(legs)} maç < en az {cfg.min_legs} maç ({cfg.name} modu: 1–2 maçlık kupon yok)")
    if len(legs) > cfg.max_legs:
        res.errors.append(f"{len(legs)} maç > en çok {cfg.max_legs} maç ({cfg.name} modu)")
    if legs and res.p_win < cfg.lottery_p_win:
        msg = f"P(kupon) %{100 * res.p_win:.1f} < %{100 * cfg.lottery_p_win:.0f}: piyango kuponu, banko değil"
        (res.errors if cfg.lottery_is_error else res.warnings).append(msg)
    res.ok = not res.errors
    return res


def max_banko_total(n_legs: int, cfg: GuardConfig = DEFAULT, leg_margin: float = 0.12) -> float:
    """P ≥ min_prob bacaklarla ulaşılabilecek kaba en yüksek toplam oran (Nesine bacak başı pay ≈ %8–13)."""
    leg = min(cfg.max_leg_odds, 1.0 / (cfg.min_prob * (1.0 + leg_margin)))
    return leg ** n_legs


def _sel_name(label: str) -> str:
    """Bacak etiketinden ("Ev - Dep Ev 1.5 Üst") seçim adını bul: bilinen aile kalıbıyla biten en kısa kuyruk."""
    toks = (label or "").split()
    for i in range(len(toks) - 1, -1, -1):
        tail = " ".join(toks[i:])
        if selection_family(tail):
            return tail
    return label or ""

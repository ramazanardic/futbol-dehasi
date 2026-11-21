"""Pazar güvenilirliği — 21 Kas hata analizinin arşivle DOĞRULANAN dersleri (scripts/hata_analizi_21kasim.py).

* ``tail_adjust``: banko bölgesinde (P .55–.90) mevcut üretim kalibrasyonundan sonra kalan, walk-forward testte
  (2021/22+) log-loss'u GA ile iyileştiren küçük logit kaymaları (5 seçim; ör. ÇŞ 12 −0.7 puan: beraberlik hafif
  düşük fiyatlanıyor, İY ÇŞ 1X −0.75, Dep İY 0.5 Alt −0.8, Ev İY 0.5 Üst +2.6). Diğer 65 seçim: arşivde sapma yok.
* ``is_archive_tested``: seçim arşivde sınanabiliyor mu. Sınanamayan türetilmiş pazarlar (İlk Gol, İY/2Y KG
  kombineleri, …) için ``settings.UNTESTED_MARKET_SHRINK`` ek büzme (kalibrasyonu hiç doğrulanmamış P'ye temkin).
* ``draw_risk``: beraberlik riski = marjsız piyasa P(0) + düşük toplam bölgesi düzeltmesi. Arşiv (2016/17+, 77,5k maç):
  P(2.5Ü) < .45 maçlarda gerçek beraberlik piyasadan +1.6 puan fazla (11/11 sezon aynı yön); favori oranı 1.10–1.80
  bandında piyasa beraberliği doğru fiyatlıyor (fark ≤ ±0.15 puan). Bu bir KALİBRASYON değil, risk puanıdır
  (2021+ testte log-loss iyileşmesi GA'yı geçmedi) — banko MS 1/MS 2 bacaklarını ve risk modu beraberlik seçimlerini süzer.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from quantfoot import settings as S

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "calibration" / "market_tail_calibration.json"
_CACHE: dict[str, Any] = {}


def load_tail_calibration(path: Path | str | None = None) -> dict[str, Any]:
    p = str(Path(path) if path else DEFAULT_PATH)
    if p not in _CACHE:
        try:
            _CACHE[p] = json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _CACHE[p] = {}
    return _CACHE[p]


def normalize_name(name: str | None) -> str:
    """'Ev İY 0,5 Üst' → 'Ev İY 0.5 Üst'; 'Çifte Şans: 1-2' → 'ÇŞ 12'; fazla boşluk temizlenir."""
    n = " ".join(str(name or "").replace(",", ".").split())
    m = re.match(r"^(1\. Yarı |İY )?Çifte Şans: ?([1X2])-([1X2])$", n, re.I)
    if m:
        return ("İY " if m.group(1) else "") + f"ÇŞ {m.group(2).upper()}{m.group(3).upper()}"
    return n


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sig(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def tail_adjust(name: str | None, p: float, cal: dict[str, Any] | None = None) -> float:
    """Arşivle doğrulanmış yüksek-P kuyruk düzeltmesi; listede yoksa ya da bölge dışındaysa P aynen döner."""
    if not S.TAIL_CALIBRATION_ON or not math.isfinite(p):
        return p
    cal = load_tail_calibration() if cal is None else cal
    t = (cal.get("tail") or {}).get(normalize_name(name))
    if not t or not (t.get("lo", 0.55) <= p < t.get("hi", 0.90)):
        return p
    return _sig(_logit(p) + float(t["delta"]))


def is_archive_tested(name: str | None, cal: dict[str, Any] | None = None) -> bool | None:
    """Seçim (ya da karşı tarafı) arşiv kalibrasyon çalışmasında sınandı mı. Ad yoksa None (bilinmiyor)."""
    n = normalize_name(name)
    if not n:
        return None
    cal = load_tail_calibration() if cal is None else cal
    rel = cal.get("reliability") or {}
    if not rel:
        return None
    if n in rel:
        return True
    for a, b in (("Alt", "Üst"), ("Üst", "Alt"), ("Yok", "Var"), ("Var", "Yok"), ("Çift", "Tek"), ("Tek", "Çift")):
        if n.endswith(a) and (n[: -len(a)] + b) in rel:
            return True
    if n.startswith("DEĞİL(") and n[6:-1] in rel:
        return True
    return False


# ---------------------------------------------------------------- beraberlik riski
_MS_SIDE = re.compile(r"^(MS|Maç Sonucu:?) ?([12])$", re.I)


def draw_risk(p_draw: float | None, p_over25: float | None = None, cal: dict[str, Any] | None = None) -> float | None:
    """Beraberlik riski: logit P(0) + a + c·1[P(2.5Ü) < eşik] (arşiv eğitim ≤2020). Girdi yoksa None."""
    if p_draw is None or not math.isfinite(p_draw):
        return None
    cal = load_tail_calibration() if cal is None else cal
    d = cal.get("draw_adjust") or {}
    z = _logit(p_draw) + float(d.get("a", 0.0))
    if p_over25 is not None and p_over25 < float(d.get("low_total_below", S.DRAW_ZONE_MAX_OVER25)):
        z += float(d.get("c_low_total", 0.0))
    return _sig(z)


def is_match_result_side(name: str | None) -> bool:
    return bool(_MS_SIDE.match(normalize_name(name)))


def ms_prob_after_draw_risk(p_side: float, p_draw: float | None, p_over25: float | None) -> float:
    """MS 1/MS 2 P'si: beraberlik riskindeki fazlalık (risk − piyasa) iki taraftan P'leriyle orantılı düşülür."""
    r = draw_risk(p_draw, p_over25)
    if r is None or p_draw is None or r <= p_draw or p_draw >= 1:
        return p_side
    return max(0.0, p_side - (r - p_draw) * p_side / (1.0 - p_draw))


def draw_risk_level(r: float | None) -> str:
    if r is None:
        return "bilinmiyor"
    if r >= S.BANKO_DRAW_RISK_MAX:
        return "yüksek"
    if r >= S.BANKO_DRAW_RISK_WARN:
        return "orta"
    return "düşük"


def draw_pick_ok(p_draw: float | None, p_over25: float | None, odds: float, min_ev: float | None = None) -> tuple[bool, str]:
    """Risk modu beraberlik (MS 0) seçimi süzgeci: yalnız arşivde beraberliğin fazla geldiği bölgede (düşük toplam,
    piyasa P(0) ≥ ``DRAW_PICK_MIN_P``) ve risk P'siyle EV ≥ ``DRAW_PICK_MIN_EV``. Arşivde bu bölgede ortalama büro
    oranıyla ROI −0.9 % (en iyi oranla +3.7 %) — Nesine payıyla genelde değer YOK, süzgeç çoğu MS 0'ı reddeder."""
    min_ev = S.DRAW_PICK_MIN_EV if min_ev is None else min_ev
    if p_draw is None or p_over25 is None:
        return False, "beraberlik P'si ya da 2.5 Üst P'si yok"
    if p_over25 >= S.DRAW_ZONE_MAX_OVER25:
        return False, f"düşük toplam bölgesi değil (P(2.5Ü) {p_over25:.2f} ≥ {S.DRAW_ZONE_MAX_OVER25:.2f})"
    if p_draw < S.DRAW_PICK_MIN_P:
        return False, f"piyasa beraberlik P'si {p_draw:.2f} < {S.DRAW_PICK_MIN_P:.2f}"
    r = draw_risk(p_draw, p_over25) or p_draw
    ev = r * odds - 1.0
    if ev < min_ev:
        return False, f"EV {100 * ev:+.1f} % < {100 * min_ev:.0f} % (oran {odds:.2f}, P {r:.3f})"
    return True, f"uygun: P {r:.3f}, EV {100 * ev:+.1f} %"


# ---------------------------------------------------------------- yüksek oranlı pazarlar (İY/MS, İY/2Y sonucu, skor…)
# Arşiv (2016/17+, 77,5k maç): üretim hattının İY/MS 9 çıktısı, İY/2Y sonucu, iki yarıda KG ve skor kuyrukları
# kalibre (fark ≤ ±0.8 puan; geri dönüş 1/2: model %6.3, gerçek %6.6; 2/1: %10.5 vs %10.6). Ek kalibrasyon yalnız
# Skor 3-1'de GA'yı geçti. Nesine ödemesi bu pazarlarda marjsız P'nin ≈ .71–.85'i → değer neredeyse hiç yok.
_HIGH_ODDS = re.compile(r"^(İY/MS [102]/[102]|İY [102]|2Y [102]|İki Yarıda KG Var|Skor \d-\d|İY Skor \d-\d)$")


def is_high_odds_market(name: str | None) -> bool:
    return bool(_HIGH_ODDS.match(normalize_name(name)))


def high_odds_pick_ok(name: str | None, p_model: float | None, odds: float, p_sharp: float | None = None,
                      direct: bool | None = None, min_ev: float | None = None) -> tuple[bool, str, float | None]:
    """Yüksek oranlı seçim süzgeci (``yuksek_oran`` modu). Keskin fiyat varsa model ile keskin P'nin göreli farkı
    ≤ ``HIGH_ODDS_MAX_MODEL_SHARP_GAP`` olmalı ve EV ikisinin KÜÇÜĞÜYLE hesaplanır; keskin fiyat yoksa seçim arşivde
    sınanmış olmalı ve model P'si ``HIGH_ODDS_NO_SHARP_HAIRCUT`` kadar kırpılır. EV ≥ max(aile tabanı, HIGH_ODDS_MIN_EV).
    Dönen: (uygun mu, gerekçe, kullanılan P)."""
    from quantfoot.markets.families import family_rule

    if not is_high_odds_market(name):
        return False, "yüksek oranlı pazar değil", None
    if odds > S.HIGH_ODDS_MAX_ODDS:
        return False, f"oran {odds:.2f} > {S.HIGH_ODDS_MAX_ODDS:.0f} (piyango)", None
    floor = max(S.HIGH_ODDS_MIN_EV, family_rule(normalize_name(name))[0]) if min_ev is None else min_ev
    if p_sharp is None and direct and p_model is not None:
        p_sharp, p_model = p_model, None          # doğrudan kote: P keskin piyasanın kendisi
    if p_sharp is not None:
        if p_model is not None:
            gap = abs(p_model - p_sharp) / max(p_sharp, 1e-6)
            if gap > S.HIGH_ODDS_MAX_MODEL_SHARP_GAP:
                return False, f"model ({p_model:.3f}) ile keskin ({p_sharp:.3f}) uyuşmuyor (%{100 * gap:.0f})", None
            p = min(p_model, p_sharp)
        else:
            p = p_sharp
    else:
        if p_model is None:
            return False, "P yok", None
        if is_archive_tested(name) is not True:
            return False, "keskin fiyat yok ve pazar arşivde sınanmamış", None
        p = p_model * (1.0 - S.HIGH_ODDS_NO_SHARP_HAIRCUT)
    ev = p * odds - 1.0
    if ev < floor:
        return False, f"EV {100 * ev:+.1f} % < {100 * floor:.0f} % (P {p:.3f}, oran {odds:.2f})", p
    return True, f"uygun: P {p:.3f}, EV {100 * ev:+.1f} %", p


def select_high_odds(cands: list[dict], top: int = 5) -> list[dict]:
    """Aday sözlükleri (name, odds, p | p_model, p_sharp, direct) → süzgeçten geçenler, EV'ye göre sıralı."""
    out = []
    for c in cands:
        ok, why, p = high_odds_pick_ok(c.get("name"), c.get("p_model", c.get("p")), float(c["odds"]),
                                       c.get("p_sharp"), c.get("direct"))
        if ok and p is not None:
            out.append({**c, "p_used": p, "ev_used": p * float(c["odds"]) - 1.0, "why": why})
    return sorted(out, key=lambda x: -x["ev_used"])[:top]

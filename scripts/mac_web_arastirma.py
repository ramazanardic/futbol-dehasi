"""Kupon öncesi maç araştırması: web-araştırma + yapılandırılmış araştırma notu (t190u).

1) Eski kullanım (değişmedi) — aday maçlara ``research["web"]`` yazar:
     python scripts/mac_web_arastirma.py --tarih 2026-11-22 [--girdi tahminler/<ai>/2026-11-22/nesine_global.json]
            [--en-fazla 20] [--cikti reports/research/web_arastirma_2026-11-22.json]

2) Araştırma notu üret (ücretsiz kaynaklar: ESPN, FPL, Wikipedia, Open Matchday, Open-Meteo; API-Football YOK, bot koruması aşılmaz):
     python scripts/mac_web_arastirma.py --tarih 2026-11-28 --not-uret [--girdi nesine_global.json | --bulten --mac 3318456 ...]
   Otomatik toplanamayan alanlar boş kalır (``bos_alanlar``). Çıktı: tahminler/<QUANTFOOT_AI>/arastirma/<gün>/<kod>_<ev>_<dep>.json

3) Ana yapay zekâ notu okur / doldurur (WebSearch ile bulduklarını yazar):
     python scripts/mac_web_arastirma.py --tarih 2026-11-28 --not-oku [--mac 3318456] [--bos]
     python scripts/mac_web_arastirma.py --tarih 2026-11-28 --not-yaz --mac 3318456 --json '{"takimlar":{"ev":{"kesin_eksik":[{"oyuncu":"X","rol":"GK","onem":3}]}},
            "bacak_kararlari":[{"secim":"MS 1","karar":"veto","gerekce":"kaleci cezalı, kaynak ..."}],"kaynaklar":[{"url":"https://...","baslik":"..."}]}'
     (--json-dosya yama.json de olur.) ``bacak_kararlari``: secim = Nesine seçim adı ("MS 1", "2.5 Üst", ...) ya da "*" (maçın tüm bacakları);
     karar = onay | uyari | veto (uyari/veto için gerekçe zorunlu). Not olasılığı yükseltemez; yalnız eler/işaretler.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from quantfoot.data import arastirma_notu as AN
from quantfoot.data import web_research as W


def _find(day: str) -> Path | None:
    c = sorted(ROOT.glob(f"tahminler/*/{day}/nesine_global.json"), key=lambda p: p.stat().st_mtime)
    return c[-1] if c else None


def _bulletin_matches(day: str, codes: set[str], league: str | None) -> list[dict]:
    """nesine_global yoksa: canlı bültenden istenen maçlar + ESPN araştırması + hava (fiyat/olasılık YOK)."""
    import nesine_global as NG  # noqa: WPS433
    from quantfoot.data.nesine import betting_day, fetch_bulletin, league_names, parse_bulletin
    from quantfoot.data.weather import fetch_matchday_weather

    payload = fetch_bulletin()
    leagues = league_names(payload)
    evs = [e for e in parse_bulletin(payload) if betting_day(e.kickoff) == day]
    evs = [e for e in evs if (not codes or str(e.code) in codes) and (not league or league.lower() in leagues.get(e.league_code, "").lower())]
    recs = [{"code": e.code, "home": e.home, "away": e.away, "league": leagues.get(e.league_code), "kickoff_iso": e.kickoff.isoformat(),
             "status": "fiyatlandı", "price_tier": None} for e in evs]
    events = [e for e in evs]
    if recs:
        NG.attach_research(recs, events, dt.date.fromisoformat(day), None)
        for code, w in fetch_matchday_weather(recs).items():
            for r in recs:
                if r["code"] == code and w:
                    r.setdefault("research", {"teams": {}, "flags": [], "motivation": {}})["weather"] = w
    return recs


def _collect_web(ms: list[dict], day: str, verbose: bool = True) -> dict:
    """``research["web"]`` yoksa topla (API-Football kapalı: ``af={}``)."""
    todo = [m for m in ms if not (m.get("research") or {}).get("web")]
    if not todo:
        return {"islenen": 0}
    http = W.Http()
    fpl = {}
    try:
        from quantfoot.data import free_absences as FA
        fpl = FA.fetch_fpl() if any(m.get("league") == "İngiltere Premier Lig" for m in todo) else {}
    except Exception:  # noqa: BLE001
        fpl = {}
    ctx = W.Ctx(day, http, fpl=fpl, af={})
    for m in todo:
        m.setdefault("research", {"teams": {}, "flags": [], "motivation": {}})
        w = W.research_match(m, ctx)
        W.normalize_into(m, w, shield=False)
        if verbose:
            print(f"  web-araştırma {m['home']} - {m['away']}: {w['sure_sn']} sn, bilinmeyen {len(w['bilinmiyor'])}")
    return {"islenen": len(todo), "kaynak_ozeti": W.summarize_log(http.log)}


def cmd_not_uret(a) -> None:
    f = Path(a.girdi) if a.girdi else _find(a.tarih)
    codes = {str(c) for c in a.mac or []}
    if f and f.exists() and not a.bulten:
        ms = json.loads(f.read_text(encoding="utf-8"))["matches"]
        pool = [m for m in ms if str(m["code"]) in codes] if codes else [m for m in ms if W.is_candidate(m)][: a.en_fazla]
        kaynak = str(f)
    else:
        if not (codes or a.lig):
            sys.exit("bülten kipinde --mac KOD ... ya da --lig gerekli (nesine_global.json bulunamadı)")
        pool = _bulletin_matches(a.tarih, codes, a.lig)[: a.en_fazla]
        kaynak = "canlı Nesine bülteni"
    if not pool:
        sys.exit("eşleşen maç yok")
    ozet = _collect_web(pool, a.tarih)
    root = Path(a.not_klasoru) if a.not_klasoru else None
    rows = []
    for m in pool:
        auto = AN.from_match(m, a.tarih)
        old = AN.find_note_path(a.tarih, m["code"], root)
        note = AN.refresh(auto, AN.load(old) if old else None)
        if old and old.name != AN.note_filename(m["code"], m["home"], m["away"]):
            old.unlink()
        p = AN.save(note, a.tarih, root)
        rows.append({"kod": m["code"], "mac": f"{m['home']} - {m['away']}", "dosya": str(p), "bos_alanlar": note["bos_alanlar"]})
    print(json.dumps({"kaynak": kaynak, "ozet": ozet, "notlar": rows}, ensure_ascii=False, indent=1, default=str))


def cmd_not_oku(a) -> None:
    root = Path(a.not_klasoru) if a.not_klasoru else None
    notes = AN.load_day(a.tarih, root)
    if a.mac:
        sel = {str(c): notes.get(str(c)) for c in a.mac}
        miss = [c for c, n in sel.items() if n is None]
        if miss:
            sys.exit(f"not yok: {', '.join(miss)} (önce --not-uret)")
        for c, n in sel.items():
            if a.bos:
                print(json.dumps({"kod": c, "mac": n["mac"], "bos_alanlar": AN.empty_fields(n)}, ensure_ascii=False))
            else:
                print(json.dumps({**n, "bos_alanlar": AN.empty_fields(n)}, ensure_ascii=False, indent=1))
        return
    for c, n in notes.items():
        m = n["mac"]
        kar = collections.Counter(d["karar"] for d in n.get("bacak_kararlari") or [])
        print(f"{c}\t{m['ev']} - {m['dep']}\t{m.get('lig')}\tkarar={dict(kar) or '-'}\tbos={len(AN.empty_fields(n))}")
    if not notes:
        print(f"{a.tarih} için not yok")


def cmd_not_yaz(a) -> None:
    if len(a.mac or []) != 1:
        sys.exit("--not-yaz için tek --mac KOD gerekli")
    code = str(a.mac[0])
    if a.json_dosya:
        patch = json.loads(Path(a.json_dosya).read_text(encoding="utf-8"))
    elif a.json:
        patch = json.loads(a.json)
    else:
        sys.exit("--json ya da --json-dosya gerekli")
    root = Path(a.not_klasoru) if a.not_klasoru else None
    old = AN.find_note_path(a.tarih, code, root)
    note = AN.load(old) if old else None
    if note is None:
        m = patch.get("mac") or {}
        if not (m.get("ev") and m.get("dep")):
            sys.exit("not yok: yamada mac.ev ve mac.dep verin ya da önce --not-uret çalıştırın")
        note = AN.empty_note(a.tarih, code, m["ev"], m["dep"], m.get("saat"), m.get("lig"))
    new = AN.merge_patch(note, patch, who=a.kim)
    errs = AN.validate(new)
    if errs:
        sys.exit("şema hatası: " + "; ".join(errs))
    p = AN.save(new, a.tarih, root)
    print(json.dumps({"kaydedildi": str(p), "bos_alanlar": new["bos_alanlar"],
                      "kararlar": [(d["secim"], d["karar"]) for d in new["bacak_kararlari"]]}, ensure_ascii=False))


def cmd_eski(a) -> None:
    f = Path(a.girdi) if a.girdi else _find(a.tarih)
    if not f or not f.exists():
        sys.exit(f"{a.tarih} için nesine_global.json bulunamadı")
    data = json.loads(f.read_text(encoding="utf-8"))
    ms = data["matches"]
    t0 = time.time()
    s = W.attach(ms, dt.date.fromisoformat(a.tarih), max_matches=a.en_fazla, verbose=True, shield=False)
    webs = [(m, m["research"]["web"]) for m in ms if (m.get("research") or {}).get("web")]
    unk = collections.Counter(u.split(".", 1)[-1] for _, w in webs for u in w["bilinmiyor"])
    rep = {"tarih": a.tarih, "girdi": str(f), "ozet": s, "bilinmeyen_alan_sayisi": dict(unk),
           "toplam_sn": round(time.time() - t0, 1),
           "maclar": [{"kod": m["code"], "mac": f"{m['home']} - {m['away']}", "lig": m["league"], "web": w} for m, w in webs]}
    out = Path(a.cikti) if a.cikti else ROOT / "reports" / "research" / f"web_arastirma_{a.tarih}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"ozet": s, "bilinmeyen": dict(unk)}, ensure_ascii=False, indent=1))
    print("->", out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tarih", required=True)
    ap.add_argument("--girdi")
    ap.add_argument("--en-fazla", type=int, default=20)
    ap.add_argument("--cikti")
    ap.add_argument("--not-uret", action="store_true", help="aday maçlar için araştırma notu üret/yenile")
    ap.add_argument("--not-oku", action="store_true", help="notları listele / --mac ile tek notu yazdır")
    ap.add_argument("--not-yaz", action="store_true", help="--mac KOD için --json yamasını nota işle")
    ap.add_argument("--bulten", action="store_true", help="nesine_global yerine canlı bültenden (--mac / --lig ile)")
    ap.add_argument("--mac", nargs="*", help="Nesine maç kodu/kodları")
    ap.add_argument("--lig", help="bülten kipinde lig adı süzgeci")
    ap.add_argument("--bos", action="store_true", help="--not-oku: yalnız boş alanlar")
    ap.add_argument("--json")
    ap.add_argument("--json-dosya")
    ap.add_argument("--kim", default="yapay_zeka")
    ap.add_argument("--not-klasoru", help="varsayılan: tahminler/grokbottahmin/arastirma")
    a = ap.parse_args()
    if a.not_uret:
        cmd_not_uret(a)
    elif a.not_oku:
        cmd_not_oku(a)
    elif a.not_yaz:
        cmd_not_yaz(a)
    else:
        cmd_eski(a)


if __name__ == "__main__":
    main()

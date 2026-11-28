"""Wikipedia sezon sayfalarından (yalnız /wiki/ HTML — robots.txt izinli; /w/ ve /api/ kullanılmaz) sonuç matrisi + gol krallığı.

Lig başına jsonl.gz yazar (ham HTML saklanmaz). Başlık kalıpları: '{yıl}–{yy} {ad}' ve '{yıl} {ad}' ikisi de denenir; 404'ler önbelleğe
alınır (bir daha istenmez). İçerik CC BY-SA 4.0 (atıf: Wikipedia katkıcıları). Nazik hız: ~3 istek/sn.
    python scripts/arsiv_wiki_tara.py --bas 1995 --bit 2025 --cikti /workspace/arsiv_ham/wiki
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.data import arsiv as A

UA = {"User-Agent": "QuantFoot/3.0 (kisisel futbol arastirmasi; dusuk hizli okuma; github.com/ramazanardic/futbol-dehasi)"}
LIGLER = {  # anahtar: [Wikipedia başlık adları]
    "ukrayna": ["Ukrainian Premier League"], "rusya": ["Russian Premier League", "Russian Top League"],
    "hirvatistan": ["Croatian First Football League", "Prva HNL"], "sirbistan": ["Serbian SuperLiga", "First League of Serbia and Montenegro"],
    "bulgaristan": ["Bulgarian First League", "A Group"], "cekya": ["Czech First League", "Gambrinus liga"],
    "slovakya": ["Slovak First Football League", "Slovak Super Liga"], "slovenya": ["Slovenian PrvaLiga"],
    "macaristan": ["Nemzeti Bajnokság I"], "yunanistan": ["Super League Greece", "Alpha Ethniki"], "turkiye": ["Süper Lig"],
    "israil": ["Israeli Premier League", "Ligat Ha'Al"], "kibris": ["Cypriot First Division"], "romanya": ["Liga I"],
    "polonya": ["Ekstraklasa"], "danimarka": ["Danish Superliga"], "isvicre": ["Swiss Super League", "Swiss Super League"],
    "avusturya": ["Austrian Football Bundesliga"], "belarus": ["Belarusian Premier League"], "kazakistan": ["Kazakhstan Premier League"],
    "azerbaycan": ["Azerbaijan Premier League"], "gurcistan": ["Umaglesi Liga", "Erovnuli Liga"], "ermenistan": ["Armenian Premier League"],
    "moldova": ["Moldovan Super Liga", "Moldovan National Division"], "litvanya": ["A Lyga"], "letonya": ["Latvian Higher League"],
    "estonya": ["Meistriliiga"], "izlanda": ["Úrvalsdeild", "Úrvalsdeild karla (football)"], "isvec": ["Allsvenskan"], "norvec": ["Eliteserien", "Tippeligaen"],
    "finlandiya": ["Veikkausliiga"], "irlanda": ["League of Ireland Premier Division"], "kuzey_irlanda": ["NIFL Premiership", "IFA Premiership"],
    "galler": ["Welsh Premier League", "Cymru Premier"], "arnavutluk": ["Albanian Superliga", "Kategoria Superiore"],
    "bosna": ["Premier League of Bosnia and Herzegovina"], "makedonya": ["Macedonian First Football League"], "karadag": ["Montenegrin First League"],
    "malta": ["Maltese Premier League"], "luksemburg": ["Luxembourg National Division", "BGL Ligue"], "japonya": ["J1 League"], "guney_kore": ["K League 1", "K League Classic"],
    "cin": ["Chinese Super League"], "avustralya": ["A-League", "A-League Men"], "tayland": ["Thai League 1", "Thai Premier League"],
    "suudi": ["Saudi Professional League"], "katar": ["Qatar Stars League"], "bae": ["UAE Pro League", "UAE Arabian Gulf League"], "iran": ["Persian Gulf Pro League"],
    "hindistan": ["Indian Super League"], "brezilya": ["Campeonato Brasileiro Série A"], "arjantin": ["Argentine Primera División"],
    "meksika": ["Liga MX"], "abd": ["Major League Soccer"], "sili": ["Chilean Primera División"], "kolombiya": ["Categoría Primera A"],
    "uruguay": ["Uruguayan Primera División"], "paraguay": ["Paraguayan Primera División"], "peru": ["Peruvian Primera División"],
    "ekvador": ["Ecuadorian Serie A"], "bolivya": ["Bolivian Primera División"], "venezuela": ["Venezuelan Primera División"],
    "kosta_rika": ["Costa Rican Primera División"], "misir": ["Egyptian Premier League"], "guney_afrika": ["South African Premier Division", "Premier Soccer League"],
    "fas": ["Botola"], "tunus": ["Tunisian Ligue Professionnelle 1"], "cezayir": ["Algerian Ligue Professionnelle 1"], "nijerya": ["Nigeria Premier Football League"],
    "gana": ["Ghana Premier League"],
}
_last = [0.0]
_lock = threading.Lock()


def get(s: requests.Session, title: str, gap: float = 0.3) -> str | None:
    url = "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")
    with _lock:
        wait = _last[0] + gap - time.time()
        _last[0] = max(time.time(), _last[0] + gap)
    if wait > 0:
        time.sleep(wait)
    for t in range(3):
        try:
            r = s.get(url, timeout=30)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return None
        except requests.RequestException:
            time.sleep(2 * (t + 1))
    return None


def one_league(key: str, names: list[str], y0: int, y1: int, out: Path, s: requests.Session) -> dict:
    f = out / f"{key}.jsonl.gz"
    if f.exists():
        return {"lig": key, "atlandi": True}
    rows, seasons, tried = [], 0, 0
    for y in range(y0, y1 + 1):
        got = False
        for nm in names:
            for title in (f"{y}–{str(y + 1)[2:]} {nm}", f"{y} {nm}", f"{y}–{str(y + 1)[2:]} {nm} season", f"{y} {nm} season"):
                tried += 1
                html = get(s, title)
                if not html:
                    continue
                r = A.parse_wiki_season(html)
                if r["maclar"]:
                    sez = f"{y}/{str(y + 1)[2:]}" if "–" in title else str(y)
                    for ev, dep, hg, ag in r["maclar"]:
                        rows.append({"_t": "mac", "tarih": "", "sezon": sez, "yarisma": f"wiki/{key}", "ev": ev, "dep": dep, "hg": hg, "ag": ag,
                                     "iy_ev": None, "iy_dep": None, "durum": "FT", "ham_skor": None, "kaynak": "wikipedia"})
                    for pl, tm, g in r["golculer"][:10]:
                        rows.append({"_t": "oyuncu", "oyuncu": pl, "takim": tm, "yarisma": f"wiki/{key}", "sezon": sez, "mac": None, "ilk11": None,
                                     "gol": g, "penalti_gol": None, "kendi_kalesine": None, "sari": None, "kirmizi": None, "kaynak": "wikipedia"})
                    seasons += 1
                    got = True
                    break
            if got:
                break
    with gzip.open(f, "wt", encoding="utf-8") as g:
        for r in rows:
            g.write(json.dumps(r, ensure_ascii=False) + "\n")
    return {"lig": key, "sezon": seasons, "satir": len(rows), "istek": tried}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bas", type=int, default=1995)
    ap.add_argument("--bit", type=int, default=2025)
    ap.add_argument("--cikti", type=Path, required=True)
    ap.add_argument("--is", dest="workers", type=int, default=3)
    a = ap.parse_args()
    a.cikti.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update(UA)
    with ThreadPoolExecutor(a.workers) as ex:
        for r in ex.map(lambda kv: one_league(kv[0], kv[1], a.bas, a.bit, a.cikti, s), LIGLER.items()):
            print(json.dumps(r, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

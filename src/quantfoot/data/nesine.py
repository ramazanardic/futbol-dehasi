"""Nesine pre-match bulletin: fetch, parse and translate markets into QuantFoot selection names.

The bulletin is Nesine's public JSON feed (the one its web site renders). Market type ids
(MTID) are mapped with Nesine's own market-definition table, extracted from the site's
`CCAll.min.js` (`nesine_markets.json`), so outcome labels are authoritative, not guessed.

Each translated selection is a `NesineSelection` whose `name` is a QuantFoot goal-market
name (see `markets.goal_markets`) or a timing name ("İlk Gol Ev"); `negate=True` means
the Nesine outcome is the complement of that event (e.g. "Ev İki Yarıda Gol: Atamaz").
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
import json
from pathlib import Path

import time

import requests

BULLETIN_URL = "https://cdnbulten.nesine.com/api/bulten/getprebultenfull"
RESULTS_URL = "https://ls.nesine.com/api/v2/LiveScore/GetUnliveMatches"  # public feed of Nesine's live-score page
FINISHED = {"MS", "UZT", "PEN"}  # full time, after extra time, after penalties (Ksl. = abandoned: not settled)
MARKETS_FILE = Path(__file__).with_name("nesine_markets.json")
TSI = dt.timezone(dt.timedelta(hours=3))

_RES = {"1": "1", "X": "0", "2": "2"}


@dataclass(frozen=True)
class NesineSelection:
    market_id: int
    market_title: str
    label: str          # Nesine's own outcome label
    name: str           # QuantFoot selection name
    odds: float
    negate: bool = False
    mbs: int | None = None  # minimum number of events Nesine requires in a coupon


@dataclass
class NesineEvent:
    code: int
    home: str
    away: str
    kickoff: dt.datetime
    league_code: int
    selections: list[NesineSelection] = field(default_factory=list)
    untranslated: list[str] = field(default_factory=list)

    def odds_of(self, name: str) -> float | None:
        for s in self.selections:
            if s.name == name and not s.negate:
                return s.odds
        return None


def load_market_definitions() -> dict[int, dict]:
    raw = json.loads(MARKETS_FILE.read_text(encoding="utf-8"))
    return {int(k): {"title": v["title"], "outcomes": {int(i): t for i, t in v["outcomes"].items()}} for k, v in raw.items()}


def fetch_bulletin(timeout: float = 60.0, attempts: int = 3, backoff_s: float = 5.0) -> dict:
    """The live Nesine bulletin; a transient connection error is retried (20 Nov: one dropped connection stopped a
    whole analysis run while the very next request succeeded)."""
    for i in range(attempts):
        try:
            resp = requests.get(BULLETIN_URL, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                                timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except (requests.ConnectionError, requests.Timeout):
            if i == attempts - 1:
                raise
            time.sleep(backoff_s * (i + 1))
    raise RuntimeError("unreachable")


def _line(sov: float | None) -> str:
    return f"{float(sov):.1f}"


def translate(mtid: int, outcome: int, sov: float | None, defs: dict[int, dict]) -> tuple[str, bool] | None:
    """Return (QuantFoot selection name, negate) for a Nesine market outcome, or None if unsupported."""
    d = defs.get(mtid)
    if not d or outcome not in d["outcomes"]:
        return None
    label = d["outcomes"][outcome]
    title = d["title"]
    # Variable goal line from SOV; only non-negative half-goal lines settle as plain Alt/Üst.
    L = _line(sov) if sov is not None and float(sov) >= 0 and abs(float(sov) % 1 - 0.5) < 1e-9 else None
    au = "Alt" if "Alt" in label else ("Üst" if "Üst" in label else None)

    if mtid == 1:
        return f"MS {_RES[label]}", False
    if mtid == 3:
        return {"1-X": "ÇŞ 1X", "1-2": "ÇŞ 12", "X-2": "ÇŞ X2"}[label], False
    if mtid == 7:
        return f"İY {_RES[label]}", False
    if mtid == 9:
        return f"2Y {_RES[label]}", False
    if mtid == 5:
        a, b = label.split("/")
        return f"İY/MS {_RES[a]}/{_RES[b]}", False
    if mtid == 38:
        return f"KG {label}", False
    if mtid == 452:
        return f"İY KG {label}", False
    if mtid == 599:
        return f"2Y KG {label}", False
    if mtid == 801:
        if label == "Evet/Evet":
            return "İki Yarıda KG Var", False
        a, b = label.split("/")
        yn = {"Evet": "Var", "Hayır": "Yok"}
        return f"İY KG {yn[a]} & 2Y KG {yn[b]}", False
    if mtid in (216, 217, 218, 219):  # total corners O/U (line from SOV)
        if L is None or au is None:
            return None
        return f"{'İY ' if mtid in (218, 219) else ''}Korner {L} {au}", False
    if mtid in (8, 62, 641):  # first-half double chance
        return {"1-X": "İY ÇŞ 1X", "1-2": "İY ÇŞ 12", "X-2": "İY ÇŞ X2"}[label], False
    if mtid in (455, 456, 644, 457, 458, 645):  # one team's first-half goals
        if L is None or au is None:
            return None
        return f"{'Ev' if mtid in (455, 456, 644) else 'Dep'} İY {L} {au}", False
    if mtid in (584, 585):
        return f"{'Ev' if mtid == 584 else 'Dep'} En Az Bir Yarıyı Kazanır", label == "Hayır"
    if mtid == 592:
        return "Dep Her İki Yarıyı Kazanır", label == "Hayır"
    if mtid in (586, 587):
        return f"{'Ev' if mtid == 586 else 'Dep'} En Çok Gol " + {"1.": "1Y", "2.": "2Y", "Eşit": "Eşit"}[label], False
    if mtid in (588, 594):  # winning margin: 'Ev. 3+', 'Dep. 1', '0'
        if label == "0":
            return "Fark 0", False
        side, n = label.split(". ")
        return f"Fark {'Ev' if side == 'Ev' else 'Dep'} {n}", False
    if mtid == 571:  # half-time / full-time correct score '1:0 / 2:1'
        if "+" in label:
            return None
        ht, ft = (x.strip().replace(":", "-") for x in label.split("/"))
        return f"İY Skor {ht} & Skor {ft}", False
    if mtid == 49:
        return label, False
    if mtid == 450:
        return f"İY {label}", False
    if mtid == 43:
        return label.replace(" Gol", "") + " Gol", False
    if mtid == 48:
        return {"1.Y": "En Çok Gol 1Y", "Eşit": "En Çok Gol Eşit", "2.Y": "En Çok Gol 2Y"}[label], False
    if mtid == 268 and sov is not None:
        return f"Hnd({int(round(float(sov))):+d}) {_RES[label]}", False
    if mtid == 291:
        return {"1": "İlk Gol Ev", "2": "İlk Gol Dep", "Olmaz": "İlk Gol Yok"}[label], False
    if mtid == 414:
        r, k = label.split(" & ")
        return f"MS {_RES[r]} & KG {k}", False
    if mtid == 416:
        r, k = label.split(" & ")
        return f"İY {_RES[r]} & İY KG {k}", False
    if mtid == 446:
        a, k = label.split("&")
        return f"2.5 {a.strip()} & KG {k.strip()}", False
    if mtid in (272, 342, 343, 459):
        line = {342: "1.5", 343: "2.5"}.get(mtid, L)
        if line is None:
            return None
        r, side = label.split(" & ")
        prefix = "İY " if mtid == 459 else "MS "
        half = "İY " if mtid == 459 else ""
        return f"{prefix}{_RES[r]} & {half}{line} {side}", False
    if mtid in (295, 296):
        team = "Ev" if mtid == 295 else "Dep"
        return f"{team} İki Yarıda Gol", label == "Atamaz"
    if mtid == 591:
        return "Ev Her İki Yarıyı Kazanır", label == "Hayır"
    if mtid in (528, 529) and L:
        side = "Alt" if mtid == 528 else "Üst"
        return f"İY {L} {side} & 2Y {L} {side}", label == "Hayır"
    # Alt/Üst families: decide the scope from the market title.
    if au and "Alt/Üst" in title and " ve " not in title and "&" not in label:
        # Fixed-line markets carry the line in the title/label ("2,5 Gol Alt/Üst"); only
        # variable-line markets ("{{handicap}} Gol Alt/Üst") take it from SOV.
        line = L if "{{handicap}}" in title else label.split()[0].replace(",", ".")
        try:
            value = float(line)
        except (TypeError, ValueError):
            return None
        if value < 0 or abs(value % 1 - 0.5) > 1e-9:
            return None  # only half-goal lines settle as plain Alt/Üst
        line = f"{value:.1f}"
        if "Korner" in title or "Kart" in title:
            return None
        scope = ""
        if title.startswith("1. Yarı") or "1.Y" in title:
            scope = "İY "
        elif title.startswith("2. Yarı") or "2.Y" in title:
            scope = "2Y "
        team = "Ev " if title.startswith("Ev Sahibi") else ("Dep " if title.startswith("Deplasman") else "")
        if team and scope:
            return None  # team-half totals are not in the goal parser
        return f"{team}{scope}{line} {au}", False
    return None


def parse_bulletin(payload: dict, defs: dict[int, dict] | None = None) -> list[NesineEvent]:
    """Football events (TYPE 1) with translated selections."""
    defs = defs or load_market_definitions()
    events = []
    for e in payload["sg"]["EA"]:
        if e.get("TYPE") != 1:
            continue
        ko = dt.datetime.fromtimestamp(e["ESD"] / 1000, tz=TSI)
        ev = NesineEvent(code=int(e["C"]), home=e.get("HN", ""), away=e.get("AN", ""), kickoff=ko, league_code=int(e.get("LC", 0)))
        for m in e.get("MA", []):
            mtid = int(m["MTID"])
            if m.get("MS", 1) != 1:
                # MS = market status: 0 = closed / suspended on Nesine (not offered on the site) although the feed still
                # carries its last odds (20 Nov: Sumgayit - Sabah 2,5 Alt/Üst had MS 0 and still entered a coupon)
                continue
            for oc in m.get("OCA", []):
                odds = float(oc.get("O", 0))
                if odds <= 1.0:
                    continue
                tr = translate(mtid, int(oc["N"]), m.get("SOV"), defs)
                title = defs.get(mtid, {}).get("title", str(mtid))
                label = defs.get(mtid, {}).get("outcomes", {}).get(int(oc["N"]), str(oc["N"]))
                if tr is None:
                    ev.untranslated.append(f"{title}: {label}")
                    continue
                ev.selections.append(NesineSelection(mtid, title, label, tr[0], odds, tr[1], m.get("MBS")))
        events.append(ev)
    return events


def league_names(payload: dict) -> dict[int, str]:
    """Nesine league code -> name, when the bulletin carries a league list."""
    out = {}
    for lg in payload["sg"].get("LA", []) or []:
        code = lg.get("LID") or lg.get("LC") or lg.get("ID")
        name = lg.get("LN") or lg.get("N") or lg.get("NAME")
        if code is not None and name:
            out[int(code)] = str(name)
    return out


def market_overrounds(payload: dict, codes: set[int] | None = None, defs: dict[int, dict] | None = None) -> dict[str, dict]:
    """Average bookmaker margin (sum of 1/odds − 1) per market title, over complete outcome sets.

    `codes` restricts to the given event codes (e.g. today's matches).
    """
    defs = defs or load_market_definitions()
    acc: dict[str, list[float]] = {}
    for e in payload["sg"]["EA"]:
        if e.get("TYPE") != 1 or (codes is not None and int(e["C"]) not in codes):
            continue
        for m in e.get("MA", []):
            d = defs.get(int(m["MTID"]))
            oca = [o for o in m.get("OCA", []) if float(o.get("O", 0)) > 1.0]
            if not d or len(oca) != len(d["outcomes"]) or len(oca) < 2:
                continue
            acc.setdefault(d["title"].replace("{{handicap}}", "X"), []).append(sum(1.0 / float(o["O"]) for o in oca) - 1.0)
    return {k: {"n": len(v), "margin": sum(v) / len(v)} for k, v in acc.items()}


def parse_results(payload: dict) -> dict[int, dict]:
    """Nesine event code -> {'completed', 'status', 'ht', 'ft90'} from the live-score feed.
    Score types: 2 = half time, 3 = 90 minutes (what Nesine settles on), 1 = final incl. extra time."""
    out: dict[int, dict] = {}
    for m in payload.get("d") or []:
        try:
            code = int(m["C"])
        except (KeyError, TypeError, ValueError):
            continue
        sc = {e.get("T"): (int(e.get("H", 0)), int(e.get("A", 0))) for e in m.get("ES") or []}
        rec = {"completed": False, "status": m.get("ST")}
        if m.get("ST") in FINISHED and 2 in sc and (3 in sc or 1 in sc):
            rec.update(completed=True, ht=list(sc[2]), ft90=list(sc.get(3, sc.get(1))))
        out[code] = rec
    return out


def fetch_results(dates: list[str], timeout: float = 30.0) -> dict[int, dict]:
    """Finished football matches of the given calendar dates (YYYY-MM-DD), keyed by Nesine event code."""
    out: dict[int, dict] = {}
    for d in dates:
        try:
            r = requests.get(RESULTS_URL, params={"sportType": 1, "date": d}, timeout=timeout,
                             headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            out.update(parse_results(r.json()))
        except (requests.RequestException, ValueError):
            continue
    return out

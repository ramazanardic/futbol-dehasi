"""GLOBAL FOOTBALL INTELLIGENCE (GFI) dışa aktarımından küçük türetilmiş tablolar (28 Kas, Ramazan onayı).

Girdi: GFI gzip CSV dışa aktarımı (varsayılan /workspace/gfi_import; repoya KONMAZ):
  market_history.csv.gz  world_results (lisansı belirsiz) + openfootball (CC0) + openligadb maç sonuçları
  global_gap.csv.gz      openfootball football.json / txt depoları (CC0)
  half_case.csv.gz       İY skoru durum tablosu (yalnız sayım için)
  wi_matches.csv.gz      world_incidents maçları (lisansı belirsiz)
  wi_goals.csv.gz        world_incidents gol / penaltı / kırmızı kart olayları (lisansı belirsiz)

Çıktı (data/gfi/, her biri birkaç yüz KB; MAÇ SATIRI YOK, yalnız agregat):
  lig_taban_gfi.csv      lig taban oranları (n, tarih aralığı, gol ort., 1.5/2.5/3.5 alt, KG, 1X2, İY 0.5/1.5, 2Y KG yok)
  takim_form_gfi.csv     arşivde (data/matches.csv) olmayan liglerin takım son-10 form özeti (ev/dep ayrı)
  lig_yari_dakika_gfi.csv  wi_goals'tan lig başına İY/2Y gol payı ve 15 dk'lık dakika dağılımı (+ _genel satırı)

Lisans: world_results ve world_incidents lisansı belirsiz olduğundan bunlardan yalnız agregat (oran / ortalama)
türetilir. openfootball CC0, openligadb (ODbL) — yine yalnız agregat yazılır.

    python scripts/gfi_turet.py [--dir /workspace/gfi_import] [--asof 2026-11-18]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.data.oddsmath import _norm_team

OUT = ROOT / "data" / "gfi"
DEFAULT_DIR = Path("/workspace/gfi_import")
FT_SINCE = "2023-07-01"  # FT taban oranı penceresi (son ~3 sezon)
MIN_N = 60
NOTE = ("# Kaynak: GLOBAL FOOTBALL INTELLIGENCE dışa aktarımı (28 Kas 2026). openfootball/football.json CC0; "
        "world_results ve world_incidents lisansı belirsiz -> yalnız agregat, maç satırı yok. scripts/gfi_turet.py\n")

# openfootball txt depoları -> football.json kodu
_TXT = {"1-bundesliga": "de.1", "2-bundesliga2": "de.2", "3-liga": "de.3", "3-league1": "en.3", "1-liga": "es.1",
        "1-seriea": "it.1", "copal": "copa.l", "3-liga3": "de.3"}
OPENLIGA = {"bl1": "de.1", "bl2": "de.2", "bl3": "de.3"}
WI_CODE = {"belgien_jupiler-league": "be.1", "danemark_superliga": "wr:denmark", "deutschland_bundesliga": "de.1",
           "england_premier-league": "en.1", "frankreich_ligue-1": "fr.1", "italien_serie-a": "it.1",
           "niederlande_eredivisie": "nl.1", "osterreich_bundesliga": "at.1", "polen_ekstraklasa": "wr:poland",
           "portugal_liga-portugal": "pt.1", "schweiz_super-league": "ch.1", "spanien_la-liga": "es.1"}
# arşiv (data/matches.csv Division) -> GFI yarışma anahtarı; "yeni lig" sayımı ve takım formu bunları atlar
ARCHIVE_COMP = {"E0": "en.1", "E1": "en.2", "E2": "en.3", "E3": "en.4", "EC": "en.5", "SP1": "es.1", "SP2": "es.2",
                "I1": "it.1", "I2": "it.2", "F1": "fr.1", "F2": "fr.2", "D1": "de.1", "D2": "de.2", "T1": "tr.1",
                "N1": "nl.1", "P1": "pt.1", "B1": "be.1", "SC0": "sco.1", "SC1": "sco.2", "SC2": "sco.3", "SC3": "sco.4",
                "G1": "gr.1", "ARG": "ar.1", "USA": "mls", "BRA": "br.1", "MEX": "mx.1", "JAP": "jp.1", "ROM": "wr:romania",
                "POL": "wr:poland", "SWE": "wr:sweden", "NOR": "wr:norway", "RUS": "ru.1", "CHN": "cn.1",
                "DEN": "wr:denmark", "SUI": "ch.1", "IRL": "wr:ireland-republic", "FIN": "wr:finland", "AUT": "at.1"}
# world_results ülke (üst lig) = openfootball kodu olan aynı lig -> tek anahtar
WR_SAME = {"england": "en.1", "spain": "es.1", "italy": "it.1", "germany": "de.1", "france": "fr.1", "turkey": "tr.1",
           "netherlands": "nl.1", "portugal": "pt.1", "belgium": "be.1", "scotland": "sco.1", "greece": "gr.1",
           "argentina": "ar.1", "united-states": "mls", "brazil": "br.1", "mexico": "mx.1", "japan": "jp.1",
           "russia": "ru.1", "china-pr": "cn.1", "switzerland": "ch.1", "austria": "at.1", "czech-republic": "cz.1",
           "hungary": "hu.1", "egypt": "eg.1", "morocco": "ma.1", "algeria": "dz.1", "colombia": "co.1",
           "australia": "au.1", "UEFA CL": "uefa.cl", "Copa Lib": "copa.l"}


def _code_from_path(p: str) -> str:
    leaf = p.split("/")[-1].removesuffix(".json").removesuffix(".txt")
    leaf = re.sub(r"^\d{4}(-\d{2})?_", "", leaf)  # openliga/2025-26_de.1, 2026_copal
    if leaf in _TXT:
        return _TXT[leaf]
    if leaf == "cup":  # deutschland/<sezon>/cup.txt
        return "de.cup"
    m = re.fullmatch(r"([a-z]+)(\d|cup)", leaf)  # europe/turkey/2023-24_tr1.txt, trcup
    if m:
        return f"{m.group(1)}.{m.group(2)}"
    return leaf.removesuffix("-full")


def _halves_from_goals(wm: pd.DataFrame, wg: pd.DataFrame) -> pd.DataFrame:
    """wi maçlarına İY skoru: gol dakikası (45+x dahil) <= 45 ise 1. yarı. Gol sayısı FT ile tutmayan maçlar atılır."""
    g = wg[wg.kind.isin(["Goal", "Own goal"])].copy()
    g["base"] = g.minute.astype(str).str.extract(r"^(\d+)")[0].astype(float)
    g["iy"] = g["base"] <= 45
    ft = g.groupby(["match_id", "team"]).size().unstack(fill_value=0)
    iy = g[g.iy].groupby(["match_id", "team"]).size().unstack(fill_value=0)
    x = wm.set_index("id")
    x["n_h"], x["n_a"] = ft.get("home"), ft.get("away")
    x[["n_h", "n_a"]] = x[["n_h", "n_a"]].fillna(0)
    x["ht_h"], x["ht_a"] = iy.get("home"), iy.get("away")
    x[["ht_h", "ht_a"]] = x[["ht_h", "ht_a"]].fillna(0)
    et = g[g.base > 90].match_id.unique()  # uzatma oynanmış
    ok = (x.hg == x.n_h) & (x.ag == x.n_a) & ~x.index.isin(et)
    x.loc[~ok, ["ht_h", "ht_a"]] = np.nan
    return x.reset_index()


def load(d: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Tüm kaynakları tek şemaya getirir ve kaynaklar arası tekrarları atar. Döner: maçlar, wi gol olayları, sayımlar."""
    mh = pd.read_csv(d / "market_history.csv.gz")
    gg = pd.read_csv(d / "global_gap.csv.gz")
    wm = pd.read_csv(d / "wi_matches.csv.gz")
    wg = pd.read_csv(d / "wi_goals.csv.gz")
    stats = {"market_history": len(mh), "global_gap": len(gg), "wi_matches": len(wm), "wi_goals": len(wg)}
    parts = []
    of = mh[mh.source == "openfootball"].copy()
    of["comp"], of["lic"] = of.competition.map(_code_from_path), "CC0"
    ol = mh[mh.source == "openligadb"].copy()
    ol["comp"], ol["lic"] = ol.competition.str.split("/").str[0].map(OPENLIGA).fillna("de.1"), "ODbL"
    wr = mh[mh.source == "world_results"].copy()
    wr["comp"] = wr.competition.map(lambda c: WR_SAME.get(c, f"wr:{c}"))
    wr["lic"] = "belirsiz"
    for t in (wr,):
        for col in ("home", "away"):
            t[col] = t[col].str.replace(r"\s*\([^)]*\)\s*$", "", regex=True)
    for t in (of, ol, wr):
        parts.append(t.rename(columns={"ft_home": "fh", "ft_away": "fa", "ht_home": "hh", "ht_away": "ha"})
                     [["source", "comp", "lic", "day", "home", "away", "fh", "fa", "hh", "ha"]])
    g2 = gg.copy()
    g2["comp"], g2["lic"], g2["source"] = g2.path.map(_code_from_path), "CC0", "openfootball_gap"
    parts.append(g2.rename(columns={"ft_h": "fh", "ft_a": "fa", "ht_h": "hh", "ht_a": "ha"})
                 [["source", "comp", "lic", "day", "home", "away", "fh", "fa", "hh", "ha"]])
    wx = _halves_from_goals(wm, wg)
    wx["comp"] = wx.league.str.replace(r"-\d{4}-\d{4}$", "", regex=True).map(WI_CODE)
    wx["source"], wx["lic"] = "world_incidents", "belirsiz"
    parts.append(wx.rename(columns={"hg": "fh", "ag": "fa", "ht_h": "hh", "ht_a": "ha"})
                 [["source", "comp", "lic", "day", "home", "away", "fh", "fa", "hh", "ha"]])
    df = pd.concat(parts, ignore_index=True).dropna(subset=["fh", "fa", "comp"])
    df["fh"], df["fa"] = df.fh.astype(int), df.fa.astype(int)
    df["nh"], df["na"] = df.home.map(_norm_team), df.away.map(_norm_team)
    stats["birlesik_ham"] = len(df)
    # tekrar: aynı gün + aynı skor + aynı (normalize) takımlar. HT'si olan / CC0 kaynak önce tutulur.
    rank = {"openfootball": 0, "openfootball_gap": 1, "openligadb": 2, "world_incidents": 3, "world_results": 4}
    df["_r"] = df.source.map(rank) + df.hh.isna() * 10
    df = df.sort_values("_r")
    key = df.day.astype(str) + "|" + df.nh.str[:6] + "|" + df.na.str[:6] + "|" + df.fh.astype(str) + "-" + df.fa.astype(str)
    df["key"] = key
    agg = df.groupby("key").agg(hh=("hh", "first"), ha=("ha", "first"))  # İY'yi tekrar kaydından tamamla
    df = df.drop_duplicates("key").drop(columns=["hh", "ha"]).merge(agg, left_on="key", right_index=True)
    stats["tekil_mac"] = len(df)
    stats["tekil_iy_skorlu"] = int(df.hh.notna().sum())
    return df.drop(columns=["_r"]).reset_index(drop=True), wg, stats


def archive_overlap(df: pd.DataFrame, matches_csv: Path) -> dict:
    """GFI maçlarından kaçı zaten data/matches.csv'de (aynı gün±1, aynı skor, takım adı alias eşleşmesi)."""
    m = pd.read_csv(matches_csv, usecols=["Division", "MatchDate", "HomeTeam", "AwayTeam", "FTHome", "FTAway", "HTHome"],
                    low_memory=False).dropna(subset=["FTHome", "FTAway"])
    m = m[m.MatchDate >= "2019-07-01"]
    keys = set()
    for shift in (-1, 0, 1):
        d = (pd.to_datetime(m.MatchDate) + pd.Timedelta(days=shift)).dt.strftime("%Y-%m-%d")
        keys |= set(d + "|" + m.HomeTeam.map(_norm_team).str[:6] + "|" + m.FTHome.astype(int).astype(str) + "-" + m.FTAway.astype(int).astype(str))
    k = df.day.astype(str) + "|" + df.nh.str[:6] + "|" + df.fh.astype(str) + "-" + df.fa.astype(str)
    inarch = k.isin(keys)
    arch_comps = set(ARCHIVE_COMP.values())
    df = df.assign(arsivde=inarch | df.comp.isin(arch_comps) & False)
    new = df[~inarch]
    return {"arsivde_var": int(inarch.sum()), "arsivde_yok": int((~inarch).sum()),
            "arsivde_yok_iy_skorlu": int(new.hh.notna().sum()),
            "arsiv_disi_lig": sorted(set(df.comp) - arch_comps)}


def league_table(df: pd.DataFrame, asof: str | None = None) -> pd.DataFrame:
    if asof:
        df = df[df.day < asof]
    rows = []
    for comp, g in df.groupby("comp"):
        ft = g[g.day >= FT_SINCE]
        if len(ft) < MIN_N:
            ft = g.sort_values("day").tail(400)
        if len(ft) < MIN_N:
            continue
        tot = ft.fh + ft.fa
        ht = g.dropna(subset=["hh"])
        r = {"lig": comp, "kaynak": "+".join(sorted(set(ft.source))), "lisans": "+".join(sorted(set(ft.lic))),
             "n": len(ft), "ilk": ft.day.min(), "son": ft.day.max(), "gol": round(tot.mean(), 3),
             "ev_gol": round(ft.fh.mean(), 3), "dep_gol": round(ft.fa.mean(), 3),
             "alt15": round((tot <= 1).mean(), 3), "alt25": round((tot <= 2).mean(), 3), "alt35": round((tot <= 3).mean(), 3),
             "kg": round(((ft.fh > 0) & (ft.fa > 0)).mean(), 3), "ev": round((ft.fh > ft.fa).mean(), 3),
             "ber": round((ft.fh == ft.fa).mean(), 3), "dep": round((ft.fh < ft.fa).mean(), 3), "n_iy": len(ht)}
        if len(ht) >= MIN_N:
            iy = ht.hh + ht.ha
            sh, sa = ht.fh - ht.hh, ht.fa - ht.ha
            all_g = (ht.fh + ht.fa).sum()
            r.update({"iy_ilk": ht.day.min(), "iy_son": ht.day.max(), "iy05_ust": round((iy >= 1).mean(), 3),
                      "iy15_alt": round((iy <= 1).mean(), 3), "iy_gol_payi": round(iy.sum() / all_g, 3) if all_g else None,
                      "y2_kg_yok": round(1 - ((sh > 0) & (sa > 0)).mean(), 3)})
        rows.append(r)
    return pd.DataFrame(rows)


def team_form(df: pd.DataFrame, asof: str | None = None, last: int = 10) -> pd.DataFrame:
    """Arşiv dışı liglerde takım son-10: atılan/yenilen ortalama, ev ve deplasman ayrı."""
    if asof:
        df = df[df.day < asof]
    df = df[~df.comp.isin(set(ARCHIVE_COMP.values()))]
    long = pd.concat([
        pd.DataFrame({"lig": df.comp, "takim": df.home, "tk": df.nh, "day": df.day, "gf": df.fh, "ga": df.fa, "yer": "ev"}),
        pd.DataFrame({"lig": df.comp, "takim": df.away, "tk": df.na, "day": df.day, "gf": df.fa, "ga": df.fh, "yer": "dep"}),
    ]).sort_values("day")
    out = []
    for (lig, tk), g in long.groupby(["lig", "tk"]):
        t = g.tail(last)
        h, a = g[g.yer == "ev"].tail(last), g[g.yer == "dep"].tail(last)
        out.append({"lig": lig, "takim": g.takim.iloc[-1], "anahtar": tk, "son_mac": t.day.iloc[-1], "n": len(t),
                    "at": round(t.gf.mean(), 2), "yer_": round(t.ga.mean(), 2),
                    "ev_n": len(h), "ev_at": round(h.gf.mean(), 2) if len(h) else None, "ev_yer": round(h.ga.mean(), 2) if len(h) else None,
                    "dep_n": len(a), "dep_at": round(a.gf.mean(), 2) if len(a) else None, "dep_yer": round(a.ga.mean(), 2) if len(a) else None})
    return pd.DataFrame(out).rename(columns={"yer_": "yedi"})


def minute_table(wm: pd.DataFrame, wg: pd.DataFrame, asof: str | None = None) -> pd.DataFrame:
    g = wg[wg.kind.isin(["Goal", "Own goal"])].copy()
    g["base"] = g.minute.astype(str).str.extract(r"^(\d+)")[0].astype(float)
    g = g.merge(wm[["id", "league", "day"]], left_on="match_id", right_on="id")
    if asof:
        g = g[g.day < asof]
    g = g[g.base <= 90]
    g["lig"] = g.league.str.replace(r"-\d{4}-\d{4}$", "", regex=True).map(WI_CODE)
    bins = [0, 15, 30, 45, 60, 75, 90]
    g["bin"] = pd.cut(g.base, bins=bins, labels=["dk00_15", "dk16_30", "dk31_45p", "dk46_60", "dk61_75", "dk76_90p"],
                      include_lowest=True)
    rows = []
    for lig, x in list(g.groupby("lig")) + [("_genel", g)]:
        dist = x.bin.value_counts(normalize=True)
        rows.append({"lig": lig, "n_mac": x.match_id.nunique(), "n_gol": len(x), "ilk": x.day.min(), "son": x.day.max(),
                     "iy_payi": round((x.base <= 45).mean(), 4), **{k: round(float(dist.get(k, 0.0)), 4) for k in
                                                                   ["dk00_15", "dk16_30", "dk31_45p", "dk46_60", "dk61_75", "dk76_90p"]}})
    return pd.DataFrame(rows)


def _write(df: pd.DataFrame, path: Path, extra: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(NOTE)
        if extra:
            fh.write(f"# {extra}\n")
        df.to_csv(fh, index=False, lineterminator="\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--asof", help="yalnız bu tarihten ÖNCEKİ maçlar (zaman sızıntısız ölçüm için)")
    args = ap.parse_args()
    df, wg, stats = load(args.dir)
    wm = pd.read_csv(args.dir / "wi_matches.csv.gz")
    lt = league_table(df, args.asof)
    tf = team_form(df, args.asof)
    mt = minute_table(wm, wg, args.asof)
    _write(lt, OUT / "lig_taban_gfi.csv", f"FT penceresi {FT_SINCE}.., lig başına n>={MIN_N}; wr:<ülke> = world_results o ülkenin üst ligi")
    _write(tf, OUT / "takim_form_gfi.csv", "arşiv (data/matches.csv) dışı ligler; son 10 maç / son 10 ev / son 10 deplasman ortalamaları")
    _write(mt, OUT / "lig_yari_dakika_gfi.csv", "world_incidents gol dakikaları (45+x 1. yarı); 90 sonrası (uzatma) hariç")
    print(stats)
    print(archive_overlap(df, ROOT / "data" / "matches.csv"))
    print(len(lt), len(tf), len(mt))


if __name__ == "__main__":
    main()

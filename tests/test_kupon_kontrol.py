"""Odds double-read, cross-coupon shared-match limit, pre-kick-off leg check and closing-price (CLV) record."""

import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


kupon = _load("nesine_kupon")
kontrol = _load("kupon_kontrol")
TSI = dt.timezone(dt.timedelta(hours=3))


def test_double_read_keeps_lowest_odds_and_reports_flicker(monkeypatch):
    reads = iter([{"odds": 1.71}, {"odds": 1.65}])
    monkeypatch.setattr(kupon, "fetch_bulletin", lambda: next(reads))
    monkeypatch.setattr(kupon, "selection_key", lambda s: s.key)

    def parse(payload):
        sels = [SimpleNamespace(key="13|3.5 Alt|0", odds=payload["odds"]), SimpleNamespace(key="1|MS 1|0", odds=1.30)]
        return [SimpleNamespace(code=7, selections=sels)]

    monkeypatch.setattr(kupon, "parse_bulletin", parse)
    odds, flicker = kupon.read_bulletin_odds(reads=2, gap_s=0)
    assert odds[7]["13|3.5 Alt|0"] == 1.65
    assert flicker == {(7, "13|3.5 Alt|0"): (1.65, 1.71)}
    assert (7, "1|MS 1|0") not in flicker


def test_prior_codes_use_latest_main_coupon_of_other_targets(tmp_path, monkeypatch):
    monkeypatch.setattr(kupon, "AI_AREA", tmp_path)
    day = tmp_path / "2026-11-20"
    day.mkdir()

    def write(name, coupons):
        (day / name).write_text(json.dumps({"coupons": [{"legs": [{"code": c} for c in cs]} for cs in coupons]}))

    write("kupon_5x_0800.json", [[1, 2]])
    write("kupon_5x_0851.json", [[3, 4], [5]])   # latest 5x: only its main coupon counts
    write("kupon_10x_0858.json", [[9]])          # same target as the one being built: ignored
    assert kupon.prior_coupon_codes("2026-11-20", 10) == {3, 4}


def _day(tmp_path, kick_iso, p_now, odds_now=1.50, flags=None):
    day = tmp_path / "2026-11-20"
    day.mkdir(exist_ok=True)
    leg = {"code": 1, "key": "13|3.5 Alt|0", "kickoff": kick_iso[:16].replace("T", " "), "match": "A - B",
           "market": "3,5 Gol Alt/Üst", "selection": "3,5 Alt", "odds": 1.50, "p": 0.62}
    (day / "kupon_5x_0851.json").write_text(json.dumps({"coupons": [{"legs": [leg]}]}), encoding="utf-8")
    match = {"code": 1, "kickoff_iso": kick_iso, "status": "fiyatlandı", "reference": "Matchbook + Smarkets",
             "research": {"flags": flags or []},
             "selections": [{"key": "13|3.5 Alt|0", "fair_prob": p_now, "odds": odds_now}]}
    (day / "nesine_global.json").write_text(json.dumps({"matches": [match]}), encoding="utf-8")


def test_check_warns_on_probability_drop_and_records_closing_price(tmp_path, monkeypatch):
    monkeypatch.setattr(kontrol, "DAILY", tmp_path)
    monkeypatch.setattr(kontrol, "AREA", tmp_path)
    _day(tmp_path, "2026-11-20T22:00:00+03:00", p_now=0.56)
    now = dt.datetime(2026, 11, 20, 21, 0, tzinfo=TSI)
    rows, clv = kontrol.check("2026-11-20", now)
    assert rows[0]["warn"] == ["olasılık 6 puan düştü"]
    assert rows[0]["new_warn"] == rows[0]["warn"]
    rec = clv["1|13|3.5 Alt|0"]
    assert rec["p_pick"] == 0.62 and rec["p_close"] == 0.56
    # a second run does not re-alert the same warning
    rows, _ = kontrol.check("2026-11-20", now)
    assert rows[0]["warn"] and not rows[0]["new_warn"]


def test_check_floor_odds_and_flags(tmp_path, monkeypatch):
    monkeypatch.setattr(kontrol, "DAILY", tmp_path)
    monkeypatch.setattr(kontrol, "AREA", tmp_path)
    _day(tmp_path, "2026-11-20T22:00:00+03:00", p_now=0.50, odds_now=1.18, flags=["TM: golcü eksik"])
    rows, _ = kontrol.check("2026-11-20", dt.datetime(2026, 11, 20, 21, 0, tzinfo=TSI))
    w = rows[0]["warn"]
    assert any("%55 altına" in x for x in w) and any("1,20 altında" in x for x in w) and "uyarı: TM: golcü eksik" in w


def test_closing_price_frozen_after_kickoff_and_clv_stats(tmp_path, monkeypatch):
    monkeypatch.setattr(kontrol, "DAILY", tmp_path)
    monkeypatch.setattr(kontrol, "AREA", tmp_path)
    _day(tmp_path, "2026-11-20T22:00:00+03:00", p_now=0.65)
    kontrol.check("2026-11-20", dt.datetime(2026, 11, 20, 21, 40, tzinfo=TSI))
    _day(tmp_path, "2026-11-20T22:00:00+03:00", p_now=0.40)  # in-play price after kick-off must not count
    after = dt.datetime(2026, 11, 20, 22, 30, tzinfo=TSI)
    rows, clv = kontrol.check("2026-11-20", after)
    assert rows[0]["started"] and clv["1|13|3.5 Alt|0"]["p_close"] == 0.65
    st = kontrol.clv_stats(clv, after)
    assert st["n"] == 1 and st["pos"] == 1 and abs(st["mean"] - 0.03) < 1e-9


def test_apply_live_odds_lowers_and_drops_suspended():
    matches = [{"code": 7, "selections": [
        {"key": "a", "odds": 1.71, "fair_prob": 0.58, "ev": 0.0},
        {"key": "b", "odds": 1.30, "fair_prob": 0.70, "ev": 0.0},
        {"key": "c", "odds": 2.00, "fair_prob": 0.40, "ev": 0.0}]},
        {"code": 8, "selections": [{"key": "x", "odds": 1.5, "fair_prob": 0.6, "ev": 0.0}]}]
    kupon.apply_live_odds(matches, {7: {"a": 1.65, "b": 1.35}})
    sel = {s["key"]: s for s in matches[0]["selections"]}
    assert sel["a"]["odds"] == 1.65 and abs(sel["a"]["ev"] - (0.58 * 1.65 - 1)) < 1e-12
    assert sel["b"]["odds"] == 1.30          # a higher live price is not used
    assert "c" not in sel                    # no longer offered
    assert matches[1]["selections"] == []  # unavailable matches cannot supply coupon legs


def test_prior_legs_block_same_selection_but_allow_other_selection_on_same_match(tmp_path, monkeypatch):
    monkeypatch.setattr(kupon, "AI_AREA", tmp_path)
    day = tmp_path / "2026-11-20"
    day.mkdir()
    leg = {"code": 1, "key": "1|MS 1|0", "name": "MS 1"}
    (day / "kupon_5x_0926.json").write_text(json.dumps({"coupons": [{"legs": [leg]}]}), encoding="utf-8")
    prior = kupon.prior_coupon_legs("2026-11-20", 10)
    assert prior == [leg] and kupon.prior_coupon_legs("2026-11-20", 5) == []
    pool = [[{"code": 1, "key": "1|MS 1|0", "name": "MS 1"}, {"code": 1, "key": "12|2.5 Üst|0", "name": "2.5 Üst"},
             {"code": 1, "key": "1|MS 2|0", "name": "MS 2"}]]
    left = {x["name"] for x in kupon.drop_conflicts(pool, prior)[0]}
    assert left == {"2.5 Üst"}  # same bet and the contradicting MS 2 are gone, a compatible bet stays


def test_claudetahmin_uses_own_run_and_own_coupons_and_freezes_started(tmp_path, monkeypatch):
    ai = _load("ai_tahmin")
    area = tmp_path / "area"

    def analysis(p):
        return [{"code": 1, "kickoff": "2026-11-20 20:00", "kickoff_iso": "2026-11-20T20:00:00+03:00", "league": "L",
                 "home": "A", "away": "B", "status": "fiyatlandı", "price_tier": "keskin",
                 "reference": "Matchbook + Smarkets (borsa)", "fair_1x2": [p, 0.25, 0.75 - p], "mu_home": 1.5,
                 "mu_away": 1.0, "selections": [{"key": "1|MS 1|0", "market": "Maç Sonucu", "selection": "1",
                                                 "name": "MS 1", "odds": 1.5, "fair_prob": p, "ev": 0.0, "direct": True}]}]

    leg = {"code": 1, "kickoff": "2026-11-20 20:00", "match": "A - B", "market": "Maç Sonucu", "selection": "1",
           "odds": 1.5, "p": 0.6}
    (area / "2026-11-20").mkdir(parents=True)
    for name, odds in (("kupon_5x_0800", 4.9), ("kupon_5x_0926", 5.01)):  # latest build per target counts
        (area / "2026-11-20" / f"{name}.json").write_text(json.dumps(
            {"coupons": [{"nesine_odds": odds, "probability": 0.12, "legs": [leg]}]}), encoding="utf-8")
    ai.export("2026-11-20", analysis(0.60), area, now=dt.datetime(2026, 11, 20, 19, 0, tzinfo=TSI))
    ai.export("2026-11-20", analysis(0.70), area, now=dt.datetime(2026, 11, 20, 21, 0, tzinfo=TSI))
    rows = ai._read(area / "2026-11-20" / "mac_tahminleri.csv")
    assert len(rows) == 1 and rows[0]["olasilik_1"] == "0.6000" and rows[0]["ana_secim"] == "1"
    c = ai._read(area / "2026-11-20" / "kuponlar.csv")
    assert [(r["kupon"], r["kupon_toplam_oran"], r["secim"]) for r in c] == [("kupon_5x_0926", "5.01", "1")]


def test_coupon_total_under_minimum_is_flagged(tmp_path, monkeypatch):
    monkeypatch.setattr(kontrol, "DAILY", tmp_path)
    monkeypatch.setattr(kontrol, "AREA", tmp_path)
    _day(tmp_path, "2026-11-20T22:00:00+03:00", p_now=0.62, odds_now=1.40)  # leg built at 1.50
    day = tmp_path / "2026-11-20"
    leg = json.loads((day / "kupon_5x_0851.json").read_text(encoding="utf-8"))["coupons"][0]["legs"][0]
    other = {**leg, "code": 2, "key": "x", "odds": 3.40}  # not in the analysis: keeps its built odds
    (day / "kupon_5x_0851.json").write_text(json.dumps(
        {"target": 5, "coupons": [{"nesine_odds": 5.10, "legs": [leg, other]}]}), encoding="utf-8")
    rows, _ = kontrol.check("2026-11-20", dt.datetime(2026, 11, 20, 21, 0, tzinfo=TSI))
    t = kontrol.coupon_totals("2026-11-20", rows)
    assert t == [{"coupon": "kupon_5x_0851 #1", "target": 5.0, "built": 5.10, "now": 4.76, "below": True, "missing": False}]


def test_families_leg_limits_and_groups():
    assert kupon.in_family("İY/MS 1/1", "iyms") and not kupon.in_family("İY 1.5 Alt", "iyms")
    assert kupon.in_family("2.5 Üst", "altust") and kupon.in_family("4.5 Alt", "altust")
    assert not kupon.in_family("İY 1.5 Alt", "altust") and not kupon.in_family("Ev 1.5 Alt", "altust")
    assert kupon.in_family("KG Yok", "kg") and not kupon.in_family("2.5 Alt & KG Yok", "kg")
    assert kupon.in_family("MS 2", "ms12") and not kupon.in_family("MS 0", "ms12")
    assert kupon.max_legs_for(5) == 7 and kupon.max_legs_for(10) == 7 and kupon.max_legs_for(20) == 8
    assert kupon.coupon_group(Path("kupon_5x_0926.json")) == ("5x", "karma")
    assert kupon.coupon_group(Path("kupon_5x_iyms_1030.json")) == ("5x", "iyms")


def test_prior_legs_cover_all_families_of_the_current_set(tmp_path, monkeypatch):
    monkeypatch.setattr(kupon, "AI_AREA", tmp_path)
    day = tmp_path / "2026-11-20"
    day.mkdir()

    def write(name, code, created):
        (day / f"{name}.json").write_text(json.dumps(
            {"created": created, "coupons": [{"legs": [{"code": code, "key": "k"}]}]}))

    write("kupon_5x_0900", 9, "2026-11-20T09:00:00+03:00")        # earlier set: ignored
    write("kupon_5x_1000", 1, "2026-11-20T10:00:00+03:00")
    write("kupon_10x_1001", 2, "2026-11-20T10:01:00+03:00")
    write("kupon_5x_ms12_1002", 3, "2026-11-20T10:02:00+03:00")
    (day / kupon.SET_FILE).write_text("2026-11-20T09:59:00+03:00\n")
    assert sorted(x["code"] for x in kupon.prior_coupon_legs("2026-11-20", 20)) == [1, 2, 3]
    assert sorted(x["code"] for x in kupon.prior_coupon_legs("2026-11-20", 5, "ms12")) == [1, 2]
    assert sorted(x["code"] for x in kupon.prior_coupon_legs("2026-11-20", 5)) == [2, 3]  # 5x karma being rebuilt
    (day / kupon.SET_FILE).unlink()
    write("kupon_5x_1000", 9, "2026-11-20T09:00:00+03:00")
    assert 9 in [x["code"] for x in kupon.prior_coupon_legs("2026-11-20", 10)]  # no set marker: every latest file



def test_check_uses_live_odds_over_analysis_odds(tmp_path, monkeypatch):
    monkeypatch.setattr(kontrol, "DAILY", tmp_path)
    monkeypatch.setattr(kontrol, "AREA", tmp_path)
    _day(tmp_path, "2026-11-20T22:00:00+03:00", p_now=0.62, odds_now=1.40)  # stale analysis odds
    now = dt.datetime(2026, 11, 20, 21, 0, tzinfo=TSI)
    rows, _ = kontrol.check("2026-11-20", now, live={1: {"13|3.5 Alt|0": 1.55}})
    assert rows[0]["odds_now"] == 1.55 and not rows[0]["warn"]
    rows, _ = kontrol.check("2026-11-20", now, live={1: {}})  # suspended on Nesine now
    assert "Nesine'de yok / askıda" in rows[0]["warn"]


def test_set_rule_same_match_other_selection_at_most_twice():
    # mirrors the coupon loop: never the same selection, a match in at most mac_limit coupons
    pools = [[{"code": 1, "key": "a", "name": "3.5 Alt"}, {"code": 1, "key": "b", "name": "MS 1"},
              {"code": 1, "key": "c", "name": "KG Yok"}], [{"code": 2, "key": "d", "name": "MS 2"}]]
    chosen = [{"code": 1, "key": "a", "name": "3.5 Alt"}]
    n = {1: 1}
    free = kupon.drop_conflicts([p for p in pools if n.get(p[0]["code"], 0) < 2], chosen)
    assert {x["name"] for x in free[0]} == {"MS 1", "KG Yok"}   # 3,5 Alt never again, other bets on the match allowed
    n = {1: 2}
    free = kupon.drop_conflicts([p for p in pools if n.get(p[0]["code"], 0) < 2], chosen + [{"code": 1, "key": "b", "name": "MS 1"}])
    assert [p[0]["code"] for p in free] == [2]                  # third coupon: the match is used up


def test_dashboard_publishes_settled_days_only(tmp_path, monkeypatch):
    dash = _load("build_dashboard")
    assert dash.current_betting_day(dt.datetime(2026, 11, 21, 6, 59, tzinfo=TSI)) == "2026-11-20"
    assert dash.current_betting_day(dt.datetime(2026, 11, 21, 7, 0, tzinfo=TSI)) == "2026-11-21"


def test_settlement_reads_own_folder_first_then_legacy_archive(tmp_path, monkeypatch):
    takip = _load("nesine_takip")
    own, legacy = tmp_path / "tahminler" / "claudetahmin", tmp_path / "reports" / "daily"
    monkeypatch.setattr(takip, "DAILY", own)
    monkeypatch.setattr(takip, "LEGACY_DAILY", legacy)
    (legacy / "2026-11-19").mkdir(parents=True)
    (own / "2026-11-20").mkdir(parents=True)
    assert takip.day_dir("2026-11-19") == legacy / "2026-11-19"   # days up to 19 Nov: old shared archive
    assert takip.day_dir("2026-11-20") == own / "2026-11-20"
    assert takip.day_dir("2026-11-22") == own / "2026-11-22"      # new days always go to the AI's own folder


def test_next_day_evaluation_reveals_finished_matches_only(tmp_path, monkeypatch):
    ev = _load("gun_degerlendirme")
    monkeypatch.setattr(ev, "TAHMIN", tmp_path)
    cols = ["tarih", "saat", "lig", "mac", "nesine_kodu", "olasilik_1", "olasilik_X", "olasilik_2", "beklenen_gol_ev",
            "beklenen_gol_dep", "en_olasi_skor", "ana_secim_pazar", "ana_secim", "nesine_oran", "olasilik", "fiyat_kaynagi", "guven", "not"]
    import csv as _csv

    def write(ai, rows, legs):
        d = tmp_path / ai / "2026-11-20"
        d.mkdir(parents=True)
        with (d / "mac_tahminleri.csv").open("w", encoding="utf-8-sig", newline="") as fh:
            w = _csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
        lc = ["tarih", "kupon_turu", "kupon", "kupon_no", "kupon_toplam_oran", "kupon_tutma_olasiligi", "saat", "mac",
              "nesine_kodu", "pazar", "secim", "nesine_oran", "olasilik"]
        with (d / "kuponlar.csv").open("w", encoding="utf-8-sig", newline="") as fh:
            w = _csv.DictWriter(fh, fieldnames=lc); w.writeheader(); w.writerows(legs)

    base = {c: "" for c in cols}
    write("claudetahmin",
          [{**base, "mac": "A - B", "nesine_kodu": "1", "olasilik_1": "0.6", "olasilik_X": "0.25", "olasilik_2": "0.15",
            "ana_secim_pazar": "2,5 Gol Alt/Üst", "ana_secim": "2,5 Üst", "nesine_oran": "1.80", "olasilik": "0.58"},
           {**base, "mac": "C - D", "nesine_kodu": "2", "ana_secim_pazar": "Maç Sonucu", "ana_secim": "1",
            "nesine_oran": "1.50", "olasilik": "0.65"}],                    # match 2 is still open
          [{"kupon_turu": "karma", "kupon": "kupon_5x_0900", "kupon_no": "1", "kupon_toplam_oran": "5.1",
            "kupon_tutma_olasiligi": "0.13", "mac": "A - B", "nesine_kodu": "1", "pazar": "Karşılıklı Gol", "secim": "Var"}])
    write("geminitahmin", [{**base, "mac": "A - B", "nesine_kodu": "1", "ana_secim_pazar": "Maç Sonucu", "ana_secim": "2",
                            "nesine_oran": "4.0", "olasilik": "0.30"}], [])
    rep = ev.evaluate("2026-11-20", results={1: {"completed": True, "ht": [1, 0], "ft90": [2, 1]}, 2: {"completed": False}})
    c, g = rep["ais"]["claudetahmin"], rep["ais"]["geminitahmin"]
    assert c["main_picks"] == 1 and c["hits"] == 1 and abs(c["flat_return"] - 0.80) < 1e-9
    assert c["coupons"][0]["won"] is True and c["n_1x2"] == 1
    assert g["hits"] == 0 and g["flat_return"] == -1 and g["biggest_misses"][0]["match"] == "A - B"
    assert list(rep["matches"]) == ["1"]                       # the open match 2 is never written
    md = ev.to_markdown(rep)
    assert "C - D" not in md and "✓ 2,5 Gol Alt/Üst: 2,5 Üst" in md


def test_weekly_report_only_on_request_and_into_own_folder(tmp_path, monkeypatch):
    ng = _load("nesine_global")
    monkeypatch.setattr(ng, "DAILY", tmp_path / "tahminler" / "claudetahmin")
    monkeypatch.setattr(ng, "ROOT", tmp_path)
    ng.write_week(dt.date(2026, 11, 20), [("2026-11-20", [])], 0.0)
    assert (tmp_path / "tahminler" / "claudetahmin" / "hafta" / "2026-11-20_nesine_hafta.md").exists()
    src = (SCRIPTS / "nesine_global.py").read_text(encoding="utf-8")
    assert "if args.haftalik:" in src and '"--haftalik"' in src  # never written without the flag


def test_deep_research_orients_history_and_tests_the_leg(tmp_path, monkeypatch):
    dr = _load("derin_arastirma")
    # home team's past games: it scored in both halves twice; once it played away (must be flipped to "home")
    home_games = [{"event": "1", "date": "2026-11-01", "side": "home", "opp": "X", "opp_id": "9", "for": (1, 1), "against": (0, 1)},
                  {"event": "2", "date": "2026-11-08", "side": "away", "opp": "Y", "opp_id": "8", "for": (0, 2), "against": (2, 0)},
                  {"event": "3", "date": "2026-11-15", "side": "home", "opp": "Z", "opp_id": "7", "for": (1, 0), "against": (0, 0)}]
    away_games = [{"event": "4", "date": "2026-11-02", "side": "away", "opp": "Q", "opp_id": "6", "for": (0, 0), "against": (1, 2)}]
    assert dr.oriented(home_games[1], "home") == ((0, 2), (2, 2))   # team kept on the home side
    assert dr.oriented(away_games[0], "away") == ((1, 0), (3, 0))
    h = dr.leg_history("MS 1", home_games, away_games)
    assert h["home_rate"] == 2 / 3 and h["away_rate"] == 1.0 and h["home_n"] == 3 and h["away_n"] == 1
    p = dr.profile(home_games)
    assert p["n"] == 3 and p["score2H"] == 2 / 3 and p["both_halves_btts"] == 0.0 and p["form"] == "GBG"
    assert dr.verdict(0.6, {"mean": 0.3, "home_n": 10, "away_n": 9}).startswith("⚠")
    assert dr.verdict(0.6, {"mean": 0.62, "home_n": 10, "away_n": 9}).startswith("✓")
    assert dr.verdict(0.6, {"mean": 0.62, "home_n": 3, "away_n": 9}) == "geçmiş yetersiz"


def test_deep_research_caches_espn_and_throttles(tmp_path, monkeypatch):
    dr = _load("derin_arastirma")
    monkeypatch.setattr(dr, "CACHE", tmp_path)
    monkeypatch.setattr(dr, "MIN_INTERVAL_S", 0.0)
    calls = []

    class R:
        status_code = 200
        def json(self):
            return {"ok": 1}

    monkeypatch.setattr(dr._session, "get", lambda url, params=None, timeout=None: calls.append(url) or R())
    assert dr.espn("nor.1/summary", None, event="1") == {"ok": 1}
    assert dr.espn("nor.1/summary", None, event="1") == {"ok": 1}   # second time from the cache
    assert len(calls) == 1


def test_evaluation_scores_research_verdicts_and_accumulates(tmp_path, monkeypatch):
    ev = _load("gun_degerlendirme")
    monkeypatch.setattr(ev, "TAHMIN", tmp_path / "tahminler")
    monkeypatch.setattr(ev, "OUT", tmp_path / "degerlendirme")
    d = tmp_path / "tahminler" / "claudetahmin" / "2026-11-20"
    d.mkdir(parents=True)
    (d / "derin_arastirma.json").write_text(json.dumps([
        {"code": 1, "legs": [{"name": "2.5 Üst", "p": 0.6, "mean": 0.65, "verdict": "✓ geçmiş destekliyor"},
                             {"name": "MS 2", "p": 0.55, "mean": 0.25, "verdict": "⚠ geçmiş desteklemiyor"}]},
        {"code": 2, "legs": [{"name": "KG Var", "p": 0.58, "mean": None, "verdict": "geçmiş yetersiz"}]}]), encoding="utf-8")
    v = ev.research_verdicts(d, {1: {"completed": True, "ht": [1, 0], "ft90": [2, 1]}, 2: {"completed": False}})
    assert v["✓"]["n"] == 1 and v["✓"]["won"] == 1 and v["⚠"]["won"] == 0 and "?" not in v   # open match 2 not scored
    out = tmp_path / "degerlendirme"
    out.mkdir()
    (out / "2026-11-20.json").write_text(json.dumps({"date": "2026-11-20", "ais": {"claudetahmin": {"research_verdicts": v}}}))
    (out / "2026-11-21.json").write_text(json.dumps({"date": "2026-11-21", "ais": {"claudetahmin": {"research_verdicts": v}}}))
    md = ev.cumulative_verdicts(out)
    assert "| ⚠ geçmiş desteklemiyor | 2 | 0 | %0.0 |" in md and "| ✓ geçmiş destekliyor | 2 | 2 | %100.0 |" in md


def test_deep_research_links_unlinked_match_by_league_time_and_name(monkeypatch):
    dr = _load("derin_arastirma")
    board = {"events": [{"id": "77", "date": "2026-11-20T11:30Z", "competitions": [{"competitors": [
        {"homeAway": "home", "team": {"displayName": "East Bengal"}}, {"homeAway": "away", "team": {"displayName": "Sporting Club Delhi"}}]}]}]}
    monkeypatch.setattr(dr, "espn", lambda path, ttl=None, **kw: board if path == "ind.1/scoreboard" else None)
    m = {"league": "Hindistan Süper Ligi", "home": "SC East Bengal", "away": "Hyderabad", "kickoff_iso": "2026-11-20T14:30:00+03:00"}
    assert dr.find_espn_event(m) == ("ind.1", "77")
    assert dr.find_espn_event({**m, "kickoff_iso": "2026-11-20T18:30:00+03:00"}) is None   # other kick-off time
    assert dr.find_espn_event({**m, "league": "Etiyopya Premier Lig"}) is None              # league not on ESPN


def test_bulletin_fetch_retries_a_dropped_connection(monkeypatch):
    import requests
    from quantfoot.data import nesine
    calls = []

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"sg": {}}

    def get(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise requests.ConnectionError("dropped")
        return R()

    monkeypatch.setattr(nesine.requests, "get", get)
    monkeypatch.setattr(nesine.time, "sleep", lambda s: None)
    assert nesine.fetch_bulletin() == {"sg": {}} and len(calls) == 2


def test_all_coupon_legs_today_covers_every_build(tmp_path, monkeypatch):
    monkeypatch.setattr(kupon, "AI_AREA", tmp_path)
    day = tmp_path / "2026-11-20"
    day.mkdir()
    for name, code in (("kupon_5x_0851", 1), ("kupon_5x_0926", 2), ("kupon_10x_kg_1141", 3)):
        (day / f"{name}.json").write_text(json.dumps({"coupons": [{"legs": [{"code": code, "key": "k"}]}]}))
    assert sorted(x["code"] for x in kupon.all_coupon_legs_today("2026-11-20")) == [1, 2, 3]  # old builds too


def test_deep_research_refreshes_a_summary_cached_before_kickoff(monkeypatch):
    dr = _load("derin_arastirma")
    pre = {"header": {"competitions": [{"status": {"type": {"completed": False}}, "competitors": []}]}}
    post = {"header": {"competitions": [{"status": {"type": {"completed": True}}, "competitors": [
        {"team": {"id": "1", "displayName": "A"}, "homeAway": "home", "linescores": [{"displayValue": "1"}, {"displayValue": "0"}]},
        {"team": {"id": "2", "displayName": "B"}, "homeAway": "away", "linescores": [{"displayValue": "0"}, {"displayValue": "2"}]}]}]}}
    monkeypatch.setattr(dr, "espn", lambda path, ttl=None, **kw: pre if ttl is None else post)
    assert dr.half_scores("nor.1", "9") == {"1": (1, 0, "home", "A"), "2": (0, 2, "away", "B")}


def test_kupon_kur_rejects_warned_legs(monkeypatch):
    kk = _load("kupon_kur")
    legs = [{"code": i, "key": f"k{i}", "match": f"M{i}", "market": "Maç Sonucu", "selection": "1", "name": "MS 1",
             "p": 0.6, "odds": 1.5} for i in range(5)]
    monkeypatch.setattr(kk.dr, "research_match", lambda m, l: {"legs": [{"verdict": "⚠ geçmiş desteklemiyor" if m["code"] == 4 else "✓", "mean": 0.3}]})
    bad, rows = kk.check(legs, {str(i): {"code": i} for i in range(5)})
    assert [b[0]["code"] for b in bad] == [4] and len(rows) == 5
    assert not hasattr(kk, "clustered")   # no league / kick-off limit (user decision, 20 Nov)


def test_closed_nesine_markets_are_not_offered():
    from quantfoot.data.nesine import parse_bulletin
    ev = {"TYPE": 1, "C": 7, "HN": "A", "AN": "B", "ESD": 1795186800000, "LC": 1,
          "MA": [{"MTID": 1, "SOV": 0.0, "MS": 1, "OCA": [{"N": 1, "O": 1.5}, {"N": 2, "O": 4.0}, {"N": 3, "O": 6.0}]},
                 {"MTID": 12, "SOV": 2.5, "MS": 0, "OCA": [{"N": 1, "O": 2.04}, {"N": 2, "O": 1.34}]}]}
    names = {s.name for s in parse_bulletin({"sg": {"EA": [ev]}})[0].selections}
    assert "MS 1" in names and "2.5 Üst" not in names and "2.5 Alt" not in names


def test_watcher_day_and_active_coupons(tmp_path, monkeypatch):
    monkeypatch.setattr(kontrol, "AREA", tmp_path)
    assert kontrol.betting_day(dt.datetime(2026, 11, 21, 2, 0, tzinfo=TSI)) == "2026-11-20"
    assert kontrol.betting_day(dt.datetime(2026, 11, 21, 8, 0, tzinfo=TSI)) == "2026-11-21"
    d = tmp_path / "2026-11-20"
    d.mkdir()
    for n in ("kupon_5x_0851", "kupon_5x_1629", "kupon_3x_1620", "kupon_5x_kg_1141"):
        (d / f"{n}.json").write_text("{}")
    assert kontrol.active_coupons("2026-11-20") == {"kupon_5x_1629", "kupon_3x_1620", "kupon_5x_kg_1141"}
    (d / "kupon_5x_2350.json").write_text("{}", encoding="utf-8")
    (d / "kupon_5x_0010.json").write_text('{"created":"2026-11-21T00:10:00+03:00"}', encoding="utf-8")
    assert kontrol.active_coupons("2026-11-20") == {"kupon_5x_0010", "kupon_3x_1620", "kupon_5x_kg_1141"}



def test_kupon_kontrol_reads_single_custom_and_system_coupon_schemas_and_skips_meta(tmp_path, monkeypatch):
    monkeypatch.setattr(kontrol, "DAILY", tmp_path)
    monkeypatch.setattr(kontrol, "AREA", tmp_path)
    day = tmp_path / "2026-11-22"
    day.mkdir()
    # 1. Tekil şema (top-level legs)
    (day / "kupon_10x_17sonrasi.json").write_text(json.dumps({
        "target": 10.0,
        "nesine_odds": 10.1,
        "legs": [{"code": 11, "key": "k1", "kickoff": "2026-11-22 20:00", "match": "A - B",
                  "market": "Alt/Üst", "selection": "2.5 Üst", "odds": 1.40, "p": 0.65}],
    }), encoding="utf-8")
    # 2. Özel isimli çoklu şema (kupon_en_emin_*)
    (day / "kupon_en_emin_17sonrasi.json").write_text(json.dumps({
        "coupons": [{"nesine_odds": 3.1, "legs": [{"code": 12, "key": "k2", "kickoff": "2026-11-22 21:00",
                                                  "match": "C - D", "market": "Alt/Üst", "selection": "3.5 Alt",
                                                  "odds": 1.30, "p_raw": 0.72}]}],
    }), encoding="utf-8")
    # 3. Sistem şeması (primary_system.legs)
    (day / "kupon_sistem_21_12_100tl.json").write_text(json.dumps({
        "primary_system": {"legs": [{"code": 13, "kickoff": "2026-11-22 22:00", "match": "E - F",
                                     "name": "İY/MS 2/1", "odds": 25.0, "p": 0.05}]},
    }), encoding="utf-8")
    # Meta dosyaları kesinlikle kupon olarak sayılmamalı
    (day / "kupon_clv.json").write_text(json.dumps({"11|k1": {"p_pick": 0.65}}), encoding="utf-8")

    legs = kontrol.coupon_legs("2026-11-22")
    assert set(legs) == {"11|k1", "12|k2", "13|İY/MS 2/1"}
    assert legs["12|k2"]["p"] == 0.72
    act = kontrol.active_coupons("2026-11-22")
    assert act == {"kupon_10x_17sonrasi", "kupon_en_emin_17sonrasi", "kupon_sistem_21_12_100tl"}


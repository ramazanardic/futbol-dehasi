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
    monkeypatch.setattr(kupon, "CLAUDE_AREA", tmp_path)
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
    assert matches[1]["selections"][0]["odds"] == 1.5  # match not in the bulletin (started): untouched


def test_prior_legs_block_same_selection_but_allow_other_selection_on_same_match(tmp_path, monkeypatch):
    monkeypatch.setattr(kupon, "CLAUDE_AREA", tmp_path)
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
    monkeypatch.setattr(kupon, "CLAUDE_AREA", tmp_path)
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


def test_scheduler_recovers_from_autostash_conflict_on_generated_files(tmp_path, monkeypatch):
    import subprocess
    sched = _load("scheduled")
    monkeypatch.setattr(sched, "ROOT", tmp_path)

    def git(*a):
        return subprocess.run(["git", *a], cwd=tmp_path, capture_output=True, text=True, check=False)

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    f = tmp_path / "reports" / "x.json"
    f.parent.mkdir()
    f.write_text("v1\n")
    git("add", "-A")
    git("commit", "-qm", "v1")
    f.write_text("pc-latest\n")       # this PC's regeneration (uncommitted)
    git("stash", "push", "-q")
    f.write_text("remote\n")          # what came from GitHub
    git("commit", "-qam", "remote")
    git("stash", "apply", "-q")       # conflicts, as the autostash did on 20 Nov
    assert git("diff", "--name-only", "--diff-filter=U").stdout.strip() == "reports/x.json"
    log = []
    sched._recover(SimpleNamespace(write=log.append))
    assert git("diff", "--name-only", "--diff-filter=U").stdout.strip() == ""
    assert f.read_text() == "pc-latest\n" and any("çakışma çözüldü" in x for x in log)


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


def test_unsettled_days_are_kept_off_github(tmp_path, monkeypatch):
    sched = _load("scheduled")
    monkeypatch.setattr(sched, "ROOT", tmp_path)
    for d in ("2026-11-19", "2026-11-20", "2026-11-21"):
        (tmp_path / "reports" / "daily" / d).mkdir(parents=True)
        (tmp_path / "tahminler" / "claudetahmin" / d).mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "data").mkdir(parents=True)
    for d in ("2026-11-19", "2026-11-20", "dashboard"):
        (tmp_path / "docs" / "data" / f"{d}.json").write_text("{}")
    ex = sched._unsettled_excludes(dt.datetime(2026, 11, 21, 3, 0))  # 03:00: betting day is still the 20th
    assert ":(exclude)reports/daily/2026-11-20" in ex and ":(exclude)reports/daily/2026-11-21" in ex
    assert ":(exclude)tahminler/claudetahmin/2026-11-20" in ex and ":(exclude)docs/data/2026-11-20.json" in ex
    assert not any("2026-11-19" in x for x in ex) and not any("dashboard" in x for x in ex)
    assert not any("2026-11-20" in x for x in sched._unsettled_excludes(dt.datetime(2026, 11, 21, 9, 0)))


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

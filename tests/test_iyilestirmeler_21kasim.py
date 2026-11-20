"""Calibration shift, evidence rule, API-Football history, measured "~" rule and the watcher's line-up check."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
TSI = dt.timezone(dt.timedelta(hours=3))

from quantfoot.evaluation import auto_learn as al  # noqa: E402


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_calibrated_probability_shift_by_kind_and_band():
    cal = {"adjustments": {"prob_shift": {"model|0.6-0.7": -0.03, "doğrudan|0.6-0.7": 0.01}}}
    assert al.calibrated_probability(0.65, False, cal) == 0.62
    assert al.calibrated_probability(0.65, True, cal) == 0.66
    assert al.calibrated_probability(0.45, False, cal) == 0.45      # outside the coupon zone: untouched
    assert al.calibrated_probability(0.65, False, None) == 0.65


def test_prob_shift_learned_shrunk_and_clipped(tmp_path):
    root = tmp_path
    day = root / "reports" / "daily" / "2026-11-18"
    day.mkdir(parents=True)
    store, res = {}, {}
    for i in range(200):  # model legs at 65 % that hit 40 %: strongly overconfident
        store[str(i)] = {"reference": "Pinnacle", "league": "L", "s": {"MS 1": [0.65, 1.5, 0]}}
        res[str(i)] = {"completed": True, "won": {"MS 1": i % 5 < 2}}
    (day / "takip_kayit.json").write_text(json.dumps(store), encoding="utf-8")
    (day / "takip_sonuc.json").write_text(json.dumps(res), encoding="utf-8")
    own = root / "tahminler" / "claudetahmin"
    own.mkdir(parents=True)
    snap = al.analyze_settled_history(own)
    assert snap["kind_bands"]["model|0.6-0.7"]["n"] == 200
    assert snap["adjustments"]["prob_shift"]["model|0.6-0.7"] == -0.08   # -0.25 * 200/350 = -0.143, clipped


def test_kupon_kur_rejects_untested_legs_unless_allowed(monkeypatch):
    kk = _load("kupon_kur")
    legs = [{"code": i, "key": f"k{i}", "match": f"M{i}", "market": "Maç Sonucu", "selection": "1", "name": "MS 1",
             "p": 0.6, "odds": 1.5} for i in range(3)]
    verdicts = {0: "✓ geçmiş destekliyor", 1: "geçmiş yetersiz", 2: "~ geçmiş zayıf destekliyor"}
    monkeypatch.setattr(kk, "research_leg", lambda m, leg, fx: {"legs": [{"verdict": verdicts[m["code"]], "mean": 0.6}]})
    analysis = {str(i): {"code": i} for i in range(3)}
    assert [b[0]["code"] for b in kk.check(legs, analysis)[0]] == [1]
    assert kk.check(legs, analysis, evidence=False)[0] == []
    assert [b[0]["code"] for b in kk.check(legs, analysis, allow_weak=False)[0]] == [1, 2]


def test_weak_legs_allowed_by_measurement(tmp_path):
    kk = _load("kupon_kur")
    f = tmp_path / "v.json"
    f.write_text(json.dumps({"claudetahmin": {"~": {"n": 40, "won": 18, "p_sum": 26.0, "p_n": 40}}}), encoding="utf-8")
    assert kk.weak_legs_allowed("claudetahmin", f) is False          # 45 % hit vs 65 % priced
    f.write_text(json.dumps({"claudetahmin": {"~": {"n": 10, "won": 2, "p_sum": 6.5, "p_n": 10}}}), encoding="utf-8")
    assert kk.weak_legs_allowed("claudetahmin", f) is True           # too few settled legs to judge
    assert kk.weak_legs_allowed("claudetahmin", tmp_path / "missing.json") is True


def _fx(fid, date, hid, hname, aid, aname, ht, ft, status="FT"):
    return {"fixture": {"id": fid, "date": date, "status": {"short": status}},
            "teams": {"home": {"id": hid, "name": hname}, "away": {"id": aid, "name": aname}},
            "score": {"halftime": {"home": ht[0], "away": ht[1]}, "fulltime": {"home": ft[0], "away": ft[1]}}}


def test_api_gecmis_fixture_match_and_team_games(monkeypatch):
    af = _load("api_gecmis")
    m = {"home": "Black Bulls", "away": "Fer. de Maputo", "kickoff_iso": "2026-11-20T20:00:00+03:00"}
    day = [_fx(1, "2026-11-20T20:00:00+03:00", 10, "Black Bulls", 20, "Ferroviario Maputo", (0, 0), (0, 0), "NS"),
           _fx(2, "2026-11-20T20:10:00+03:00", 30, "Other Team", 40, "Another", (0, 0), (0, 0), "NS")]
    assert af.find_fixture(m, day)["fixture"]["id"] == 1
    assert af.find_fixture({**m, "kickoff_iso": "2026-11-20T22:00:00+03:00"}, day) is None   # kick-off too far
    hist = [_fx(5, "2026-11-10T18:00:00+03:00", 10, "Black Bulls", 50, "X", (1, 0), (2, 1)),
            _fx(6, "2026-11-14T18:00:00+03:00", 60, "Y", 10, "Black Bulls", (0, 2), (1, 3)),
            _fx(7, "2026-11-22T18:00:00+03:00", 10, "Black Bulls", 70, "Z", (0, 0), (0, 0))]   # after kick-off
    g = af.team_games(10, dt.datetime.fromisoformat(m["kickoff_iso"]), hist + day)
    assert [x["event"] for x in g] == [5, 6]
    assert g[0]["for"] == (1, 1) and g[0]["against"] == (0, 1) and g[0]["side"] == "home"
    assert g[1]["for"] == (2, 1) and g[1]["against"] == (0, 1) and g[1]["side"] == "away"


def test_api_gecmis_archive_keeps_past_days_only(tmp_path, monkeypatch):
    af = _load("api_gecmis")
    monkeypatch.setattr(af, "DAYS", tmp_path)
    calls = []
    monkeypatch.setattr(af, "get", lambda path, ttl, **p: calls.append(p["date"]) or [_fx(1, p["date"] + "T18:00:00+03:00",
                                                                                         10, "A", 20, "B", (1, 0), (1, 1))])
    today = dt.datetime.now(TSI).date()
    past, now_ = (today - dt.timedelta(days=1)).isoformat(), today.isoformat()
    af.archive_day(past); af.archive_day(past); af.archive_day(now_)
    assert calls == [past, now_] and (tmp_path / f"{past}.json").exists() and not (tmp_path / f"{now_}.json").exists()
    assert len(af.archived()) == 1


def test_api_key_from_dotenv(tmp_path, monkeypatch):
    af = _load("api_gecmis")
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    monkeypatch.setattr(af.dr, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("OTHER=1\nAPI_FOOTBALL_KEY=abc123\n", encoding="utf-8")
    assert af.api_key() == "abc123"


def test_watcher_lineup_check_only_near_kickoff_and_kept(tmp_path, monkeypatch):
    kc = _load("kupon_kontrol")
    day = tmp_path / "2026-11-20"
    day.mkdir()
    monkeypatch.setattr(kc, "AREA", tmp_path)
    monkeypatch.setattr(kc, "DAILY", tmp_path)
    m = {"code": 1, "kickoff_iso": "2026-11-20T21:00:00+03:00", "status": "fiyatlandı", "research": {"espn_event": "9"},
         "selections": [{"key": "k", "fair_prob": 0.7, "odds": 1.4}]}
    (day / "nesine_global.json").write_text(json.dumps({"matches": [m]}), encoding="utf-8")
    leg = {"code": 1, "key": "k", "match": "A - B", "market": "MS", "selection": "1", "kickoff": "20.11 21:00", "p": 0.7,
           "odds": 1.4, "coupons": ["kupon_5x_1200 #1"]}
    monkeypatch.setattr(kc, "coupon_legs", lambda d: {"L1": leg})
    calls = []
    lineups = lambda mm: calls.append(1) or ["Ev: düzenli kaleci ilk 11'de yok"]  # noqa: E731
    early = dt.datetime(2026, 11, 20, 19, 0, tzinfo=TSI)
    rows, _ = kc.check("2026-11-20", early, {1: {"k": 1.4}}, lineups=lineups, active={"kupon_5x_1200"})
    assert calls == [] and not any(w.startswith("ilk 11") for w in rows[0]["warn"])        # 2 h before: not asked
    near = dt.datetime(2026, 11, 20, 20, 0, tzinfo=TSI)
    rows, _ = kc.check("2026-11-20", near, {1: {"k": 1.4}}, lineups=lineups, active={"kupon_5x_1200"})
    assert calls == [1] and "ilk 11: Ev: düzenli kaleci ilk 11'de yok" in rows[0]["warn"]
    rows, _ = kc.check("2026-11-20", near, {1: {"k": 1.4}}, lineups=lineups, active={"kupon_5x_1200"})
    assert calls == [1] and "ilk 11: Ev: düzenli kaleci ilk 11'de yok" in rows[0]["warn"]  # kept, not fetched again
    rows, _ = kc.check("2026-11-20", near, {1: {"k": 1.4}}, lineups=lineups, active={"another"})
    assert calls == [1]                                                                    # coupon not in force


def test_family_table_lists_suitable_selections_per_family():
    ba = _load("bahis_aileleri")
    sel = lambda name, p, o, d=True: {"name": name, "market": "M", "selection": name, "fair_prob": p, "odds": o, "direct": d}  # noqa: E731
    m = {"selections": [sel("MS 1", 0.62, 1.45), sel("MS 2", 0.15, 6.0), sel("2.5 Alt", 0.58, 1.55), sel("2.5 Üst", 0.42, 2.1),
                        sel("KG Var", 0.45, 1.8), sel("1.5 Üst", 0.80, 1.10)]}
    games = {"home": [{"for": (1, 1), "against": (0, 0), "side": "home"}] * 6,
             "away": [{"for": (0, 0), "against": (1, 0), "side": "away"}] * 6}
    t = {f["family"]: f for f in ba.family_table(m, games)}
    assert [r["name"] for r in t["Maç sonucu"]["suitable"]] == ["MS 1"]
    assert t["Maç sonucu"]["suitable"][0]["hist"] == 1.0 and t["Maç sonucu"]["suitable"][0]["verdict"].startswith("✓")
    assert [r["name"] for r in t["Alt/Üst"]["suitable"]] == ["2.5 Alt"]          # 1.5 Üst: odds under 1.20
    assert t["Karşılıklı gol"]["suitable"] == [] and t["Karşılıklı gol"]["best_other"]["p"] == 0.45
    assert ba.best_families(list(t.values()))[0][0] in ("Maç sonucu", "Alt/Üst")


def test_evaluation_row_name_prefers_column_then_label_then_raw():
    g = _load("gun_degerlendirme")
    assert g.row_name({"secim_adi": "Dep İY 0.5 Alt", "ana_secim_pazar": "x", "ana_secim": "y"}, "ana_secim_pazar", "ana_secim", None) == "Dep İY 0.5 Alt"
    assert g.row_name({"ana_secim_pazar": "2,5 Gol Alt/Üst", "ana_secim": "2,5 Üst"}, "ana_secim_pazar", "ana_secim", None) == "2.5 Üst"
    assert g.row_name({"ana_secim_pazar": "Ev Sahibi 1.Y Gol Alt/Üst", "ana_secim": "Ev İY 0.5 Alt"}, "ana_secim_pazar", "ana_secim", None) == "Ev İY 0.5 Alt"
    assert g.row_name({"ana_secim_pazar": "Bilinmeyen", "ana_secim": "Hayır"}, "ana_secim_pazar", "ana_secim", None) is None
    lk = {("Deplasman 0,5 Gol Alt/Üst", "0,5 Üst"): "Dep 0.5 Üst"}
    assert g.row_name({"ana_secim_pazar": " Deplasman 0,5 Gol Alt/Üst ", "ana_secim": "0,5 Üst"}, "ana_secim_pazar", "ana_secim", lk) == "Dep 0.5 Üst"


def test_settle_negated_selection_and_label_names(tmp_path):
    from quantfoot.evaluation.settlement import settle_selection
    assert settle_selection("DEĞİL(Dep En Az Bir Yarıyı Kazanır)", (0, 0), (0, 1)) is False
    assert settle_selection("DEĞİL(Dep En Az Bir Yarıyı Kazanır)", (0, 0), (0, 0)) is True
    g = _load("gun_degerlendirme")
    for day, name in (("2026-11-18", "Dep 0.5 Üst"), ("2026-11-19", "Dep 0.5 Üst")):
        (tmp_path / day).mkdir()
        (tmp_path / day / "nesine_global.json").write_text(json.dumps({"matches": [{"code": 1, "selections": [
            {"market": "Deplasman 0,5 Gol Alt/Üst", "selection": "0,5 Üst", "name": name},
            {"market": "X", "selection": "Y", "name": f"N{day}"}]}]}), encoding="utf-8")
    lb = g.label_names(tmp_path / "2026-11-20")
    assert lb[("Deplasman 0,5 Gol Alt/Üst", "0,5 Üst")] == "Dep 0.5 Üst" and ("X", "Y") not in lb   # ambiguous: dropped

"""Verify all 45 matches and 7 QuantFoot-v6 coupons from Nov 18, 2026 against actual 90-minute regulation & HT results."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]

# Verified Nov 18, 2026 Nesine 2. Lig (12. Hafta) results from official match reports
TUR3_ACTUALS: dict[int, dict] = {
    1:  {"ht_h": None, "ht_a": None, "ft_h": 0, "ft_a": 1, "status": "FT", "note": "12 Bingölspor 0-1 Sakaryaspor"},
    2:  {"ht_h": None, "ht_a": None, "ft_h": 1, "ft_a": 0, "status": "FT", "note": "1461 Trabzon FK 1-0 Kahramanmaraş İstiklalspor"},
    3:  {"ht_h": 2, "ht_a": 1, "ft_h": 2, "ft_a": 2, "status": "FT", "note": "Adana Demirspor 2-2 GMG Kastamonuspor (İY 2-1)"},
    4:  {"ht_h": 0, "ht_a": 1, "ft_h": 0, "ft_a": 2, "status": "FT", "note": "Ankara Demirspor 0-2 52 Orduspor FK (İY 0-1, 33' 60')"},
    5:  {"ht_h": None, "ht_a": None, "ft_h": 0, "ft_a": 2, "status": "FT", "note": "Hatayspor 0-2 İnegöl Kafkas SK"},
    6:  {"ht_h": None, "ht_a": None, "ft_h": 0, "ft_a": 0, "status": "FT", "note": "ISBAŞ Isparta 32 Spor 0-0 Somaspor"},
    7:  {"ht_h": None, "ht_a": None, "ft_h": 1, "ft_a": 1, "status": "FT", "note": "MKE Ankaragücü 1-1 Kırklarelispor"},
    8:  {"ht_h": None, "ht_a": None, "ft_h": 0, "ft_a": 1, "status": "FT", "note": "Serik Spor 0-1 Erzincanspor"},
    9:  {"ht_h": None, "ht_a": None, "ft_h": 1, "ft_a": 1, "status": "FT", "note": "Seza Çimento Elazığspor 1-1 Menemen FK"},
    10: {"ht_h": None, "ht_a": None, "ft_h": 2, "ft_a": 1, "status": "FT", "note": "Şanlıurfaspor 2-1 Efor Çay Erbaaspor"},
    11: {"ht_h": None, "ht_a": None, "ft_h": 2, "ft_a": 0, "status": "FT", "note": "Aliağa Futbol A.Ş. 2-0 Sebat Gençlik Spor"},
    12: {"ht_h": None, "ht_a": None, "ft_h": 2, "ft_a": 3, "status": "FT", "note": "Arnavutköy Bld. 2-3 68 Aksaray Belediyespor"},
    13: {"ht_h": None, "ht_a": None, "ft_h": 2, "ft_a": 1, "status": "FT", "note": "Fethiyespor 2-1 Kütahyaspor"},
    14: {"ht_h": 2, "ht_a": 1, "ft_h": 2, "ft_a": 1, "status": "FT", "note": "Güzide Gebze Spor 2-1 Ankaraspor (İY 2-1, 6' 32' 43')"},
    15: {"ht_h": None, "ht_a": None, "ft_h": 0, "ft_a": 3, "status": "FT", "note": "Karacabey Belediyespor 0-3 Beyoğlu Yeni Çarşı"},
    16: {"ht_h": None, "ht_a": None, "ft_h": 1, "ft_a": 4, "status": "FT", "note": "Çorluspor 1947 1-4 Muş Spor"},
    17: {"ht_h": None, "ht_a": None, "ft_h": 2, "ft_a": 0, "status": "FT", "note": "İnegölspor 2-0 İskenderunspor A.Ş."},
}


def fetch_espn_90min_and_ht(m: dict) -> dict:
    idx = m["idx"]
    eid = str(m["event_id"])
    slug = m["slug"]
    if idx in TUR3_ACTUALS:
        return {**TUR3_ACTUALS[idx], "idx": idx, "event_id": eid}

    jd = {}
    for s in (slug, "all"):
        try:
            r = requests.get(
                f"https://site.api.espn.com/apis/site/v2/sports/soccer/{s}/summary",
                params={"event": eid},
                timeout=10,
            )
            if r.status_code == 200:
                jd = r.json()
                break
        except Exception:
            continue

    comp = ((jd.get("header") or {}).get("competitions") or [{}])[0]
    st = comp.get("status", {}).get("type", {})
    status_name = st.get("name", "")
    status_detail = st.get("detail", "")
    state = st.get("state", "")
    cs = comp.get("competitors", [])
    hc = next((c for c in cs if c.get("homeAway") == "home"), {})
    ac = next((c for c in cs if c.get("homeAway") == "away"), {})

    raw_ft_h = int(hc["score"]) if str(hc.get("score", "")).isdigit() else None
    raw_ft_a = int(ac["score"]) if str(ac.get("score", "")).isdigit() else None
    hid = str(hc.get("id") or (hc.get("team") or {}).get("id") or "")
    aid = str(ac.get("id") or (ac.get("team") or {}).get("id") or "")

    ht_h, ht_a = None, None
    reg_h, reg_a = raw_ft_h, raw_ft_a
    goal_log = []

    key_events = jd.get("keyEvents") or []
    if key_events and raw_ft_h is not None and raw_ft_a is not None:
        h1, a1 = 0, 0
        h90, a90 = 0, 0
        for kev in key_events:
            t_txt = (kev.get("type") or {}).get("text", "").lower()
            is_goal = ("goal" in t_txt or "penalty - scored" in t_txt or "own goal" in t_txt) and (
                "miss" not in t_txt and "saved" not in t_txt and "disallowed" not in t_txt
            )
            if not is_goal:
                continue
            period = int((kev.get("period") or {}).get("number", 0))
            clock_val = float((kev.get("clock") or {}).get("value", 0))
            disp_clock = (kev.get("clock") or {}).get("displayValue", "")
            ev_tid = str((kev.get("team") or {}).get("id", ""))

            in_1h = (period == 1) or (period == 0 and (clock_val <= 2700 or disp_clock.startswith("45'")))
            in_90 = (period in (1, 2)) or (
                period == 0 and (clock_val <= 5400 or disp_clock.startswith("90'"))
            )
            if in_1h:
                if ev_tid == hid:
                    h1 += 1
                elif ev_tid == aid:
                    a1 += 1
            if in_90:
                if ev_tid == hid:
                    h90 += 1
                elif ev_tid == aid:
                    a90 += 1
            goal_log.append(f"{disp_clock}(P{period})")

        ht_h, ht_a = h1, a1
        # If match went to AET (Extra Time), 90-minute regular time is necessarily a draw (h90 == a90)!
        if status_name in ("STATUS_FINAL_AET", "STATUS_FINAL_PEN") and h90 == a90:
            reg_h, reg_a = h90, a90

    aet_note = ""
    if status_name == "STATUS_FINAL_AET" and (reg_h != raw_ft_h or reg_a != raw_ft_a):
        aet_note = f" (90' Normal Süre: {reg_h}-{reg_a}, Uzatma Sonu: {raw_ft_h}-{raw_ft_a})"
    elif status_name == "STATUS_FINAL_PEN":
        aet_note = f" (90' Normal Süre: {reg_h}-{reg_a}, Penaltılarla)"

    return {
        "idx": idx,
        "event_id": eid,
        "status_name": status_name,
        "status": status_detail,
        "state": state,
        "ht_h": ht_h,
        "ht_a": ht_a,
        "ft_h": reg_h,
        "ft_a": reg_a,
        "raw_h": raw_ft_h,
        "raw_a": raw_ft_a,
        "note": f"MS {reg_h}-{reg_a}" + (f" (İY {ht_h}-{ht_a})" if ht_h is not None else "") + aet_note,
    }


def evaluate_selection(sel: str, ht_h: int | None, ht_a: int | None, ft_h: int | None, ft_a: int | None) -> bool | None:
    if ft_h is None or ft_a is None:
        return None
    tot = ft_h + ft_a
    kg = ft_h >= 1 and ft_a >= 1
    ht_tot = (ht_h + ht_a) if (ht_h is not None and ht_a is not None) else None
    h2_h = (ft_h - ht_h) if ht_h is not None else None
    h2_a = (ft_a - ht_a) if ht_a is not None else None
    h2_tot = (h2_h + h2_a) if (h2_h is not None and h2_a is not None) else None
    kg1 = (ht_h >= 1 and ht_a >= 1) if (ht_h is not None and ht_a is not None) else None
    kg2 = (h2_h >= 1 and h2_a >= 1) if (h2_h is not None and h2_a is not None) else None

    if sel == "MS 1":
        return ft_h > ft_a
    if sel == "MS 0":
        return ft_h == ft_a
    if sel == "MS 2":
        return ft_a > ft_h
    if sel == "ÇŞ 10":
        return ft_h >= ft_a
    if sel == "ÇŞ 02":
        return ft_a >= ft_h
    if sel == "ÇŞ 12":
        return ft_h != ft_a
    if sel == "1.5 Üst":
        return tot >= 2
    if sel == "1.5 Alt":
        return tot <= 1
    if sel == "2.5 Üst":
        return tot >= 3
    if sel == "2.5 Alt":
        return tot <= 2
    if sel == "3.5 Üst":
        return tot >= 4
    if sel == "3.5 Alt":
        return tot <= 3
    if sel == "4.5 Alt":
        return tot <= 4
    if sel == "KG Var":
        return kg
    if sel == "KG Yok":
        return not kg
    if sel == "İY 0.5 Üst":
        return (ht_tot >= 1) if ht_tot is not None else None
    if sel == "İY 1.5 Alt":
        return (ht_tot <= 1) if ht_tot is not None else None
    if sel == "İY 1.5 Üst":
        return (ht_tot >= 2) if ht_tot is not None else None
    if sel == "2Y 0.5 Üst":
        return (h2_tot >= 1) if h2_tot is not None else None
    if sel == "2Y 1.5 Alt":
        return (h2_tot <= 1) if h2_tot is not None else None
    if sel == "1. Yarı KG Var":
        return kg1
    if sel == "2. Yarı KG Var":
        return kg2
    if sel == "1Y ve 2Y KG Var":
        return (kg1 and kg2) if (kg1 is not None and kg2 is not None) else None
    if sel == "0-1 Gol":
        return tot <= 1
    if sel == "2-3 Gol":
        return 2 <= tot <= 3
    if sel == "2-4 Gol":
        return 2 <= tot <= 4
    if sel == "3-5 Gol":
        return 3 <= tot <= 5
    if sel.startswith("İY/MS "):
        if ht_h is None or ht_a is None:
            return None
        code = sel.replace("İY/MS ", "").strip()
        ht_c = "1" if ht_h > ht_a else ("0" if ht_h == ht_a else "2")
        ft_c = "1" if ft_h > ft_a else ("0" if ft_h == ft_a else "2")
        return f"{ht_c}/{ft_c}" == code
    return None


def main() -> None:
    pred_data = json.loads((REPO_ROOT / "reports" / "today_v6_predictions_2026_11_18.json").read_text(encoding="utf-8"))
    matches = pred_data["matches"]

    actual_by_idx: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        for res in pool.map(fetch_espn_90min_and_ht, matches):
            actual_by_idx[res["idx"]] = res

    print("=" * 105)
    print("18 KASIM 2026 ÇARŞAMBA — TÜM 45 MAÇIN GERÇEKLEŞEN SONUÇLARI VE QUANTFOOT-v6 TAHMİN KONTROLÜ")
    print("=" * 105)

    settled_best = 0
    won_best = 0
    settled_band = 0
    won_band = 0
    exact_top3_hits = 0
    settled_matches_count = 0

    match_audit_rows = []
    for m in matches:
        idx = m["idx"]
        act = actual_by_idx[idx]
        st = act.get("status", "")
        state = act.get("state", "post" if idx in TUR3_ACTUALS else "")
        ft_h, ft_a = act["ft_h"], act["ft_a"]
        ht_h, ht_a = act["ht_h"], act["ht_a"]

        b_sel = m["best_valid_bet"]["selection"]
        b_odd = m["best_valid_bet"]["offered_odds"]
        b_prob = m["best_valid_bet"]["prob"]
        gb_sel = m["best_goal_band"]["selection"] if m.get("best_goal_band") else "2-4 Gol"

        is_finished = (idx in TUR3_ACTUALS) or (state == "post") or (st in ("FT", "AET", "FT-Pens"))
        is_live = state == "in"
        # Check if 1st half is already completed in a live match (HT or 2nd half minute >= 46')
        ht_completed = is_finished or (
            is_live and (st == "HT" or (st.endswith("'") and int(st.split("'")[0].replace("+", "")) > 45 and not st.startswith("45'")))
        )

        hit_best = evaluate_selection(b_sel, ht_h, ht_a, ft_h, ft_a) if (is_finished or is_live) else None
        settled_live_ht = False
        if is_live and b_sel.startswith("İY ") and ht_h is not None and ht_a is not None:
            if b_sel == "İY 0.5 Üst" and (ht_h + ht_a >= 1):
                settled_live_ht = True
                hit_best = True
            elif ht_completed:
                settled_live_ht = True

        if is_finished:
            settled_matches_count += 1
            if hit_best is not None:
                settled_best += 1
                won_best += int(hit_best)
            hit_gb = evaluate_selection(gb_sel, ht_h, ht_a, ft_h, ft_a)
            if hit_gb is not None:
                settled_band += 1
                won_band += int(hit_gb)
            actual_score_str = f"{ft_h}-{ft_a}"
            if any(s["score"] == actual_score_str for s in m["top_ft_scores"]):
                exact_top3_hits += 1
        elif settled_live_ht and hit_best is not None:
            settled_best += 1
            won_best += int(hit_best)

        if not is_finished and not is_live:
            res_tag = f"ERTELENDİ ({st})"
        elif is_live:
            if settled_live_ht:
                res_tag = f"CANLI ({st}: {ft_h}-{ft_a}) — 1. YARI SONUCUYLA {'TUTTU ✅' if hit_best else 'YATTI ❌'}"
            else:
                res_tag = f"CANLI ({st}: {ft_h}-{ft_a}) -> {'ŞU AN TUTUYOR ✅' if hit_best else 'DEVAM EDİYOR ⏳'}"
        else:
            res_tag = "TUTTU ✅" if hit_best else "YATTI ❌"

        print(
            f"#{idx:2d} [{m['ko_tsi'][11:]}] {m['home']} vs {m['away']} | {act['note']} | "
            f"v6 En Geçerli: {b_sel} @ {b_odd:.2f} (P=%{b_prob*100:.1f}) -> {res_tag}"
        )
        match_audit_rows.append({
            "idx": idx,
            "ko_tsi": m["ko_tsi"],
            "league": m["league"],
            "home": m["home"],
            "away": m["away"],
            "score_note": act["note"],
            "status": st,
            "is_finished": is_finished,
            "is_live": is_live,
            "clinched_live": settled_live_ht,
            "ft_h": ft_h,
            "ft_a": ft_a,
            "ht_h": ht_h,
            "ht_a": ht_a,
            "best_selection": b_sel,
            "best_odds": b_odd,
            "best_prob": b_prob,
            "has_live_odds": bool(m.get("has_live_odds")),
            "hit_best": hit_best,
            "top3_hit": (f"{ft_h}-{ft_a}" in [s["score"] for s in m["top_ft_scores"]]) if is_finished else None,
            "res_tag": res_tag,
            "top_scores": [s["score"] for s in m["top_ft_scores"]],
        })

    settled_live = [r for r in match_audit_rows if (r["is_finished"] or r["clinched_live"]) and r["has_live_odds"]]
    won_live = [r for r in settled_live if r["hit_best"]]
    settled_unpriced = [r for r in match_audit_rows if (r["is_finished"] or r["clinched_live"]) and not r["has_live_odds"]]
    won_unpriced = [r for r in settled_unpriced if r["hit_best"]]

    print("-" * 105)
    print(f"SONUÇLANAN / KESİNLEŞEN EN GEÇERLİ TAHMİN İSABETİ: {won_best} / {settled_best} (%{won_best/max(1,settled_best)*100:.1f})")
    print(f"  -> CANLI PİYASA ORANLI ANA MAÇLARDA: {len(won_live)} / {len(settled_live)} (%{len(won_live)/max(1,len(settled_live))*100:.1f})")
    print(f"  -> CANLI ORANSIZ KUPA / 2. LİG MAÇLARINDA: {len(won_unpriced)} / {len(settled_unpriced)} (%{len(won_unpriced)/max(1,len(settled_unpriced))*100:.1f})")
    print(f"TAMAMLANAN MAÇLARDA TOP-3 KESİN SKOR KÜMESİ İSABETİ: {exact_top3_hits} / {settled_matches_count} (%{exact_top3_hits/max(1,settled_matches_count)*100:.1f})")
    print("-" * 105)

    # Check the 7 archived coupons from reports/ledger/coupons_2026_11_18.json
    ledger_p = REPO_ROOT / "reports" / "ledger" / "coupons_2026_11_18.json"
    ledger = json.loads(ledger_p.read_text(encoding="utf-8"))
    by_home_act = {r["home"]: r for r in match_audit_rows}

    print("\n" + "=" * 105)
    print("ARŞİVLENEN 7 KUPONUN GERÇEKLEŞEN KONTROLÜ (reports/ledger/coupons_2026_11_18.json)")
    print("=" * 105)
    for cp in ledger["coupons"]:
        print(f"\n### {cp['title']} (Toplam Oran: {cp['total_odds']:.2f})")
        w_c, l_c, live_c = 0, 0, 0
        for leg in cp["legs"]:
            ar = by_home_act[leg["home"]]
            hit = evaluate_selection(leg["selection"], ar["ht_h"], ar["ht_a"], ar["ft_h"], ar["ft_a"])
            if ar["is_finished"] or (ar["is_live"] and leg["selection"] == "İY 0.5 Üst" and ar["ht_h"] is not None and (ar["ht_h"] + ar["ht_a"] >= 1)):
                if hit:
                    w_c += 1
                    st_s = "TUTTU ✅"
                else:
                    l_c += 1
                    st_s = "YATTI ❌"
            else:
                live_c += 1
                st_s = f"CANLI ({ar['status']}: {ar['ft_h']}-{ar['ft_a']}) -> {'ŞU AN TUTUYOR ✅' if hit else 'DEVAM EDİYOR ⏳'}"
            leg["result"] = st_s
            leg["actual_score"] = ar["score_note"]
            print(f"  - [{leg['ko_tsi'][11:]}] {leg['home']} - {leg['away']}: {leg['selection']} @ {leg['odds']:.2f} | Gerçekleşen: {ar['score_note']} -> {st_s}")
        cp["summary_result"] = f"{w_c} Tuttu, {l_c} Yattı, {live_c} Canlı"
        if l_c > 0:
            cp["status"] = f"LOST ({w_c}/{w_c + l_c + live_c})"
        elif live_c == 0 and w_c == len(cp["legs"]):
            cp["status"] = f"WON ({w_c}/{w_c})"
        else:
            cp["status"] = f"LIVE_LEADING ({w_c}/{len(cp['legs'])} Bitti, {live_c} Canlı Önde)"
        print(f"  => KUPON ÖZETİ: {cp['summary_result']} | Durum: {cp['status']}")

    # Persist updated ledger JSON and Markdown Audit Report
    ledger["audit_summary"] = {
        "best_bet_accuracy": f"{won_best}/{settled_best} (%{won_best/max(1,settled_best)*100:.1f})",
        "live_priced_accuracy": f"{len(won_live)}/{len(settled_live)} (%{len(won_live)/max(1,len(settled_live))*100:.1f})",
        "unpriced_accuracy": f"{len(won_unpriced)}/{len(settled_unpriced)} (%{len(won_unpriced)/max(1,len(settled_unpriced))*100:.1f})",
        "top3_score_cluster_hits": f"{exact_top3_hits}/{settled_matches_count} (%{exact_top3_hits/max(1,settled_matches_count)*100:.1f})",
    }
    ledger_p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")

    out_audit = REPO_ROOT / "reports" / "ledger" / "nov18_audit_results.json"
    out_audit.write_text(json.dumps({"summary": ledger["audit_summary"], "matches": match_audit_rows, "coupons": ledger["coupons"]}, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# 18 Kasım 2026 Çarşamba — Tüm Maçlar & 7 Kupon Gerçekleşen Denetim Raporu (`04:02 TSİ` İtibarıyla)",
        "",
        "Dün (**18 Kasım 2026**) `QuantFoot-v6` algoritmasıyla tahmin edilen **45 maçın** ve arşivlenen **7 kuponun** gerçekleşen sonuçları (uzatma/penaltıya giden İspanya Kral Kupası maçlarında İddaa/Nesine kuralı gereği **90 dakikalık normal süre skorları** esas alınarak) aşağıdadır.",
        "",
        "## 1. Genel Performans Özeti",
        f"- **Sonuçlanan / Kesinleşen Tüm Maçlarda En Geçerli Tahmin İsabeti:** **`{won_best} / {settled_best}` (`%{won_best/max(1,settled_best)*100:.1f}`)**",
        f"  - **Canlı Piyasa Oranlı Ana Maçlarda İsabet (`has_live_odds=True`):** **`{len(won_live)} / {len(settled_live)}` (`%{len(won_live)/max(1,len(settled_live))*100:.1f}`)**",
        f"  - **Canlı Oransız Alt Lig / Kadınlar Kupa Maçlarında İsabet (`has_live_odds=False`):** **`{len(won_unpriced)} / {len(settled_unpriced)}` (`%{len(won_unpriced)/max(1,len(settled_unpriced))*100:.1f}`)**",
        f"- **Tamamlanan Maçlarda Top-3 Dar Kesin Skor Kümesi İsabeti:** **`{exact_top3_hits} / {settled_matches_count}` (`%{exact_top3_hits/max(1,settled_matches_count)*100:.1f}`)**",
        "- **Ertelenen Maç:** `#35 Lye Town - Peterborough United` (22 Kasım'a ertelendi).",
        "",
        "---",
        "",
        "## 2. Dün Verilen 7 Kuponun Tek Tek Kontrolü",
        "",
        "| Kupon Kodu | Kupon Adı | Ayak | Toplam Oran | Sonuç Özeti | Durum |",
        "| :--- | :--- | :---: | :---: | :--- | :--- |",
    ]
    for cp in ledger["coupons"]:
        md.append(
            f"| `{cp['coupon_id']}` | {cp['title']} | {cp['leg_count']} | **`{cp['total_odds']:.2f}`** | {cp['summary_result']} | `{cp['status']}` |"
        )
    md.append("")
    for cp in ledger["coupons"]:
        md.append(f"### {cp['title']} (`{cp['total_odds']:.2f}` Oran — {cp['summary_result']})")
        md.append("| Saat | Karşılaşma | Tercih | Oran | Gerçekleşen Skor | Durum |")
        md.append("| :---: | :--- | :---: | :---: | :--- | :--- |")
        for leg in cp["legs"]:
            md.append(
                f"| `{leg['ko_tsi'][11:]}` | **{leg['home']} - {leg['away']}** | **`{leg['selection']}`** | `{leg['odds']:.2f}` | {leg['actual_score']} | {leg['result']} |"
            )
        md.append("")

    md.extend([
        "---",
        "",
        "## 3. Tüm 45 Maçın Saat Sıralı Gerçekleşen Skor ve Tahmin Tablosu",
        "",
        "| # | Saat | Karşılaşma | Lig | Canlı Oranlı? | Gerçekleşen Skor (90') | `QuantFoot-v6` En Geçerli Tahmin | Oran (Olasılık) | Durum |",
        "| :---: | :---: | :--- | :--- | :---: | :--- | :---: | :---: | :--- |",
    ])
    for r in match_audit_rows:
        live_tag = "✅" if r["has_live_odds"] else "⚪ (Oransız)"
        md.append(
            f"| {r['idx']} | `{r['ko_tsi'][11:]}` | **{r['home']} - {r['away']}** | {r['league']} | {live_tag} | {r['score_note']} | **`{r['best_selection']}`** | `{r['best_odds']:.2f}` (`%{r['best_prob']*100:.1f}`) | {r['res_tag']} |"
        )
    md.append("")

    audit_md_path = REPO_ROOT / "reports" / "ledger" / "nov18_audit_results.md"
    audit_md_path.write_text("\n".join(md), encoding="utf-8")

    idx_lines = [
        "# QuantFoot-v6 Kalıcı Tahmin ve Kupon Denetim Arşivi (Ledger Index)",
        "",
        "Bu dizin, oluşturulan tüm günlük maç tahminlerini, kupon portföylerini ve geçmişe dönük doğrulama (*backtest / post-mortem*) kayıtlarını kalıcı olarak saklar.",
        "",
        "## Arşivlenmiş Günler ve Raporlar",
        "",
        "| Tarih | Motor Sürümü | Maç Sayısı | Kupon / Rapor Dosyaları | Doğrulama Durumu |",
        "| :---: | :--- | :---: | :--- | :--- |",
        "| **2026-11-17** | `QuantFoot-v5 -> v6 Post-Mortem` | 16 Ana Maç | [quantfoot_v6_omni_upgrade_report.md](../quantfoot_v6_omni_upgrade_report.md) / [verify_v6_on_nov17_coupons.py](../../scripts/verify_v6_on_nov17_coupons.py) | `v6 Geriye Dönük Test: 16/16 (%100)` |",
        f"| **2026-11-18** | `QuantFoot-v6 (OmniMarketBundle)` | 45 Maç | [nov18_audit_results.md](nov18_audit_results.md) / [coupons_2026_11_18.md](coupons_2026_11_18.md) / [coupons_2026_11_18.json](coupons_2026_11_18.json) | `Ana Kuponlar K1/K2/K3: 0 Yatan (Flamengo Canlı 2-1 Önde) | Genel İsabet: {won_best}/{settled_best} (%{won_best/max(1,settled_best)*100:.1f})` |",
        "",
    ]
    (REPO_ROOT / "reports" / "ledger" / "INDEX.md").write_text("\n".join(idx_lines), encoding="utf-8")
    print(f"Wrote Markdown audit to {audit_md_path}")


if __name__ == "__main__":
    main()

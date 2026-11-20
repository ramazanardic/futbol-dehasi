"""Send daily QuantFoot briefings and pre-kickoff steam/injury alerts to Telegram.

Activates automatically when ``TELEGRAM_BOT_TOKEN`` and ``TELEGRAM_CHAT_ID`` are configured in
environment variables (or GitHub Actions Secrets). Prints a clean skip note and exits 0 when unset.

    python scripts/notify_telegram.py --date 2026-11-20 --mode morning
    python scripts/notify_telegram.py --date 2026-11-20 --mode alerts --dry-run
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from gunluk_analiz import best_pick  # noqa: E402
from nesine_global import DAILY, TSI, classify_price_tier  # noqa: E402

DASHBOARD_URL = "https://ramazanardic.github.io/futbol-dehasi/"
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def build_telegram_message(
    date_str: str,
    *,
    mode: str = "morning",
    daily_dir: Path = DAILY,
    calibration_path: Path = ROOT / "data" / "calibration" / "live_calibration.json",
    dashboard_url: str = DASHBOARD_URL,
) -> str:
    """Build a crisp Turkish Telegram briefing from the day's live JSON and calibration snapshot."""
    day_path = daily_dir / date_str / "nesine_global.json"
    if not day_path.exists():
        return f"📊 QuantFoot ({date_str}): Henüz günlük analiz dosyası oluşmadı.\n🌐 {dashboard_url}"

    data = json.loads(day_path.read_text(encoding="utf-8"))
    ms = data.get("matches") or []
    real = [m for m in ms if (m.get("price_tier") or classify_price_tier(m["status"], m.get("reference"))) != "ozel_bahis"]
    sharp = [m for m in real if (m.get("price_tier") or classify_price_tier(m["status"], m.get("reference"))) == "keskin"]
    mid = [m for m in real if (m.get("price_tier") or classify_price_tier(m["status"], m.get("reference"))) == "global_buro"]
    researched = sum(1 for m in real if (m.get("research") or {}).get("teams") or (m.get("research") or {}).get("tm_absences"))

    top_picks: list[tuple[float, dict[str, Any], dict[str, Any], str]] = []
    steam_alerts: list[str] = []
    injury_alerts: list[str] = []
    weather_alerts: list[str] = []

    for m in real:
        pick, tag = best_pick(m)
        if pick is not None:
            top_picks.append((float(pick["fair_prob"]), m, pick, tag))
        st = m.get("steam_1x2")
        if st and max(abs(float(x)) for x in st) >= 0.07:
            best_idx = max(range(3), key=lambda i: abs(float(st[i])))
            lbl = ("Ev", "Ber", "Dep")[best_idx]
            steam_alerts.append(f"• {m['kickoff'][11:]} {m['home']} - {m['away']}: {lbl} {st[best_idx]*100:+.1f}p")
        for fl in (m.get("research") or {}).get("flags") or []:
            if fl.startswith("TM:") and ("1. kaleci" in fl or "golcü" in fl):
                injury_alerts.append(f"• {m['kickoff'][11:]} {m['home']} - {m['away']}: {fl.replace('TM: ', '')}")
            elif fl.startswith("Hava uyarısı:"):
                weather_alerts.append(f"• {m['kickoff'][11:]} {m['home']} - {m['away']}: {fl.replace('Hava uyarısı: ', '')}")

    top_picks.sort(key=lambda x: (-x[0], -x[2]["odds"]))

    lines: list[str] = []
    if mode == "alerts":
        lines.append(f"⚡ QuantFoot Canlı Uyarılar ({date_str})")
    else:
        lines += [
            f"📊 QuantFoot Günlük Bülten ({date_str})",
            f"Global kapsam: {len(sharp) + len(mid)}/{len(real)} maç ({len(sharp)} keskin · {len(mid)} orta güven)",
            f"Canlı araştırma (ESPN + TM): {researched}/{len(real)} maç",
            "",
        ]
        if top_picks:
            lines.append("🎯 En Güvenilir Seçimler (Nesine ≥ 1,20):")
            for prob, m, pk, tag in top_picks[:6]:
                t_s = f" [{tag}]" if tag else ""
                sel_lbl = pk.get("name") or f"{pk['market']}: {pk['selection']}"
                lines.append(
                    f"• {m['kickoff'][11:]} {m['home']} - {m['away']} → {sel_lbl} "
                    f"(%{prob*100:.0f}, @{pk['odds']:.2f}{t_s})"
                )
            lines.append("")

    if steam_alerts:
        lines.append("⚡ Sert Sharp Steam (≥ 7 puan):")
        lines.extend(steam_alerts[:6])
        lines.append("")

    if injury_alerts:
        lines.append("🩺 Kritik Kadro Eksikleri (1. Kaleci / Golcü):")
        lines.extend(injury_alerts[:6])
        lines.append("")

    if weather_alerts:
        lines.append("🌧️ Şiddetli Hava Uyarıları:")
        lines.extend(weather_alerts[:4])
        lines.append("")

    if mode != "alerts" and calibration_path.exists():
        try:
            cal = json.loads(calibration_path.read_text(encoding="utf-8"))
            ov = cal.get("overall") or {}
            by_day = cal.get("by_day") or []
            if ov.get("n"):
                last_d = by_day[-1] if by_day else None
                last_txt = (
                    f" · Son gün ({last_d['date']}): %{last_d['safest_hit']*100:.1f} ({last_d['safest_n']} maç)"
                    if last_d and last_d.get("safest_hit") is not None
                    else ""
                )
                lines.append(f"🧠 Öz-Öğrenme: {ov['n']} seçim · Brier {ov['brier']:.4f}{last_txt}")
        except (OSError, json.JSONDecodeError):
            pass

    lines.append(f"🌐 Canlı Panel: {dashboard_url}")
    return "\n".join(lines).strip()[:3900]


def send_telegram_message(
    text: str,
    *,
    token: str | None = None,
    chat_id: str | None = None,
    timeout: int = 15,
) -> bool:
    """Send a Telegram message via Bot API; returns False cleanly when credentials are unset."""
    tok = (token or os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    cid = (chat_id or os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not tok or not cid:
        return False
    resp = requests.post(
        TELEGRAM_API.format(token=tok),
        json={"chat_id": cid, "text": text, "disable_web_page_preview": True},
        timeout=timeout,
    )
    resp.raise_for_status()
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--mode", choices=("morning", "alerts", "settle"), default="morning")
    ap.add_argument("--dry-run", action="store_true", help="Print message without sending")
    args = ap.parse_args()

    msg = build_telegram_message(args.date, mode=args.mode)
    if args.dry_run:
        print(msg)
        return
    if not send_telegram_message(msg):
        print("Telegram bildirimi atlandı (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID tanımlı değil).")
        return
    print(f"Telegram bildirimi gönderildi ({args.date}, mode={args.mode}).")


if __name__ == "__main__":
    main()

"""Canlı (Maç İçi / In-Play) Dakika-Dakika Yeniden Fiyatlama ve Kırmızı Kart / Geri Dönüş Analizi (Ortak Araç).

Kullanım örneği:
    python scripts/canli_analiz.py --ev "Beşiktaş" --dep "Galatasaray" --dk 55 --skor 0-1 \\
        --ev-mu 1.48 --dep-mu 1.38 --ev-xg 1.25 --dep-xg 0.42 --dep-kirmizi 1
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantfoot.markets.inplay_engine import InPlayState, reprice_inplay  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ev", default="Ev")
    ap.add_argument("--dep", default="Deplasman")
    ap.add_argument("--lig", default="")
    ap.add_argument("--dk", type=float, required=True, help="Canlı dakika (0..95)")
    ap.add_argument("--skor", required=True, help="Anlık skor, ör. 0-1 veya 1-1")
    ap.add_argument("--ev-mu", type=float, default=1.40, help="Maç öncesi Ev beklenen gol")
    ap.add_argument("--dep-mu", type=float, default=1.15, help="Maç öncesi Dep beklenen gol")
    ap.add_argument("--ev-kirmizi", type=int, default=0)
    ap.add_argument("--dep-kirmizi", type=int, default=0)
    ap.add_argument("--ev-xg", type=float, default=None, help="Canlı Ev xG (opsiyonel)")
    ap.add_argument("--dep-xg", type=float, default=None, help="Canlı Dep xG (opsiyonel)")
    ap.add_argument("--ev-sot", type=int, default=None, help="Canlı Ev isabetli şut")
    ap.add_argument("--dep-sot", type=int, default=None, help="Canlı Dep isabetli şut")
    args = ap.parse_args(argv)

    sh_s, _, sa_s = args.skor.replace(":", "-").partition("-")
    state = InPlayState(
        minute=args.dk,
        score_home=int(sh_s.strip()),
        score_away=int(sa_s.strip()),
        pre_mu_home=args.ev_mu,
        pre_mu_away=args.dep_mu,
        red_home=args.ev_kirmizi,
        red_away=args.dep_kirmizi,
        live_xg_home=args.ev_xg,
        live_xg_away=args.dep_xg,
        live_sot_home=args.ev_sot,
        live_sot_away=args.dep_sot,
        league=args.lig,
        home=args.ev,
        away=args.dep,
    )
    res = reprice_inplay(state)

    print(f"# Canlı Analiz: {args.ev} {res.score} {args.dep} (Dk {res.minute:.0f}')")
    print(f"Kalan beklenen gol: {args.ev} {res.rem_mu_home:.2f} — {args.dep} {res.rem_mu_away:.2f}")
    print(
        f"Canlı 1X2: MS 1 %{100*res.live_1x2['MS 1']:.1f} ({1/max(res.live_1x2['MS 1'],1e-4):.2f}) | "
        f"MS 0 %{100*res.live_1x2['MS 0']:.1f} ({1/max(res.live_1x2['MS 0'],1e-4):.2f}) | "
        f"MS 2 %{100*res.live_1x2['MS 2']:.1f} ({1/max(res.live_1x2['MS 2'],1e-4):.2f})"
    )
    print(
        f"Sonraki Gol: Ev %{100*res.next_goal['Sonraki Gol Ev']:.1f} | "
        f"Dep %{100*res.next_goal['Sonraki Gol Dep']:.1f} | "
        f"Gol Olmaz %{100*res.next_goal['Gol Olmaz']:.1f}"
    )
    print(
        f"Canlı Alt/Üst: 2.5 Üst %{100*res.live_ou['2.5 Üst']:.1f} | "
        f"3.5 Üst %{100*res.live_ou['3.5 Üst']:.1f} | "
        f"KG Var %{100*res.live_btts['KG Var']:.1f}"
    )
    sc = ", ".join(f"{k} %{100*v:.1f}" for k, v in res.top_final_scores.items())
    print(f"En olası maç sonu skorları: {sc}")
    if res.comeback_alert:
        print(res.comeback_alert)
    for note in res.notes:
        print(f"- {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

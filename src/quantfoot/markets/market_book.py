"""One call that prices all 20 market families for a match.

    book = build_market_book(1.7, 1.1, league="eng.1", division="E0",
                             corners=(6.0, 4.2), yellows=(1.7, 1.9),
                             players=[PlayerProfile("Kane", "Ev", goal_share=0.35)])
    book["4. Alt/Üst"]["2.5 Üst"]          # probability
    book["9. Asya Handikabı"]["Ev -0.25"]   # Outcome (win / half-win / push / ...)

Families 1-14 and the goal part of 20 come from the coherent joint goal tensor
(`goal_markets`), 15 from `goal_timing`, 16-17 from `player_markets`, 18-19 from
`corners_cards`.  Same-game combinations of any legs: `bet_builder.price_bet_builder`.
"""

from __future__ import annotations

from typing import Any

from quantfoot.markets.corners_cards import CardDistribution, CornerDistribution, league_baseline
from quantfoot.markets.goal_markets import price_asian_markets, price_goal_markets
from quantfoot.markets.goal_timing import GoalTimingModel
from quantfoot.markets.omni_markets import OmniMarketBundle, compute_omni_markets
from quantfoot.markets.player_markets import PlayerProfile, price_player_markets


def build_market_book(
    mu_home: float,
    mu_away: float,
    league: str | None = None,
    division: str | None = None,
    corners: tuple[float, float] | None = None,
    yellows: tuple[float, float] | None = None,
    reds: tuple[float, float] | None = None,
    players: list[PlayerProfile] | None = None,
    bundle: OmniMarketBundle | None = None,
) -> dict[str, Any]:
    """Price every market family. `league` selects goal regimes, `division` corner/card baselines."""
    bundle = bundle or compute_omni_markets(mu_home, mu_away, league=league)
    joint = bundle.joint
    goals = price_goal_markets(joint)
    asian = price_asian_markets(joint)
    timing = GoalTimingModel.from_joint(joint)
    t_mk = timing.markets()

    base = league_baseline(division)
    c_h, c_a = corners if corners is not None else (base[0], base[1])
    corner_dist = CornerDistribution.from_expectations(c_h, c_a, division)
    y_h, y_a = yellows if yellows is not None else (base[4], base[5])
    r_h, r_a = reds if reds is not None else (base[7] * y_h / base[4], base[8] * y_a / base[5])
    card_dist = CardDistribution.from_expectations(y_h, y_a, r_h, r_a, base[6])
    card_factor = (y_h + y_a) / (base[4] + base[5])

    first_half = {k: v for k, v in goals["İlk Yarı"].items()}
    book: dict[str, Any] = {
        "1. Maç Sonucu": goals["Maç Sonucu"],
        "2. Çifte Şans": goals["Çifte Şans"],
        "3. Beraberlikte İade": asian["Beraberlikte İade"],
        "4. Alt/Üst": goals["Alt/Üst"],
        "5. Toplam Gol Aralığı": goals["Toplam Gol Aralığı"],
        "6. Tek/Çift": goals["Tek/Çift"],
        "7. Karşılıklı Gol": goals["Karşılıklı Gol"],
        "8. Avrupa Handikabı": goals["Avrupa Handikabı"],
        "9. Asya Handikabı": asian["Asya Handikabı"],
        "9b. Asya Alt/Üst": asian["Asya Alt/Üst"],
        "10. Doğru Skor": goals["Doğru Skor"],
        "11. İlk Yarı": first_half,
        "12. İkinci Yarı": goals["İkinci Yarı"],
        "13. İY/MS": goals["İY/MS"],
        "14. Takım Golleri": goals["Takım Golleri"],
        "15. Gol Zamanı": {**t_mk["İlk Golü Atan Takım"], **t_mk["Son Golü Atan Takım"], **t_mk["İlk Gol Dakikası"],
                           **t_mk["Son Gol Dakikası"], **t_mk["Gol Dakikası Aralığı"], **goals["En Çok Gol Olan Yarı"]},
        "18. Korner": {k: v for fam in corner_dist.markets().values() for k, v in fam.items()},
        "19. Kart": {k: v for fam in card_dist.markets().values() for k, v in fam.items()},
        "20. Kombine": goals["Kombine"],
    }
    if players:
        pm = price_player_markets(joint, players, timing, card_factor=card_factor)
        goal_props = ("Gol Atar", "2+ Gol", "Hat-trick", "İlk Golü Atar", "Son Golü Atar")
        book["16. Golcü"] = {f"{n}: {k}": v for n, row in pm.items() for k, v in row.items() if k in goal_props}
        book["17. Oyuncu Özel"] = {f"{n}: {k}": v for n, row in pm.items() for k, v in row.items() if k not in goal_props}
        if any(pl.yellow_p90 > 0 for pl in players):
            book["19. Kart"].update({f"{n}: Kart Görür": row["Kart Görür"] for n, row in pm.items() if "Kart Görür" in row})
    book["_modeller"] = {"joint": joint, "timing": timing, "corners": corner_dist, "cards": card_dist}
    return book

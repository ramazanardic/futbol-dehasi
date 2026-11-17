"""Publication-grade analytics plots for model validation, calibration, and equity curves."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def generate_backtest_charts(
    wf_result: dict[str, object],
    pin_result: dict[str, object],
    output_dir: Path,
) -> list[Path]:
    """Render model comparison, reliability diagram, odds-bias, and Kelly equity curves."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    plt.style.use("seaborn-v0_8-whitegrid")

    # 1. Model Proper Scoring Rules (RPS & Log-Loss)
    scores = wf_result["model_scores"]
    names = list(scores.keys())
    rps_vals = [scores[k]["rps"] for k in names]
    ll_vals = [scores[k]["log_loss"] for k in names]

    fig, axes = plt.subplots(1, 2, figsize=(13.8, 6.2))
    y_pos = np.arange(len(names))
    colors = [
        "#4f81bd" if ("Market" not in n and "Calibrated" not in n) else ("#2ca02c" if "Calibrated" in n else "#d95f02")
        for n in names
    ]

    axes[0].barh(y_pos, rps_vals, color=colors)
    axes[0].set_yticks(y_pos, names, fontsize=9)
    axes[0].invert_yaxis()
    axes[0].set_xlim(min(rps_vals) * 0.985, max(rps_vals) * 1.005)
    axes[0].set_title("Ranked Probability Score (RPS, Lower is Better)")
    axes[0].set_xlabel("Out-of-Sample RPS")

    axes[1].barh(y_pos, ll_vals, color=colors)
    axes[1].set_yticks(y_pos, [""] * len(names))
    axes[1].invert_yaxis()
    axes[1].set_xlim(min(ll_vals) * 0.985, max(ll_vals) * 1.005)
    axes[1].set_title("Multi-Class Log-Loss (Lower is Better)")
    axes[1].set_xlabel("Out-of-Sample Log-Loss")

    fig.suptitle(f"Walk-Forward Out-of-Sample Evaluation (n={wf_result['n_test']:,} Matches)", fontsize=12, fontweight="bold")
    fig.tight_layout()
    p1 = out / "model_benchmark.png"
    fig.savefig(p1, dpi=160)
    plt.close(fig)
    generated.append(p1)

    # 2. Reliability Diagram (Calibration Curve for Home Win)
    y_test = wf_result["y_test"]
    y_home = (y_test == 0).astype(float)
    p_raw = wf_result["components"]["raw_ensemble"][:, 0]
    p_cal = wf_result["components"]["calibrated_ensemble"][:, 0]
    p_mkt = wf_result["p_b365_devig"][:, 0]

    fig, ax = plt.subplots(figsize=(6.8, 5.8))
    ax.plot([0, 1], [0, 1], "k--", lw=1.2, label="Perfect Calibration")
    bins = np.linspace(0.05, 0.90, 11)
    for label, preds, col, marker in [
        ("Raw Fundamental Ensemble", p_raw, "#e67e22", "s"),
        ("Calibrated Fundamental Ensemble", p_cal, "#2ca02c", "o"),
        ("Market Power-Devigged", p_mkt, "#1f77b4", "^"),
    ]:
        xs, ys = [], []
        for i in range(len(bins) - 1):
            m = (preds >= bins[i]) & (preds < bins[i + 1])
            if np.sum(m) >= 25:
                xs.append(float(np.mean(preds[m])))
                ys.append(float(np.mean(y_home[m])))
        ax.plot(xs, ys, marker=marker, lw=2, color=col, label=label)

    ax.set_title("Probability Calibration (Home Win Reliability Diagram)")
    ax.set_xlabel("Predicted Probability")
    ax.set_ylabel("Empirical Win Frequency")
    ax.legend(frameon=True)
    fig.tight_layout()
    p2 = out / "calibration_reliability.png"
    fig.savefig(p2, dpi=160)
    plt.close(fig)
    generated.append(p2)

    # 3. Fractional Kelly Equity Curves (Sharp Market & Pinnacle vs Soft)
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
    for name, strat in wf_result["strategies"].items():
        if "Pure Fundamental" in name:
            continue
        curve = strat["kelly"]["curve"]
        roi = strat["metrics"]["roi"] * 100.0
        axes[0].plot(curve, lw=1.8, label=f"{name}\nROI={roi:+.2f}%, MaxDD={strat['kelly']['max_drawdown_pct']:.1f}%")
    axes[0].axhline(1000.0, color="gray", ls="--", lw=1)
    axes[0].set_title("2021-2026 Club Leagues: Quarter-Kelly Equity ($1,000 Base)")
    axes[0].set_xlabel("Bet Number")
    axes[0].set_ylabel("Bankroll ($)")
    axes[0].legend(fontsize=8)

    pin_open_curve = pin_result["pin_open_vs_soft"]["kelly"]["curve"]
    pin_open_roi = pin_result["pin_open_vs_soft"]["metrics"]["roi"] * 100.0
    axes[1].plot(
        pin_open_curve,
        color="#1f77b4",
        lw=1.7,
        alpha=0.85,
        label=f"Pin Open Power vs Soft\nROI={pin_open_roi:+.2f}%, CLV={pin_result['mean_closing_ev_clv_pct']:+.2f}%, MaxDD={pin_result['pin_open_vs_soft']['kelly']['max_drawdown_pct']:.1f}%",
    )
    if "pin_open_wf_clv" in pin_result:
        clv_st = pin_result["pin_open_wf_clv"]
        clv_roi = clv_st["metrics"]["roi"] * 100.0
        axes[1].plot(
            clv_st["kelly"]["curve"],
            color="#2ca02c",
            lw=2.1,
            label=f"WF CLV-ML Filter (P>=0.70, O<=3.5)\nROI={clv_roi:+.2f}%, CLV={pin_result.get('wf_clv_ml_pct', 0.0):+.2f}%, MaxDD={clv_st['kelly']['max_drawdown_pct']:.1f}%",
        )
    axes[1].axhline(1000.0, color="gray", ls="--", lw=1)
    axes[1].set_title("2026 Pinnacle Open vs Best Soft Book (Quarter-Kelly)")
    axes[1].set_xlabel("Bet Number")
    axes[1].set_ylabel("Bankroll ($)")
    axes[1].legend(fontsize=8)

    fig.tight_layout()
    p3 = out / "equity_curves.png"
    fig.savefig(p3, dpi=160)
    plt.close(fig)
    generated.append(p3)

    # 4. Favorite-Longshot Bias Across Odds Buckets
    test_df = wf_result["test_df"]
    b365_o = test_df[["OddHome", "OddDraw", "OddAway"]].to_numpy(dtype=float).ravel()
    max_o = test_df[["MaxHome", "MaxDraw", "MaxAway"]].to_numpy(dtype=float).ravel()
    y_oh = np.column_stack([y_test == 0, y_test == 1, y_test == 2]).ravel()

    buckets = [(1.10, 1.50), (1.50, 2.00), (2.00, 2.75), (2.75, 4.00), (4.00, 8.00)]
    labels = [f"[{lo:.2f}, {hi:.2f})" for lo, hi in buckets]
    roi_b365, roi_max = [], []
    for lo, hi in buckets:
        m = (b365_o >= lo) & (b365_o < hi)
        roi_b365.append(float(np.mean(np.where(y_oh[m], b365_o[m] - 1.0, -1.0)) * 100.0))
        roi_max.append(float(np.mean(np.where(y_oh[m], max_o[m] - 1.0, -1.0)) * 100.0))

    x = np.arange(len(buckets))
    w = 0.36
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.bar(x - w / 2, roi_b365, width=w, color="#d95f02", label="Bet365 Single Book")
    ax.bar(x + w / 2, roi_max, width=w, color="#1b9e77", label="Best-of-Market (MaxBook)")
    ax.axhline(0.0, color="black", lw=1)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Flat-Stake ROI (%)")
    ax.set_xlabel("Decimal Odds Bucket")
    ax.set_title("Empirical Favorite-Longshot Bias & Line-Shopping Impact (2021-2026)")
    ax.legend()
    fig.tight_layout()
    p4 = out / "odds_bucket_bias.png"
    fig.savefig(p4, dpi=160)
    plt.close(fig)
    generated.append(p4)

    return generated

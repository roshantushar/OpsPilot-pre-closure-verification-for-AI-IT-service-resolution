"""A1 - token growth: Input(T) = B*T + D*T(T-1)/2 ~ B*T + 1/2 D T^2. Fit B, D per config from traces."""
from __future__ import annotations

import numpy as np

from common import master, need, savefig, trace


def fit(df):
    """Least squares on cumulative input tokens per run: y = B*T + D*T(T-1)/2."""
    X, y = [], []
    for rid in df.run_id:
        cum = 0
        for ev in [e for e in trace(rid) if e.get("event") == "llm"]:
            cum += ev.get("input_tokens", 0)
            T = ev["turn"]
            X.append([T, T * (T - 1) / 2])
            y.append(cum)
    if len(y) < 3:
        return None
    (B, D), *_ = np.linalg.lstsq(np.array(X), np.array(y), rcond=None)
    return {"B": float(B), "D": float(D), "n_points": len(y)}


def main():
    df = master()
    df = df[(df.backend == "live") & (df.verifier == "agent")] if len(df) else df
    if not need(df, "live agent runs"):
        return
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 4))
    for (exp, arm), g in df.groupby(["experiment_id", "arm"]):
        f = fit(g)
        if f:
            T = np.arange(1, 13)
            ax.plot(T, f["B"] * T + f["D"] * T * (T - 1) / 2, label=f"{exp}/{arm} B={f['B']:.0f} D={f['D']:.0f}")
            print(f"  {exp}/{arm}: {f}")
    ax.set(xlabel="turns T", ylabel="cumulative input tokens", title="A1 token growth")
    ax.legend(fontsize=6)
    print("  ->", savefig(fig, "a1_token_growth", "d6"))


if __name__ == "__main__":
    main()

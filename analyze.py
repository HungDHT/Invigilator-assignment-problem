"""
IAP — Phase 4: Tuning and Analysis
==================================
Sweeps lambda configurations, compares each against the baseline schedule,
and emits:
    tuning_results.csv     — per-configuration metrics table
    figs/workload.png      — baseline vs solver workload distribution
    figs/pareto.png        — travel vs fairness across configurations
    figs/sensitivity.png   — how metrics shift as lambda_travel sweeps
"""

from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from solver import (
    load_instance, build_model, solve_model,
    extract_solution, compute_metrics,
)

HERE = Path(__file__).parent
INSTANCE = HERE / "iap_data.json"
RESULTS_CSV = HERE / "tuning_results.csv"
FIGS_DIR = HERE / "figs"


# ---------- Weight configurations ----------
# Named extremes for the Pareto picture
NAMED_CONFIGS = [
    ("default",        {"travel": 1.0,  "fatigue": 5.0,  "fairness": 1.0}),
    ("balanced",       {"travel": 1.0,  "fatigue": 1.0,  "fairness": 1.0}),
    ("travel_heavy",   {"travel": 10.0, "fatigue": 1.0,  "fairness": 1.0}),
    ("fatigue_heavy",  {"travel": 1.0,  "fatigue": 50.0, "fairness": 1.0}),
    ("fairness_heavy", {"travel": 1.0,  "fatigue": 1.0,  "fairness": 10.0}),
]

# lambda_travel sweep (others held at the default's values)
TRAVEL_SWEEP_LAMBDAS = [0.0, 0.5, 2.0, 5.0]
TRAVEL_SWEEP = [
    (f"sweep_t_{lam}", {"travel": lam, "fatigue": 5.0, "fairness": 1.0})
    for lam in TRAVEL_SWEEP_LAMBDAS
]


# ---------- Baseline metrics ----------
def compute_baseline_metrics(inst: dict) -> dict:
    """Apply the same objective decomposition to the manual schedule."""
    shifts = inst["shifts"]
    invigilators = inst["invigilators"]
    d_ij = inst["d_ij"]
    E_b = [tuple(p) for p in inst["E_b"]]
    W_bar = inst["W_bar"]
    baseline = inst["baseline"]

    # Z_travel
    z_travel = 0.0
    for sid, invs in baseline.items():
        for cb in invs:
            z_travel += d_ij.get(sid, {}).get(cb, 0)

    # Z_fatigue
    inv_shifts = defaultdict(set)
    for sid, invs in baseline.items():
        for cb in invs:
            inv_shifts[cb].add(sid)
    z_fatigue = 0
    for (i1, i2) in E_b:
        for cb in invigilators:
            if i1 in inv_shifts[cb] and i2 in inv_shifts[cb]:
                z_fatigue += 1

    # Z_fairness: L1 deviation from W_bar
    workload = defaultdict(float)
    count = defaultdict(int)
    for sid, invs in baseline.items():
        mu = shifts[sid]["mu"]
        for cb in invs:
            workload[cb] += mu
            count[cb] += 1
    z_fairness = sum(abs(workload[cb] - W_bar) for cb in invigilators)

    return {
        "name": "BASELINE",
        "lambda_travel": None,
        "lambda_fatigue": None,
        "lambda_fairness": None,
        "z_travel": z_travel,
        "z_fatigue": z_fatigue,
        "z_fairness": z_fairness,
        "workload_count": dict(count),
        "weighted_workload": dict(workload),
        "solve_time_sec": 0.0,
    }


# ---------- Solver run ----------
def run_config(inst: dict, name: str, weights: dict) -> dict:
    model, x, y, am, ap = build_model(inst, weights)
    status, solve_time = solve_model(model)
    if status != "Optimal":
        print(f"  ! {name}: status={status}, skipping")
        return None
    assignment = extract_solution(x, inst["shifts"], inst["invigilators"])
    am_vals = {j: am[j].value() for j in inst["invigilators"]}
    ap_vals = {j: ap[j].value() for j in inst["invigilators"]}
    metrics = compute_metrics(assignment, am_vals, ap_vals, inst)
    return {
        "name": name,
        "lambda_travel": weights["travel"],
        "lambda_fatigue": weights["fatigue"],
        "lambda_fairness": weights["fairness"],
        "z_travel": metrics["z_travel"],
        "z_fatigue": metrics["z_fatigue"],
        "z_fairness": metrics["z_fairness"],
        "workload_count": metrics["count"],
        "weighted_workload": metrics["workload"],
        "solve_time_sec": solve_time,
    }


# ---------- Plots ----------
def plot_workload_comparison(baseline: dict, default: dict, path: Path):
    invs = sorted(baseline["workload_count"].keys(),
                  key=lambda j: -baseline["workload_count"][j])
    base_counts = [baseline["workload_count"][j] for j in invs]
    sol_counts = [default["workload_count"].get(j, 0) for j in invs]

    fig, ax = plt.subplots(figsize=(13, 5))
    x = range(len(invs))
    ax.bar(x, base_counts, label="Baseline (manual)",
           alpha=0.65, color="#999999", width=0.85)
    ax.bar(x, sol_counts, label="Solver (ILP)",
           alpha=0.75, color="#2a7ae2", width=0.55)
    ax.axhline(y=baseline["workload_count"][invs[0]] * 0 + 10.5,
               color="red", linestyle="--", alpha=0.5, label="Target ≈ 10.5")
    ax.set_xlabel("Invigilator (sorted by baseline load, descending)")
    ax.set_ylabel("Number of shifts")
    ax.set_title("Workload distribution: Baseline vs Solver")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def plot_pareto(results: list, path: Path):
    fig, ax = plt.subplots(figsize=(10, 6))
    palette = {
        "BASELINE": "#d62728",
        "default": "#2a7ae2",
        "balanced": "#7f7f7f",
        "travel_heavy": "#1f77b4",
        "fatigue_heavy": "#9467bd",
        "fairness_heavy": "#2ca02c",
    }
    for r in results:
        color = palette.get(r["name"], "#888888")
        marker = "X" if r["name"] == "BASELINE" else "o"
        size = 160 if r["name"] == "BASELINE" else 80
        ax.scatter(r["z_travel"], r["z_fairness"],
                   s=size, c=color, marker=marker,
                   edgecolors="white", linewidths=1, zorder=3)
        ax.annotate(r["name"], (r["z_travel"], r["z_fairness"]),
                    fontsize=9, alpha=0.8, xytext=(7, 7),
                    textcoords="offset points")
    ax.set_xlabel("Travel cost  $Z_{\\mathrm{travel}}$")
    ax.set_ylabel("Workload deviation  $Z_{\\mathrm{fairness}}$")
    ax.set_title("Trade-off across weight configurations")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def plot_sensitivity(results: list, path: Path):
    sweep = []
    for r in results:
        if r["name"] == "default":
            sweep.append((1.0, r))
        elif r["name"].startswith("sweep_t_"):
            lam = float(r["name"][len("sweep_t_"):])
            sweep.append((lam, r))
    sweep.sort(key=lambda p: p[0])

    lambdas = [p[0] for p in sweep]
    travels = [p[1]["z_travel"] for p in sweep]
    fairnesses = [p[1]["z_fairness"] for p in sweep]
    fatigues = [p[1]["z_fatigue"] for p in sweep]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    axes[0].plot(lambdas, travels, "o-", color="#2a7ae2", linewidth=2, markersize=8)
    axes[0].set_xlabel("$\\lambda_{\\mathrm{travel}}$")
    axes[0].set_ylabel("$Z_{\\mathrm{travel}}$")
    axes[0].set_title("Travel cost")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(lambdas, fairnesses, "o-", color="#e2552a", linewidth=2, markersize=8)
    axes[1].set_xlabel("$\\lambda_{\\mathrm{travel}}$")
    axes[1].set_ylabel("$Z_{\\mathrm{fairness}}$")
    axes[1].set_title("Fairness deviation")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(lambdas, fatigues, "o-", color="#9467bd", linewidth=2, markersize=8)
    axes[2].set_xlabel("$\\lambda_{\\mathrm{travel}}$")
    axes[2].set_ylabel("$Z_{\\mathrm{fatigue}}$")
    axes[2].set_title("Fatigue events")
    axes[2].grid(True, alpha=0.3)

    fig.suptitle("Sensitivity to $\\lambda_{\\mathrm{travel}}$ "
                 "(others held at $\\lambda_{\\mathrm{fatigue}}=5,\\ \\lambda_{\\mathrm{fairness}}=1$)",
                 y=1.02)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()


# ---------- Main ----------
def main():
    print("Loading instance...")
    inst = load_instance(INSTANCE)
    print(f"  |E|={len(inst['shifts'])}, |S|={len(inst['invigilators'])}, "
          f"W̄={inst['W_bar']:.3f}")

    print("\nComputing baseline metrics...")
    baseline = compute_baseline_metrics(inst)
    print(f"  BASELINE: Z_travel={baseline['z_travel']:.2f}, "
          f"Z_fatigue={baseline['z_fatigue']}, "
          f"Z_fairness={baseline['z_fairness']:.4f}")

    print("\nRunning solver configurations...")
    results = [baseline]
    for name, weights in NAMED_CONFIGS + TRAVEL_SWEEP:
        print(f"  {name}: λ={weights}")
        r = run_config(inst, name, weights)
        if r:
            print(f"    → Z_travel={r['z_travel']:7.2f}  "
                  f"Z_fatigue={r['z_fatigue']:>4.0f}  "
                  f"Z_fairness={r['z_fairness']:6.3f}  "
                  f"time={r['solve_time_sec']:.1f}s")
            results.append(r)

    # Save tabular summary (drop nested dicts for CSV)
    summary = []
    for r in results:
        row = {k: v for k, v in r.items() if not isinstance(v, dict)}
        counts = list(r["workload_count"].values())
        row["workload_min"] = min(counts) if counts else 0
        row["workload_max"] = max(counts) if counts else 0
        row["workload_range"] = row["workload_max"] - row["workload_min"]
        row["workload_std"] = pd.Series(counts).std() if counts else 0
        summary.append(row)
    df = pd.DataFrame(summary)
    df.to_csv(RESULTS_CSV, index=False)
    print(f"\n✓ {RESULTS_CSV}")

    # Plots
    FIGS_DIR.mkdir(exist_ok=True)
    default_result = next(r for r in results if r["name"] == "default")
    plot_workload_comparison(baseline, default_result, FIGS_DIR / "workload.png")
    print(f"✓ {FIGS_DIR/'workload.png'}")
    plot_pareto(results, FIGS_DIR / "pareto.png")
    print(f"✓ {FIGS_DIR/'pareto.png'}")
    plot_sensitivity(results, FIGS_DIR / "sensitivity.png")
    print(f"✓ {FIGS_DIR/'sensitivity.png'}")


if __name__ == "__main__":
    main()

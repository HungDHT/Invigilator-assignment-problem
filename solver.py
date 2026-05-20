"""
IAP — Phase 3: ILP Solver
=========================
Reads iap_data.json (from Phase 2), builds the ILP model with PuLP/CBC,
solves it, verifies feasibility, and exports a baseline-compatible CSV.

Outputs:
    solution.csv     — optimized assignment in the original schema
    solver_log.json  — diagnostics (status, objective, breakdown, times)
"""

import json
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pulp


# ---------- Configuration ----------
HERE = Path(__file__).parent
INPUT_JSON = HERE / "iap_data.json"
ORIGINAL_CSV = HERE / "Dataset_Anonymized_Invigilator_Assignment_Problem.csv"
OUTPUT_CSV = HERE / "solution.csv"
OUTPUT_LOG = HERE / "solver_log.json"

# Initial weights (will be tuned in Phase 4)
LAMBDAS = {"travel": 1.0, "fatigue": 5.0, "fairness": 1.0}


# ---------- Step 1: Load instance ----------
def load_instance(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------- Step 2: Build the ILP model ----------
def build_model(inst: dict, lambdas: dict):
    shifts = inst["shifts"]
    invigilators = inst["invigilators"]
    E_d = inst["E_d"]
    E_b = [tuple(pair) for pair in inst["E_b"]]
    d_ij = inst["d_ij"]
    W_bar = inst["W_bar"]
    daily_cap = inst["config"]["daily_cap"]

    model = pulp.LpProblem("IAP", pulp.LpMinimize)

    # ----- Decision variables -----
    # Primary: x[i,j] = 1 iff invigilator j assigned to shift i
    x = {
        (i, j): pulp.LpVariable(f"x_{i}_{j}", cat="Binary")
        for i in shifts for j in invigilators
    }

    # Fatigue auxiliary: y[(i,i'),j] = 1 iff j does both back-to-back shifts
    y = {
        (i1, i2, j): pulp.LpVariable(f"y_{i1}_{i2}_{j}", cat="Binary")
        for (i1, i2) in E_b for j in invigilators
    }

    # Workload deviation: alpha_minus, alpha_plus continuous >= 0
    am = {j: pulp.LpVariable(f"am_{j}", lowBound=0) for j in invigilators}
    ap = {j: pulp.LpVariable(f"ap_{j}", lowBound=0) for j in invigilators}

    # ----- Hard constraints -----
    # (H1) Coverage: exactly P_i invigilators per shift
    for i, s in shifts.items():
        model += (
            pulp.lpSum(x[i, j] for j in invigilators) == s["P"],
            f"H1_cover_{i}",
        )

    # (H2) Daily cap: at most k shifts per invigilator per day
    for d, shifts_on_d in E_d.items():
        for j in invigilators:
            model += (
                pulp.lpSum(x[i, j] for i in shifts_on_d) <= daily_cap,
                f"H2_day_{d}_{j}",
            )

    # ----- Soft-constraint links -----
    # (S2) Fatigue linearization: y >= x_i + x_i' - 1
    for (i1, i2) in E_b:
        for j in invigilators:
            model += (
                y[i1, i2, j] >= x[i1, j] + x[i2, j] - 1,
                f"S2_b2b_{i1}_{i2}_{j}",
            )

    # (S3) Workload goal: sum(mu * x) + am - ap == W_bar
    for j in invigilators:
        model += (
            pulp.lpSum(shifts[i]["mu"] * x[i, j] for i in shifts)
            + am[j] - ap[j] == W_bar,
            f"S3_goal_{j}",
        )

    # ----- Objective -----
    Z_travel = pulp.lpSum(
        d_ij.get(i, {}).get(j, 0) * x[i, j]
        for i in shifts for j in invigilators
    )
    Z_fatigue = pulp.lpSum(y[i1, i2, j] for (i1, i2) in E_b for j in invigilators)
    Z_fairness = pulp.lpSum(am[j] + ap[j] for j in invigilators)

    model += (
        lambdas["travel"] * Z_travel
        + lambdas["fatigue"] * Z_fatigue
        + lambdas["fairness"] * Z_fairness
    )

    return model, x, y, am, ap


# ---------- Step 3: Solve ----------
def solve_model(model: pulp.LpProblem) -> tuple[str, float]:
    # gapRel=0.05: accept any integer solution within 5% of LP lower bound.
    # The fatigue linearization is structurally loose in LP, so chasing
    # provable optimality wastes time. Empirically, the same-quality
    # incumbent is found within ~7s; tight-gap proof takes ~60s.
    solver = pulp.PULP_CBC_CMD(msg=False, gapRel=0.05, timeLimit=60)
    t0 = time.time()
    status = model.solve(solver)
    elapsed = time.time() - t0
    return pulp.LpStatus[status], elapsed


# ---------- Step 4: Extract solution ----------
def extract_solution(x: dict, shifts: dict, invigilators: list) -> dict:
    assignment = defaultdict(list)
    for i in shifts:
        for j in invigilators:
            if pulp.value(x[i, j]) > 0.5:
                assignment[i].append(j)
    return dict(assignment)


# ---------- Step 5: Verify hard constraints ----------
def verify_hard_constraints(assignment: dict, inst: dict) -> list:
    issues = []
    shifts = inst["shifts"]
    daily_cap = inst["config"]["daily_cap"]

    # H1 — coverage
    for i, s in shifts.items():
        got = len(assignment.get(i, []))
        if got != s["P"]:
            issues.append(f"H1: shift {i} got {got} invigilators, needs {s['P']}")

    # H2 — daily cap
    per_day = defaultdict(lambda: defaultdict(int))
    for i, invs in assignment.items():
        d = shifts[i]["date"]
        for j in invs:
            per_day[j][d] += 1
    for j, days in per_day.items():
        for d, c in days.items():
            if c > daily_cap:
                issues.append(f"H2: {j} has {c} shifts on {d} (cap={daily_cap})")

    return issues


# ---------- Step 6: Compute metrics ----------
def compute_metrics(assignment: dict, am_vals: dict, ap_vals: dict, inst: dict) -> dict:
    shifts = inst["shifts"]
    invigilators = inst["invigilators"]
    d_ij = inst["d_ij"]
    E_b = [tuple(p) for p in inst["E_b"]]

    # Z_travel
    z_travel = 0.0
    for i, invs in assignment.items():
        for j in invs:
            z_travel += d_ij.get(i, {}).get(j, 0)

    # Z_fatigue — count realized back-to-back occurrences
    inv_shifts = defaultdict(set)
    for i, invs in assignment.items():
        for j in invs:
            inv_shifts[j].add(i)
    z_fatigue = 0
    for (i1, i2) in E_b:
        for j in invigilators:
            if i1 in inv_shifts[j] and i2 in inv_shifts[j]:
                z_fatigue += 1

    # Z_fairness — sum of deviations
    z_fairness = sum(am_vals[j] + ap_vals[j] for j in invigilators)

    # Per-staff weighted workload and raw count
    workload = defaultdict(float)
    count = defaultdict(int)
    for i, invs in assignment.items():
        mu_i = shifts[i]["mu"]
        for j in invs:
            workload[j] += mu_i
            count[j] += 1

    return {
        "z_travel": z_travel,
        "z_fatigue": z_fatigue,
        "z_fairness": z_fairness,
        "workload": dict(workload),
        "count": dict(count),
    }


# ---------- Step 7: Export solution to CSV ----------
def export_solution(assignment: dict, inst: dict, original_csv: str, output_csv: str):
    """
    Mirror the original dataset's columns. Since we treat all three roles
    (CBCT, Thư ký, Trưởng HĐ) as one, we standardize Nhiệm vụ to the
    campus-prefixed CBCT code for every row.
    """
    df_orig = pd.read_csv(original_csv)

    # Build per-shift metadata from the first occurrence in the original
    meta = {}
    for _, row in df_orig.iterrows():
        sid = row["MS Ca thi"]
        if sid not in meta:
            meta[sid] = {
                "Ca thi": row["Ca thi"],
                "Ngày": row["Ngày"],
                "GIỜ": row["GIỜ"],
                "Thời gian": row["Thời gian"],
            }

    shifts = inst["shifts"]
    rows = []
    for sid in sorted(assignment.keys()):
        m = meta[sid]
        # Reconstruct from preprocessed data (post-imputation) for Thứ / Cơ sở
        co_so = "Cơ sở 1" if shifts[sid]["campus"] == "CS1" else "Cơ sở 2"
        prefix = "LTK" if shifts[sid]["campus"] == "CS1" else "DiAn"
        nv = f"{prefix}_CBCT"
        for j in sorted(assignment[sid]):
            rows.append({
                "Ca thi": m["Ca thi"],
                "Ngày": m["Ngày"],
                "GIỜ": m["GIỜ"],
                "MS Ca thi": sid,
                "Nhiệm vụ": nv,
                "MS của CÁN BỘ COI THI": j,
                "Thời gian": m["Thời gian"],
                "Thứ": shifts[sid]["weekday"],
                "Cơ sở": co_so,
            })

    df_out = pd.DataFrame(rows)
    df_out.to_csv(output_csv, index=False)


# ---------- Main ----------
def main():
    print("[1/6] Loading instance...")
    inst = load_instance(INPUT_JSON)
    print(f"      |E|={len(inst['shifts'])}, |S|={len(inst['invigilators'])}, "
          f"|E_b|={len(inst['E_b'])}, W̄={inst['W_bar']:.3f}")

    print("[2/6] Building model...")
    t0 = time.time()
    model, x, y, am, ap = build_model(inst, LAMBDAS)
    n_vars = len(model.variables())
    n_cons = len(model.constraints)
    print(f"      {n_vars} variables, {n_cons} constraints "
          f"(built in {time.time() - t0:.2f}s)")

    print("[3/6] Solving...")
    status, solve_time = solve_model(model)
    print(f"      status: {status}, solve time: {solve_time:.2f}s")
    print(f"      Z* = {pulp.value(model.objective):.4f}")

    if status != "Optimal":
        print(f"      ! Solver did not return Optimal. Aborting.")
        return

    print("[4/6] Extracting solution...")
    assignment = extract_solution(x, inst["shifts"], inst["invigilators"])

    print("[5/6] Verifying hard constraints...")
    issues = verify_hard_constraints(assignment, inst)
    if issues:
        for issue in issues:
            print(f"      ! {issue}")
    else:
        print("      ✓ all hard constraints satisfied")

    print("[6/6] Computing metrics and exporting...")
    am_vals = {j: am[j].value() for j in inst["invigilators"]}
    ap_vals = {j: ap[j].value() for j in inst["invigilators"]}
    metrics = compute_metrics(assignment, am_vals, ap_vals, inst)

    print(f"      Z_travel   = {metrics['z_travel']:8.2f}  "
          f"(weighted = {LAMBDAS['travel'] * metrics['z_travel']:8.2f})")
    print(f"      Z_fatigue  = {metrics['z_fatigue']:8.0f}  "
          f"(weighted = {LAMBDAS['fatigue'] * metrics['z_fatigue']:8.2f})")
    print(f"      Z_fairness = {metrics['z_fairness']:8.4f}  "
          f"(weighted = {LAMBDAS['fairness'] * metrics['z_fairness']:8.2f})")

    counts = list(metrics["count"].values())
    print(f"      workload (count):  min={min(counts)}, max={max(counts)}, "
          f"mean={sum(counts)/len(counts):.2f}")

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    export_solution(assignment, inst, ORIGINAL_CSV, OUTPUT_CSV)
    print(f"      ✓ {OUTPUT_CSV}")

    log = {
        "status": status,
        "objective": pulp.value(model.objective),
        "z_travel": metrics["z_travel"],
        "z_fatigue": metrics["z_fatigue"],
        "z_fairness": metrics["z_fairness"],
        "lambdas": LAMBDAS,
        "solve_time_sec": solve_time,
        "n_variables": n_vars,
        "n_constraints": n_cons,
        "count_per_staff": metrics["count"],
        "weighted_workload_per_staff": {k: round(v, 4) for k, v in metrics["workload"].items()},
        "alpha_minus": {j: round(am_vals[j], 4) for j in inst["invigilators"]},
        "alpha_plus": {j: round(ap_vals[j], 4) for j in inst["invigilators"]},
    }
    with open(OUTPUT_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"      ✓ {OUTPUT_LOG}")


if __name__ == "__main__":
    main()

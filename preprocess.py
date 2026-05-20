"""
IAP — Phase 2: Data Preprocessing
=================================
Reads the anonymized HCMUT FCSE invigilator dataset, imputes missing
fields, synthesizes home-campus preferences, and emits a structured
JSON file consumed by the Phase 3 ILP solver.

Outputs:
    iap_data.json — sets, parameters, synthesized preferences, baseline.
"""

import json
import random
from collections import defaultdict

from pathlib import Path

import pandas as pd


# ---------- Configuration ----------
HERE = Path(__file__).parent
INPUT_CSV = HERE / "Dataset_Anonymized_Invigilator_Assignment_Problem.csv"
OUTPUT_JSON = HERE / "iap_data.json"
RNG_SEED = 42  # reproducibility of synthetic preferences

# Slot desirability multipliers
SLOT_MULT = {1: 1.1, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.2}

# Day-of-week desirability multipliers
DAY_MULT = {
    "Thứ 2": 1.0, "Thứ 3": 1.0, "Thứ 4": 1.0, "Thứ 5": 1.0, "Thứ 6": 1.0,
    "Thứ 7": 1.2, "Chủ Nhật": 1.3,
}

# Same-day consecutive-slot pairs that count as back-to-back fatigue
# (Ca k → Ca k+1 with gap < 30 min). Excludes (2,3): 1-hour lunch gap.
BACK_TO_BACK_SLOTS = [(1, 2), (3, 4), (4, 5)]

# Hard cap on shifts/invigilator/day (matches observed maximum in baseline)
DAILY_CAP = 4

# Synthetic home-campus distribution
HOME_DIST = {"CS1": 0.4, "CS2": 0.4, "eq": 0.2}


# ---------- Step 1: Load and impute ----------
def load_and_impute(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    # Impute Thứ from Ngày (date → weekday)
    weekday_map = {
        0: "Thứ 2", 1: "Thứ 3", 2: "Thứ 4", 3: "Thứ 5",
        4: "Thứ 6", 5: "Thứ 7", 6: "Chủ Nhật",
    }
    df["Ngày"] = pd.to_datetime(df["Ngày"])
    df["Thứ"] = df["Thứ"].fillna(df["Ngày"].dt.weekday.map(weekday_map))

    # Impute Cơ sở from first letter of Nhiệm vụ (L → CS1, D → CS2)
    campus_map = {"L": "Cơ sở 1", "D": "Cơ sở 2"}
    df["Cơ sở"] = df["Cơ sở"].fillna(df["Nhiệm vụ"].str[0].map(campus_map))

    assert df.isna().sum().sum() == 0, "Imputation incomplete"
    return df


# ---------- Step 2: Build shifts (E) ----------
def build_shifts(df: pd.DataFrame) -> dict:
    shifts = {}
    for shift_id, group in df.groupby("MS Ca thi"):
        slot = int(shift_id.split("_")[1])
        date = group["Ngày"].iloc[0].strftime("%Y-%m-%d")
        weekday = group["Thứ"].iloc[0]
        campus = "CS1" if group["Cơ sở"].iloc[0] == "Cơ sở 1" else "CS2"
        mu = SLOT_MULT[slot] * DAY_MULT[weekday]

        shifts[shift_id] = {
            "slot": slot,
            "date": date,
            "weekday": weekday,
            "campus": campus,
            "P": len(group),
            "mu": round(mu, 3),
        }
    return shifts


# ---------- Step 3: Invigilators (S) and synthetic homes ----------
def build_invigilators(df: pd.DataFrame) -> tuple[list, dict]:
    rng = random.Random(RNG_SEED)
    invigilators = sorted(df["MS của CÁN BỘ COI THI"].unique())

    homes = {}
    for cb in invigilators:
        r = rng.random()
        if r < HOME_DIST["CS1"]:
            homes[cb] = "CS1"
        elif r < HOME_DIST["CS1"] + HOME_DIST["CS2"]:
            homes[cb] = "CS2"
        else:
            homes[cb] = "eq"
    return invigilators, homes


# ---------- Step 4: Day index (E_d) ----------
def build_E_d(shifts: dict) -> dict:
    E_d = defaultdict(list)
    for sid, s in shifts.items():
        E_d[s["date"]].append(sid)
    return dict(E_d)


# ---------- Step 5: Back-to-back pairs (E_b) ----------
def build_E_b(shifts: dict) -> list:
    by_date = defaultdict(dict)  # date → {slot: shift_id}
    for sid, s in shifts.items():
        by_date[s["date"]][s["slot"]] = sid

    pairs = []
    for date, slot_map in by_date.items():
        for k1, k2 in BACK_TO_BACK_SLOTS:
            if k1 in slot_map and k2 in slot_map:
                pairs.append([slot_map[k1], slot_map[k2]])
    return pairs


# ---------- Step 6: Travel parameter d_{ij} ----------
def compute_travel(shifts: dict, invigilators: list, homes: dict) -> dict:
    """Sparse: only nonzero entries, keyed as d_ij[shift_id][cb_id]."""
    d_ij = defaultdict(dict)
    for sid, s in shifts.items():
        for cb in invigilators:
            home = homes[cb]
            if home == "eq":
                cost = 0.5
            elif home == s["campus"]:
                cost = 0.0
            else:
                cost = 1.0
            if cost > 0:
                d_ij[sid][cb] = cost
    return dict(d_ij)


# ---------- Step 7: Workload target W̄ ----------
def compute_W_bar(shifts: dict, n_inv: int) -> float:
    return sum(s["mu"] * s["P"] for s in shifts.values()) / n_inv


# ---------- Step 8: Baseline schedule (for Req. 9 comparison) ----------
def extract_baseline(df: pd.DataFrame) -> dict:
    baseline = defaultdict(list)
    for _, row in df.iterrows():
        baseline[row["MS Ca thi"]].append(row["MS của CÁN BỘ COI THI"])
    return dict(baseline)


# ---------- Main ----------
def main():
    print("[1/8] Loading and imputing missing values...")
    df = load_and_impute(INPUT_CSV)
    print(f"      {len(df)} rows, 0 NaNs after imputation")

    print("[2/8] Building shifts (E)...")
    shifts = build_shifts(df)
    print(f"      |E| = {len(shifts)} shifts")

    print("[3/8] Building invigilators (S) + synthetic homes...")
    invigilators, homes = build_invigilators(df)
    home_counts = pd.Series(list(homes.values())).value_counts().to_dict()
    print(f"      |S| = {len(invigilators)}; homes = {home_counts}")

    print("[4/8] Building day index (E_d)...")
    E_d = build_E_d(shifts)
    print(f"      |D| = {len(E_d)} days")

    print("[5/8] Building back-to-back pairs (E_b)...")
    E_b = build_E_b(shifts)
    print(f"      |E_b| = {len(E_b)} same-day consecutive pairs")

    print("[6/8] Computing travel parameter d_ij...")
    d_ij = compute_travel(shifts, invigilators, homes)
    nnz = sum(len(v) for v in d_ij.values())
    print(f"      nonzero entries: {nnz} / {len(shifts) * len(invigilators)}")

    print("[7/8] Computing workload target W̄...")
    W_bar = compute_W_bar(shifts, len(invigilators))
    print(f"      W̄ = {W_bar:.3f}")

    print("[8/8] Extracting baseline schedule...")
    baseline = extract_baseline(df)
    print(f"      {len(baseline)} shifts in baseline")

    data = {
        "shifts": shifts,
        "invigilators": invigilators,
        "homes": homes,
        "E_d": E_d,
        "E_b": E_b,
        "d_ij": d_ij,
        "W_bar": round(W_bar, 4),
        "baseline": baseline,
        "config": {
            "slot_mult": SLOT_MULT,
            "day_mult": DAY_MULT,
            "back_to_back_slots": BACK_TO_BACK_SLOTS,
            "daily_cap": DAILY_CAP,
            "home_dist": HOME_DIST,
            "rng_seed": RNG_SEED,
        },
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Saved to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()

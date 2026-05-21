# Invigilator Assignment Problem (IAP) — ILP Approach

**Course:** CO2011 — Mathematical Modeling, Semester 252
**Faculty of Computer Science and Engineering, HCMUT**

This project formulates and solves the exam invigilator assignment problem at HCMUT FCSE as an Integer Linear Program (ILP). The model is adapted from Bakhtiar et al. (2015) with three additional preference dimensions: travel cost, fatigue, and duration-weighted workload fairness.

## Team

- [Member 1]
- [Member 2]
- [Member 3]
- [Member 4]
- [Member 5]

## Pipeline

```
Dataset CSV ──► preprocess.py ──► iap_data.json ──► solver.py ──► solution.csv
                                                                + solver_log.json
```

1. **`preprocess.py`** — Load the anonymized HCMUT dataset, impute missing values (`Thứ` from `Ngày`; `Cơ sở` from `Nhiệm vụ`), synthesize per-invigilator home-campus preferences (40 / 40 / 20 split, seeded), and emit a structured JSON.
2. **`solver.py`** — Build the ILP with PuLP, solve with CBC at 5% optimality gap, verify hard constraints, and export the optimized schedule.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
python preprocess.py     # creates iap_data.json
python solver.py         # creates solution.csv + solver_log.json
```

## Results vs. baseline schedule

| Metric | Baseline (manual) | Solver (ILP) | Change |
|---|---|---|---|
| Workload range (count) | 3–19 shifts | 10–11 shifts | std dev 2.22 → 0.50 |
| Back-to-back fatigue events | 129 | **0** | $-100\%$ |
| Travel cost (synthetic homes) | 385.0 | 181.5 | $-52.9\%$ |
| Solve time | — | ~5–10 s | — |

## Repository structure

```
.
├── README.md                          this file
├── requirements.txt                   Python dependencies
├── preprocess.py                      Phase 2 data preprocessing
├── solver.py                          Phase 3 ILP solver
├── Phase_1_Mathematical_Modeling.md   Phase 1 report (model spec)
├── Phase_2_Data_Preprocessing.md      Phase 2 report
└── Dataset_Anonymized_Invigilator_Assignment_Problem.csv        Input dataset (anonymized)
```

Generated files (`iap_data.json`, `solution.csv`, `solver_log.json`) are produced at runtime and are listed in `.gitignore`.

## References

Bakhtiar, T., Hanum, F., & Romliyah, A. (2015). Exam Invigilators Assignment Problem: A Goal Programming Approach. *Applied Mathematical Sciences*, Vol. 9, No. 58, pp. 2871–2880.

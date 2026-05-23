# Introduction

Exam invigilation at large universities is a high-volume scheduling problem with two interlocking concerns: the operational requirement to staff every exam shift with the correct number of supervisors, and the equity concern that the resulting workload should be fair. At HCMUT's Faculty of Computer Science and Engineering (FCSE) — operating across two campuses separated by approximately 15 km and exam periods spanning several weeks — the existing manual scheduling process produces visible inefficiencies. Some invigilators repeatedly cross campuses while others stay put; some absorb six times the workload of others; same-day back-to-back shifts accumulate to dozens over a single exam period. The schedule satisfies hard constraints (every shift is covered, no clashes occur) but optimizes for nothing.

The Invigilator Assignment Problem (IAP) — formally, the constrained optimization of assignments from staff to shifts — has been studied in the operations-research literature. Bakhtiar et al. (2015) propose a goal-programming formulation that layers two soft constraints (equal total workload and equal share of unpleasant early-morning shifts) on top of standard coverage and clash-avoidance constraints. Their formulation provides a clean foundation but does not capture three operational dimensions that matter in the HCMUT context:


1. **Travel cost between campuses**, which a single-location formulation cannot represent;
2. **Same-day fatigue accumulation**, beyond what a simple daily cap can express;
3. **Duration- and slot-weighted fairness**, which accounts for the asymmetric desirability of different time slots and weekdays.

## Contributions

Thầy yêu cầu làm cái table ghi % với ai làm gì 


---

# Conclusion

This project formalized, implemented, and analyzed an Integer Linear Programming approach to the Invigilator Assignment Problem at HCMUT FCSE. The work spans the full operational pipeline from raw dataset to deployable solver, with quantitative evidence that the resulting schedule materially improves on the manual baseline across all three optimization dimensions.




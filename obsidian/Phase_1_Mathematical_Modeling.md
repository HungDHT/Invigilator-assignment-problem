# Phase 1 — Mathematical Modeling

> [!info] Scope
> This document covers Requirements 1 through 5 of the assignment (40% of total grade): formal definition of sets, parameters, decision variables, objective function, hard constraints, and soft constraints for the Invigilator Assignment Problem (IAP) at HCMUT FCSE.

## Context and Approach

The Invigilator Assignment Problem requires assigning a fixed number of invigilators to each scheduled exam shift, drawn from a pool of staff, subject to availability rules and fairness preferences. We base our formulation on Bakhtiar et al. (2015) [^bakhtiar], adapted to the HCMUT FCSE setting with three additional preference dimensions:

1. **Travel cost** — invigilators incur a penalty when assigned to shifts away from their home campus.
2. **Fatigue** — same-day consecutive shifts are softly discouraged.
3. **Duration-weighted fairness** — workload is balanced using shift-desirability multipliers, generalizing Bakhtiar's pure-count fairness.

[^bakhtiar]: Bakhtiar, T., Hanum, F., & Romliyah, A. (2015). Exam Invigilators Assignment Problem: A Goal Programming Approach. *Applied Mathematical Sciences*, Vol. 9, No. 58, pp. 2871–2880.

### Design decisions

| Decision | Rationale |
|---|---|
| All three roles (CBCT, Thư ký, Trưởng HĐ) treated as one | The optimization concerns invigilation duty assignment; role distinctions are administrative and do not affect spatial/temporal scheduling logic. |
| Bakhtiar's clash-free constraint omitted | The HCMUT five-slot timetable is non-overlapping; the only possible clash is double-assignment to the same shift, prevented by binary $x_{ij}$. |
| Daily cap raised to $k=4$ (vs. Bakhtiar's $k=2$) | The HCMUT operating environment routinely schedules more than two shifts per invigilator per day; the value of $k$ is chosen to match the maximum daily load observed during dataset analysis (Phase 2), preserving feasibility while still bounding extreme overloads. |
| $L_1$ fairness rather than variance | Variance is quadratic and would force a Mixed-Integer Quadratic Programming (MIQP) formulation. $L_1$ keeps the model in pure ILP. |
| Home-campus preference synthesized at 40/40/20 split | Reflects assumed roughly even staff distribution between the two HCMUT campuses (~15 km apart) with a smaller equidistant subset. |

---

## Req. 1 — Sets and Parameters

### 1.1 Indexing sets

| Symbol | Definition |
|---|---|
| $E$ | Set of exam shifts (one per `MS Ca thi`) |
| $S$ | Set of invigilators |
| $D$ | Set of distinct dates in the exam period |
| $C$ | Set of campuses, $C = \{c_1, c_2\} = \{\text{CS1}, \text{CS2}\}$ |
| $E_d \subseteq E$ | Shifts taking place on day $d \in D$ |
| $E_b \subseteq E \times E$ | Same-day back-to-back pairs $(i, i')$ |

The set $E_b$ is constructed from same-day consecutive time-slot pairs whose inter-slot gap is less than 30 minutes. From the HCMUT five-slot timetable, the qualifying pairs are $(s, s+1) \in \{(1,2), (3,4), (4,5)\}$. The pair $(2,3)$ is excluded because of the one-hour lunch gap between slots 2 and 3.

### 1.2 Shift parameters (extracted from data)

For each shift $i \in E$:

| Symbol | Type | Definition |
|---|---|---|
| $P_i$ | $\mathbb{Z}_{>0}$ | Required number of invigilators |
| $c(i)$ | $C$ | Campus of shift $i$ |
| $d(i)$ | $D$ | Date of shift $i$ |
| $s(i)$ | $\{1, 2, 3, 4, 5\}$ | Time slot index |
| $\tau_i$ | $\mathbb{R}_{>0}$ | Duration in minutes |
| $\mu_i$ | $\mathbb{R}_{>0}$ | Desirability multiplier (defined below) |

The desirability multiplier $\mu_i$ encodes the relative cost of a shift compared with a baseline weekday afternoon:

$$\mu_i = \mu^{\text{slot}}_{s(i)} \cdot \mu^{\text{day}}_{d(i)} \tag{1.1}$$

with the slot and day multipliers configured as:

$$\mu^{\text{slot}}_s = \begin{cases} 1.1 & s = 1 \quad \text{(07:00 — early morning)} \\ 1.0 & s \in \{2, 3, 4\} \\ 1.2 & s = 5 \quad \text{(18:15 — evening)} \end{cases} \qquad \mu^{\text{day}}_d = \begin{cases} 1.0 & \text{Mon–Fri} \\ 1.2 & \text{Saturday} \\ 1.3 & \text{Sunday} \end{cases}$$

> [!note] Justification
> Early-morning, evening, and weekend shifts are widely considered less desirable due to commute timing and personal-time impact. Multiplying these slots upward causes them to count more heavily in the workload-fairness goal — an invigilator who absorbs many such shifts contributes proportionally more "weighted workload."

### 1.3 Synthesized invigilator parameters (simulated location data)

For each invigilator $j \in S$, we synthesize a home-campus assignment $h(j)$ drawn from a fixed categorical distribution:

$$h(j) \sim \text{Categorical}\left(\{c_1: 0.4,\ c_2: 0.4,\ \texttt{eq}: 0.2\}\right) \tag{1.2}$$

with three semantic categories:

- $h(j) = c_1$ — invigilator resides near Campus 1 (Lý Thường Kiệt, District 10)
- $h(j) = c_2$ — invigilator resides near Campus 2 (Dĩ An, Bình Dương)
- $h(j) = \texttt{eq}$ — equidistant or no strong preference

> [!note] Synthesis methodology
> The two HCMUT main campuses are approximately 15 km apart. The 40-40-20 split assumes the staff population is roughly evenly divided between the two areas, with a smaller equidistant subset. Synthesis uses Python's `random` module with a fixed seed (`RNG_SEED = 42`) so all team members and reviewers reproduce the same realization.

### 1.4 Derived parameters

The travel-cost parameter is computed deterministically from $h$ and $c$:

$$d_{ij} = \begin{cases} 0 & h(j) = c(i) \quad \text{(home match)} \\ 0.5 & h(j) = \texttt{eq} \\ 1 & h(j) \in C \setminus \{c(i)\} \quad \text{(cross-campus mismatch)} \end{cases} \tag{1.3}$$

The fairness target $\bar{W}$ is the per-invigilator average of total weighted demand:

$$\bar{W} = \frac{1}{|S|} \sum_{i \in E} \mu_i \cdot P_i \tag{1.4}$$

This target is computed once during preprocessing.

### 1.5 Configuration constants

| Symbol | Value | Description |
|---|---|---|
| $k$ | $4$ | Hard cap on shifts per invigilator per day |
| $\Delta$ | $30 \text{ min}$ | Maximum inter-slot gap for back-to-back classification |
| `RNG_SEED` | $42$ | Reproducibility of synthesized homes |

---

## Req. 2 — Decision Variables

### 2.1 Primary decision variable

$$x_{ij} = \begin{cases} 1 & \text{if invigilator } j \text{ is assigned to shift } i \\ 0 & \text{otherwise} \end{cases} \qquad \forall i \in E,\ j \in S \tag{2.1}$$

**Type:** Binary. **Cardinality:** at most $|E| \cdot |S|$ in the dense case.

> [!tip] Variable pruning for scalability
> In a sparse implementation, $x_{ij}$ is instantiated only for pairs where invigilator $j$ is potentially eligible for shift $i$. This is critical when scaling to thousands of shifts and invigilators (Req. 10).

### 2.2 Auxiliary variable — fatigue

$$y_{ii'j} \in \{0, 1\} \qquad \forall (i, i') \in E_b,\ \forall j \in S \tag{2.2}$$

**Type:** Binary. **Physical meaning:** $y_{ii'j} = 1$ if and only if invigilator $j$ is assigned to both back-to-back shifts $i$ and $i'$. This variable linearizes the otherwise bilinear conjunction $x_{ij} \wedge x_{i'j}$ — see constraint (5.2) below.

### 2.3 Auxiliary variables — workload deviation

$$\alpha_j^-,\ \alpha_j^+ \in \mathbb{R}_{\ge 0} \qquad \forall j \in S \tag{2.3}$$

**Type:** Continuous, non-negative. **Physical meaning:**

- $\alpha_j^-$ — *under-deviation*: how far below $\bar{W}$ the actual weighted workload of invigilator $j$ falls
- $\alpha_j^+$ — *over-deviation*: how far above $\bar{W}$ it overshoots

These are deviation variables in the goal-programming sense [^bakhtiar]. At optimality, at most one of the two is nonzero per invigilator: any positive value in both could be reduced by the same amount in both, lowering the objective without violating any constraint.

---

## Req. 3 — Objective Function

We minimize a weighted sum of three penalty terms:

$$\boxed{\;\min Z \;=\; \lambda_1 \underbrace{\sum_{i \in E}\sum_{j \in S} d_{ij}\, x_{ij}}_{Z_{\text{travel}}} \;+\; \lambda_2 \underbrace{\sum_{(i,i') \in E_b}\sum_{j \in S} y_{ii'j}}_{Z_{\text{fatigue}}} \;+\; \lambda_3 \underbrace{\sum_{j \in S} (\alpha_j^- + \alpha_j^+)}_{Z_{\text{fairness}}}\;} \tag{3.1}$$

### 3.1 Term interpretations

| Term | Expression | Practical meaning |
|---|---|---|
| Travel | $\sum_{i,j} d_{ij} x_{ij}$ | Total travel mismatch across all assignments |
| Fatigue | $\sum_{(i,i'),j} y_{ii'j}$ | Number of same-day consecutive double-shifts |
| Fairness | $\sum_j (\alpha_j^- + \alpha_j^+)$ | Total $L_1$ deviation of weighted workload from $\bar{W}$ |

### 3.2 Justification

**Why this objective is appropriate.** It directly measures three real-world costs that the manual baseline schedule does not optimize for. Travel cost reflects commute time and energy expenditure. Fatigue penalty reflects observed quality degradation in invigilation under back-to-back duty. Fairness deviation prevents any single invigilator from absorbing disproportionate workload — the most common complaint in manual scheduling.

**Why $L_1$ rather than variance.** The $L_1$ form (sum of absolute deviations) keeps the model in pure ILP territory. Variance is quadratic and would require Mixed-Integer Quadratic Programming, restricting solver choice and increasing solution time. The $L_1$ formulation also tends to spread deviations evenly rather than concentrating them on a few extreme cases.

**On the weights $\lambda_1, \lambda_2, \lambda_3$.** These are tunable parameters subject to systematic adjustment in Phase 4 (Req. 8). Initial proposed values: $\lambda_1 = 1$, $\lambda_2 = 5$, $\lambda_3 = 1$. The fatigue coefficient is set higher because each occurrence is comparatively rare but particularly objectionable from the staff's perspective.

---

## Req. 4 — Hard Constraints

### (H1) Coverage

Every shift must be staffed by exactly its required number of invigilators:

$$\sum_{j \in S} x_{ij} = P_i \qquad \forall i \in E \tag{4.1}$$

This rule is non-negotiable: a shift with too few invigilators violates exam-administration policy; with too many, staff resources are wasted.

### (H2) Daily cap

No invigilator is assigned more than $k$ shifts on any single day:

$$\sum_{i \in E_d} x_{ij} \le k \qquad \forall d \in D,\ \forall j \in S \tag{4.2}$$

with $k$ chosen to bound extreme overloads while remaining feasible against the operating environment's actual daily-load patterns. The specific value used in this study is justified in the Design decisions table above and confirmed against the data in Phase 2.

> [!note] Removed: clash-free constraint
> Bakhtiar's formulation includes $\sum_{i \in E_o} x_{ij} \le 1$ for overlapping time slots. In our HCMUT-adapted model this is structurally redundant: the five fixed time slots are non-overlapping, so the only possible "clash" is double-assignment to the same shift — already prevented by $x_{ij} \in \{0, 1\}$.

### (H3) Pre-known unavailability

Implemented at the variable-creation level: $x_{ij}$ is not instantiated for pairs $(i, j)$ where invigilator $j$ is unavailable for shift $i$. This is more efficient than adding $x_{ij} = 0$ as an explicit linear constraint.

---

## Req. 5 — Soft Constraints

The soft constraints take two forms: **goal constraints with deviation variables** (the goal-programming pattern from Bakhtiar et al.) and **linearization auxiliaries** for non-linear expressions. Each one contributes a corresponding penalty term to the objective.

### (S1) Travel penalty

The travel cost $d_{ij}$ is a precomputed parameter, so no algebraic constraint is required. The penalty appears directly as the first term of the objective (3.1):

$$Z_{\text{travel}} = \sum_{i \in E}\sum_{j \in S} d_{ij}\, x_{ij} \tag{5.1}$$

This is the cleanest possible formulation — campus mismatch is an attribute of the assignment itself, not a state of the model.

### (S2) Fatigue — linearized conjunction

For every back-to-back pair and every invigilator:

$$y_{ii'j} \ge x_{ij} + x_{i'j} - 1 \qquad \forall (i, i') \in E_b,\ \forall j \in S \tag{5.2}$$

**Linearization argument.** In a minimization problem with $y_{ii'j}$ appearing as a positive-coefficient term in the objective, the solver pushes $y_{ii'j}$ toward zero. Constraint (5.2) forces $y_{ii'j} \ge 1$ exactly when both $x_{ij} = 1$ and $x_{i'j} = 1$. In all other cases the right-hand side is non-positive, allowing $y_{ii'j} = 0$. This achieves the AND semantics $y_{ii'j} = x_{ij} \wedge x_{i'j}$ without any bilinear terms, keeping the model in pure ILP territory.

### (S3) Duration-weighted workload fairness

For each invigilator, the actual weighted workload should match the target $\bar{W}$:

$$\sum_{i \in E} \mu_i \cdot x_{ij} + \alpha_j^- - \alpha_j^+ = \bar{W} \qquad \forall j \in S \tag{5.3}$$

**Goal-programming interpretation.** Constraint (5.3) is always satisfiable because the deviation variables $\alpha_j^-, \alpha_j^+$ absorb any discrepancy between the actual weighted workload $\sum_i \mu_i x_{ij}$ and the target $\bar{W}$. The objective then minimizes $\alpha_j^- + \alpha_j^+$, driving each invigilator's workload toward $\bar{W}$ in $L_1$ distance. If the actual is below the target, $\alpha_j^- > 0$; if above, $\alpha_j^+ > 0$; at most one is positive at optimum.

> [!note] Why $\tau_i$ does not appear in (5.3)
> Bakhtiar's general formulation uses $w_i = \tau_i \cdot \mu_i$ where $\tau_i$ is shift duration. In the HCMUT dataset, all shifts are 150 minutes — so $\tau_i$ is a global constant that cancels out of the goal equation. The simplified weight $w_i = \mu_i$ retains the meaningful structure (slot/day desirability) without redundant scaling.

---

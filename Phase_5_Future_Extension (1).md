# Phase 5 — Future Extension: Scaling via Genetic Algorithm


## 5.1 Why the ILP doesn't scale

The present FCSE instance ($|E| = 65$, $|S| = 73$, $\sim 4{,}700$ binary variables) solves in seconds. At university-wide scale across all faculties — projected at $|E| \sim 10^4$, $|S| \sim 10^3$ — the same formulation would contain on the order of $10^7$ binary variables, a 2000$\times$ expansion. The IAP is NP-hard in general, but the practical bottleneck is more specific: the fatigue linearization $y_{ii'j} \ge x_{ij} + x_{i'j} - 1$ has a structurally loose LP relaxation (Phase 3 §3.6), so branch-and-bound cannot close the optimality gap quickly. At small scale this costs seconds; at university scale it would prevent termination.

A Genetic Algorithm[^holland] sidesteps the LP relaxation entirely by operating directly in the discrete schedule space — paying for it with no optimality guarantee, but gaining tractability.

[^holland]: Holland, J. H. (1975). *Adaptation in Natural and Artificial Systems*. University of Michigan Press.

## 5.2 Chromosome Encoding

A chromosome is a list of length $|E|$, where entry $i$ is the sorted tuple of $P_i$ invigilator IDs assigned to shift $i$:

$$\text{chromosome} = \big[ (j_1^{(1)}, \dots, j_{P_1}^{(1)}),\ \dots,\ (j_1^{(|E|)}, \dots, j_{P_{|E|}}^{(|E|)}) \big]$$

This encoding makes coverage (H1) **structural** — every chromosome of this shape automatically satisfies $\sum_j x_{ij} = P_i$. The only hard constraint that operators must respect or repair is the daily cap (H2).

## 5.3 Genetic Operators

**Crossover** (uniform shift crossover): for each shift independently, copy the assignment from parent A with probability 0.5, else from parent B. Repair (H2) violations afterward.

**Mutation** (per shift with probability $p_m$): swap one invigilator with a randomly chosen alternative not currently assigned to that shift.

**Repair** (re-establish H2): when an invigilator $j$ exceeds the daily cap on day $d$, replace $j$ on one of their assigned shifts on $d$ with a randomly chosen alternative from $S$ who is below cap that day.

## 5.4 Fitness Function

Identical to the ILP objective, evaluated directly on the chromosome:

$$\text{fitness}(c) = \lambda_1 Z_{\text{travel}}(c) + \lambda_2 Z_{\text{fatigue}}(c) + \lambda_3 Z_{\text{fairness}}(c)$$

The GA minimizes fitness. Because the encoding satisfies (H1) and the repair operator enforces (H2), no penalty terms for hard-constraint violations are needed in the fitness function.

## 5.5 Initial Population and Selection

- **Initialization**: one greedy seed (assign shifts chronologically, preferring home-campus matches and avoiding back-to-back) plus $N - 1$ randomly generated feasible chromosomes.
- **Selection**: tournament of size 3 — pick three random chromosomes, keep the best as a parent.
- **Elitism**: the top 10% of each generation passes unchanged to the next, preventing loss of the best solutions found so far.

## 5.6 Hyperparameters

| Parameter | Starting value |
|---|---|
| Population size | $100$ |
| Generations | $1{,}000$ |
| Crossover rate | $0.8$ |
| Mutation rate per shift $p_m$ | $0.05$ |
| Tournament size | $3$ |
| Elitism | $10\%$ |

These are standard defaults from the scheduling-GA literature. They would themselves require tuning on the target instance class — a smaller validation instance ($|E| \sim 200$) should be used first to confirm operators behave correctly and to baseline the GA against the ILP solution on a problem where the ILP still solves to optimality.

---

## Summary

A Genetic Algorithm with shift-indexed integer-list encoding, uniform shift crossover, swap mutation, and a repair operator for the daily cap is the recommended path for scaling the IAP beyond the present ILP's tractable range. The encoding makes the dominant hard constraint structural, the operators are simple to implement and analyze, and the fitness function reuses the existing objective decomposition unchanged. The GA's lack of an optimality guarantee is the cost of escaping the LP-relaxation looseness that limits the ILP at scale.

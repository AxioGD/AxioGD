# Evaluation

## Content quality

Outputs are assessed against case-specific reference GD conditions. Method names and AD references are removed before evaluation. The evaluator checks both correctness and support from the inputs available in each run.

| Count | Definition |
|---|---|
| TP | A reference item for which each condition is correct, supported by the available inputs, and stated as an established condition. |
| FN | A reference item that does not satisfy the TP criteria, including items left unresolved. |
| FP | A distinct confirmed semantic error in the output. |

For each run:

- Precision: `P = TP / (TP + FP)`
- Recall: `R = TP / (TP + FN)`
- F1: `F1 = 2PR / (P + R)`

## Formulation success

A successful formulation preserves known requirements and the choices left to GD, satisfies the output requirements, and addresses necessary modelling decisions.

When essential information is missing, the formulation must justify a provisional model and state its scope, or specify the information or validation needed. An error that invalidates a required condition or modelling decision causes the run to fail.

## Reliability across repeated runs

Each method is run five times for each case and request version. Let `c` be the number of successful runs:

- `pass¹ = c / 5`
- `pass² = c(c − 1) / (5 × 4)`

Here, `pass²` is the probability that two runs sampled without replacement both succeed. Difficulty-level results are calculated by averaging the case-level rates with equal weight.

## Token cost per successful formulation

For each method, request version and difficulty level:

`Tokens per success (k) = total tokens across all runs / (1000 × number of successful runs)`

The total includes successful and failed runs. Only the method’s own input and output tokens are counted; simulated-designer and evaluator calls are excluded. Groups with no successful runs are reported as `—`.

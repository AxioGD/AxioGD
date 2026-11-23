# AxioGD

Companion repository for the AxioGD paper.

## Overview

AxioGD uses axiomatic design (AD) to guide the formulation
of generative design (GD) problems from natural-language
design requests and textual geometry descriptions.

## Experimental study

The study compares three approaches:

- LLM: direct formulation using a large language model.
- LLM + GD rules: formulation supported by explicit GD rules.
- AxioGD: an AD-guided LLM agent for GD problem formulation,
  using the same GD rules as the LLM + GD rules baseline.

The evaluation covers ten structural design cases,
each with simple and detailed request versions.
Each method is run five times for each case and request version.

The evaluation measures include content precision, recall,
and F1, formulation success, and token cost per successful
formulation.

## Repository contents

- [Method code](axiogd/) — Python implementation of the three methods.
- [Prompts](prompts/README.md) — Instructions used by each method.
- [Design cases](cases/README.md) — Sources and difficulty ratings for the ten cases, with a comparison of two runs for C10.
- [Evaluation](evaluation/README.md) — Scoring rules and metric definitions.
- [Results](results/README.md) — Summary of the experimental results.

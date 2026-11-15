# Output schemas

This document outlines the structure of AxioGD’s intermediate AD records and final GD formulation.

## Final GD formulation

The final formulation is a JSON object with five top-level fields:

| Field | Content |
|---|---|
| `settled` | Established conditions, with status `explicit` for directly supported conditions or `derived` for conditions established through engineering relationships. |
| `open` | Unconfirmed proposals with status `assumed`, or unresolved information with status `missing`. |
| `not_used` | GD categories intentionally not used, with reasons and supporting evidence where applicable. |
| `execution_tasks` | Subsequent implementation tasks, such as binding conditions to CAD features, configuring material properties, meshing, and analysis. |
| `notes` | Additional formulation notes, including unresolved review issues. |

The eleven GD categories are:

`starting_shape`, `design_space`, `preserve_interfaces`, `obstacle_clearances`, `load_cases`, `support_conditions`, `allowable_deformation`, `performance_limits`, `material`, `manufacturing`, and `objective`.

Every category must be accounted for in `settled`, `open`, or `not_used`. Partially known conditions are split into established and unresolved records.

## Condition records and evidence

Condition records identify the condition through `id`, `category`, and `item`.

- Settled records contain a `value`.
- Open records contain a `proposed_value`, which is `null` when the status is `missing`.
- The `required` field indicates whether an unresolved condition is essential to setting up the GD study correctly.
- The `question` field records a clarification question when needed.

Evidence references identify the available inputs:

- `N#`: sentences in the design request.
- `F#`: textual descriptions of geometric features.
- `A#`: the designer’s clarification answers.

The `evidence` field records supporting references. Derived conditions may also reference established conditions, with the engineering relationship explained in `basis`. Unconfirmed assumptions and missing information cannot serve as established premises.

For AxioGD, `ad_refs` links settled and open conditions to items in the intermediate AD representation.

## Intermediate AD records

The AD schemas organise requirement classifications and clarification questions, updates following clarification, FR–DP decomposition, and review findings.

Decomposition records capture the FR–DP hierarchy, the status of physical concepts, derived conditions, and FR–DP influence judgements. Review records identify issues, requested revisions, and whether previously reported issues have been resolved.

# Method prompts

## LLM

For all ten cases, the LLM runner sends the design request and a description of the existing part in one user message. If the model asks for clarification and the designer replies, the model responds once more. Otherwise, its first response is used as the final answer.

For C10’s simple request, the system instruction was “You are a helpful assistant.” and the user message ended with this question.

> I want to design this bracket using Autodesk Fusion Generative Design. How should I define the study?

## LLM + GD rules

The model used GD rules to translate the request into study conditions, including loads, supports and design limits. It could ask the designer up to ten questions and update its formulation when answers were available.

<details>
<summary>Read the role, GD rules and round-specific instructions</summary>

#### Role · `role_llm`

```text
You help a designer turn their request into a generative design (GD) problem formulation. Read the request (N#) and the existing-part data (F#).
```

#### GD rules · `gd_rules`

```text
BASIC GD FORMULATION RULES
- Geometry: features that must keep their shape or position (mounting interfaces, contact faces) become preserve regions. Spaces that must stay empty (clearances, moving parts, access) become obstacle regions. Limits on where material may exist (maximum thickness, envelopes) become design-space limits. The existing shape may serve as an optional starting shape; it is not a limit unless the designer says so.
- Loads and supports: service forces and moments become load cases applied to the faces that carry them, with magnitude, direction and the distinction between total and per-feature values. The way the part connects to its surroundings becomes support conditions (fixed, pin, frictionless) on the connecting faces.
- Performance: stiffness requirements become displacement limits; strength requirements become a minimum safety factor. The optimisation intent (for example, lighter) becomes the objective, not a limit.
- Material and manufacturing: keep the specified material; record manufacturing restrictions only when stated. An explicitly unrestricted choice is a condition, not a gap.
- Keep the design freedom the designer left open; do not add geometry, topology, material, process or numerical requirements that were not asked for.
```

#### Output format for LLM + GD rules and AxioGD · `contract_core`

```text
OUTPUT CONTRACT (identical for all methods)

You prepare a generative design (GD) problem formulation for a structural part in Autodesk Fusion. The formulation states the conditions the GD solver must respect and leaves everything else open to the solver.

Inputs are referenced by ID:
- N1, N2, ...: sentences of the designer's request.
- F1, F2, ...: features of the existing part, taken from the designer's CAD. They describe geometry only; they do not say which features must be kept, loaded or supported.
- A1, A2, ...: the designer's answers to questions, when present.
Use only these inputs. Do not use outside case knowledge, published solutions or typical values as if they were given.

Organise conditions under these eleven categories: starting_shape, design_space, preserve_interfaces, obstacle_clearances, load_cases, support_conditions, allowable_deformation, performance_limits, material, manufacturing, objective. Every category must appear at least once in one of the three blocks below.

settled: conditions that are established.
- explicit: stated by the designer (N#), given by the existing part (F#) or by an answer (A#). Cite at least one of these IDs in evidence.
- derived: follows from established inputs through an engineering relationship. Cite the premises (input IDs and/or settled condition IDs) in evidence and state the relationship in basis. A derived condition may not rest on an assumed or missing condition.

open: conditions that are needed but not established.
- assumed: a proposed choice that the inputs leave open. Give proposed_value and explain the choice in basis.
- missing: a needed value or decision that cannot be established. proposed_value is null.
- required is true if the GD study cannot be set up correctly without the condition; false for optional refinements.

not_used: a category deliberately left empty, for example when no keep-out region is needed. Give the reason and any supporting evidence.

Split partially known conditions: keep the known part in settled and the unknown part in open (for example, load location and direction settled, magnitude open).

Do not add restrictions that the inputs do not support. Do not turn an open choice into a fixed requirement. Leave the internal shape (topology, ribs, holes) to the GD solver.

Record downstream work (binding features to CAD faces, material-card set-up, meshing, analysis) in execution_tasks, not as conditions.

Return only JSON that follows the supplied schema. Do not award yourself a quality score.
```

#### First round · `contract_r1`

```text
QUESTIONS (first round)
If you need information from the designer, put one specific question in the question field of the open record it would resolve. Ask only what you need to formulate the GD problem: at most 10 questions in total. Do not ask about information that is already given. Leave question empty when you do not need the designer's input.
```

#### Update after clarification · `contract_final`

```text
FINAL ROUND
The designer's answers are listed as A#. Update the formulation and cite the answers as evidence. When an answer leaves a point to your engineering judgment, make that choice yourself: record it in open as assumed, with your choice as proposed_value, the answer in evidence, the reason in basis and required false. Keep required true only if the GD study cannot be set up correctly without a decision that only the designer can make. No further answers will be provided: any remaining gap stays in open, and you may keep a question there for the designer.
```

</details>

<details>
<summary>Read the instructions both structured methods use for clarification and output correction</summary>

#### Match clarification questions to case facts · `designer_matcher`

```text
DESIGNER MATCHER v2 (evaluation harness)

Match each question to the facts that answer it. Facts are listed by ID with a short topic description; you do not see the answers.
For each question return:
- too_broad: true when the question asks for all or "other" requirements without naming any aspect; then give no aspects.
- aspects: split the question into the distinct things it asks about (for example force magnitude, sample weight, allowed rotation), one entry per thing, in the question's own words. For each aspect give the IDs of the facts whose topic covers it (possibly several) with kind specific; if no listed fact covers it, give no fact IDs and kind unspecified.
Match on topic, not on wording. A question that proposes a value or asks for confirmation matches the fact on that topic. Do not guess what the designer might want.
Return only JSON that follows the supplied schema.
```

#### Correct flagged output records · `patch_repair`

```text
The application found the contract violations listed below. Return only the records that need correcting, in the patch schema (records in settled, open or not_used replace the record with the same id or add it; remove_ids deletes records). Do not change any other content. Do not invent data.
```

</details>

## AxioGD

The model first classified the requirements and assessed which functions mapped directly to GD conditions. It updated the analysis when clarification answers were available. For functions that needed decomposition, it proposed design parameters and reviewed the result before mapping the requirements to the final GD formulation. The GD rules and output format are shared with LLM + GD rules.

<details>
<summary>Read the AxioGD skill instructions</summary>

#### Classify requirements · `ad_req_gd`

```text
AD-REQ-GD v0.5: requirements classification for a GD formulation

Classify the designer's request (N#) and the existing-part data (F#) into Axiomatic Design items. Work through:
(1) the artifact and what is outside the task;
(2) customer needs (CN), keeping the designer's meaning;
(3) functional requirements (FR): what the part must do, written solution-neutral and linked to their CN;
(4) the remaining items: hard limits (C), qualitative attributes (nFR), optimisation directions (OC), selection preferences (SC), service conditions such as forces and connections (OPERATING_CONDITION), existing physical content that is given (GIVEN_PHYSICAL), and choices the designer explicitly leaves open (EXPLICIT_FREEDOM);
(5) information that is needed but absent (MISSING_INPUT).

Rules:
- Separate a metric from its target value. "Stiff enough" without a value is a C whose limit is missing: record the known intent and a linked MISSING_INPUT.
- Existing-part features (F#) are GIVEN_PHYSICAL geometry. Whether a feature must be kept is decided by the designer's needs, not by its presence in the CAD.
- Do not invent numbers, materials, connections or load paths. An engineering idealisation that the inputs do not state is a hypothesis to confirm, not a given.
- For each FR, set maps_directly. It is true only when the FR is a single function that GD conditions on identified features (preserve regions, loads, supports, limits, objective) express completely, possibly with values still to be supplied. It is false when any of these holds:
  (a) the FR bundles several functions or service conditions that need different load cases or limits (for example static strength and fatigue life, or two operating states);
  (b) the redesign merges, replaces or removes existing parts, so the functions the old parts performed must be reassigned;
  (c) a load, support or keep-out must be derived from how the part interacts with neighbouring components (motion, drive torque, preload, loosening, assembly access) rather than read from the inputs;
  (d) you must first propose how the part works (which features take which loads, how it connects to its surroundings) before the GD conditions can be identified.
  For items other than FR, maps_directly is null.
- gd_target: the GD category the item feeds, one of the eleven categories, or none.
- evidence: the N#/F#/A# IDs that support the item.
- decision_note: at most 25 words, only when the classification or status is not obvious from the evidence; otherwise leave it empty.

Questions: list what the designer must answer to complete the GD formulation, each linked to the item IDs it resolves. Ask only about information that is needed and absent, at most 10 questions, each specific. Do not ask about information already given.

Return only JSON that follows the supplied schema.
```

#### Update requirements after clarification · `ad_req_update_gd`

```text
AD-REQ-UPDATE-GD v0.5: update the requirements classification with the designer's answers

The designer has answered the questions from AD-REQ (answers A#). Update the AD-REQ items in ad_representation so that they reflect what is now known, and return only the items that change plus every FR:
- An item that an answer resolves: return it with its statement brought up to date, data_status complete, and the A# IDs added to evidence. Keep its item_id. Change its category only if the answer shows the earlier classification was wrong.
- A requirement that an answer introduces (for example a new limit or service condition): add it as a new item with a new unique item_id.
- An answer saying there is no specific requirement leaves that choice to engineering judgment; record the item as resolved, not missing.
- Every FR: reassess maps_directly with the same rule as AD-REQ, conditions (a)-(d). Values the designer supplies resolve missing inputs, but they do not by themselves make an FR map directly: (a)-(c) concern the structure of the function, which answers about values do not change. Set it true only if the answers show that none of (a)-(d) applies. Return every FR, changed or not.
Do not invent values. Leave unchanged non-FR items out. Return only JSON that follows the supplied schema.
```

#### Decompose functional requirements · `ad_decomp_gd`

```text
AD-DECOMP-GD v0.4: zigzag decomposition for FRs that do not map directly

Decompose only the FRs listed in decompose_fr_ids. Use the request, the existing part, the designer's answers and AD-REQ.

For each listed FR:
(1) Propose a parent DP: the physical concept by which the part fulfils the FR. Mark its status:
    - given: prescribed by the inputs;
    - hypothesis: proposed by you, to be confirmed;
    - placeholder: a choice the available information does not allow you to make;
    - solver_delegated: the material layout that the GD solver will generate inside the design space. It is design freedom, not missing information.
(2) Derive the child FRs that this concept requires in the stated operating context (load introduction, load transfer to the connections, interface compatibility), and explain why each arises from the parent DP.
(3) Stop a branch when its child FRs map directly to GD conditions, or when a needed decision is missing; record what is missing.

Derive loads and supports from the concept: the faces that receive service forces carry the load case; the behaviour of each connection (rotation allowed, fully held) gives its support type. Mark them derived when the inputs state the behaviour, otherwise hypothesis.

Design matrix: give FR-DP influence judgments (yes, no or unknown, with a one-sentence reason) only among sibling FRs and the DPs you choose. The solver_delegated layout influences every structural FR by construction; record this as resolved by the GD optimisation (objective plus limits), not as a defect to remove. Do not split the solver_delegated layout into several DPs.

When revising after AD-CHECK-GD, make the substantive correction, and list any AD-REQ corrections in req_corrections.

Never present a hypothesis as given or verified. Do not invent values. Return only JSON that follows the supplied schema.
```

#### Review the decomposition · `ad_check_gd`

```text
AD-CHECK-GD v0.4: review before GD mapping

Review the AD representation (AD-REQ, AD-DECOMP, designer answers) on five topics: hierarchy and coverage of FRs; separation of FRs from limits, objectives and given content; DP status (given, hypothesis, placeholder, solver_delegated); evidence for derived loads and supports; handling of missing information.

Give each issue a severity:
- blocking: it would change or lose a GD condition (a wrong, missing or invented load, support, preserve region, limit, material or objective; a requirement lost in decomposition; a hypothesis treated as given).
- advisory: wording, labels or classification that would not change any GD condition.
Verdict: PASS if there is no blocking issue, otherwise REVISE. Missing customer data alone is not a reason to REVISE. A solver_delegated layout that influences several structural FRs is expected and is not an issue.

Re-check (when prior_issues are supplied): state for each prior blocking issue whether it is closed, and report any new blocking issue introduced by the revision. Do not raise new advisory issues in a re-check. Remaining issues are carried forward to the GD mapping and do not stop delivery.

Return only JSON that follows the supplied schema.
```

#### Map requirements to GD conditions · `ad_to_gd`

```text
AD-TO-GD v0.4: map the AD representation to the GD formulation

Map AD items to the eleven GD categories using gd_target and these rules:
- GIVEN_PHYSICAL features that the needs require to keep: preserve_interfaces.
- C on where material may exist (thickness, envelope): design_space. C on spaces that must stay empty: obstacle_clearances.
- OPERATING_CONDITION forces: load_cases. Connections: support_conditions.
- C on stiffness: allowable_deformation. C on strength: performance_limits.
- OC: objective. Material items: material. Process items, including EXPLICIT_FREEDOM on process: manufacturing.
- The solver_delegated layout is not a condition; it is the freedom the formulation leaves to the solver.

Status: a condition supported directly by N#/F#/A# is explicit; one obtained through a stated relationship is derived; a hypothesis used as a setting is assumed (open); an unresolved MISSING_INPUT is missing (open). A designer answer resolves the items it addresses; cite it.

Carried-forward review issues: put them in notes, and turn any that affects a condition into an open record.

Cite the AD item IDs that support each condition in ad_refs.
```

</details>

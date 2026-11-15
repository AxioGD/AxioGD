# Prompting protocol

For each case and request version, all three methods receive the same initial design request and textual geometry descriptions.

## Method comparison

| Method | Prompting approach |
|---|---|
| LLM | Directly request a GD problem formulation, without added GD rules or AD instructions. |
| LLM + GD rules | Supplement the design request with explicit rules for translating requirements into GD conditions. |
| AxioGD | Use the same GD rules within an AD-guided LLM agent that analyses requirements, selectively decomposes functional requirements, reviews the reasoning, and maps the resulting representation to GD conditions. |

## Shared GD rules

LLM + GD rules and AxioGD use the same GD formulation rules. These cover preserved interfaces, spaces that must remain empty, design-space limits, loads and supports, objectives, performance limits, materials, and manufacturing requirements.

The rules preserve choices left to GD and avoid introducing unsupported requirements. Existing geometry is not automatically treated as a design-space restriction.

## AxioGD procedure

1. **Requirement analysis:** Distinguish functional requirements, constraints, objectives, given information, and missing inputs. Incorporate the designer’s clarification answers.
2. **Selective FR–DP decomposition:** Decompose functional requirements when further reasoning is needed to identify GD conditions. Explicitly identify unconfirmed physical concepts and their dependent conditions.
3. **Review:** Check the decomposed representation for requirement coverage, consistency, and supporting evidence. Errors affecting GD conditions trigger one revision and re-check.
4. **GD mapping:** Translate the AD representation into GD conditions with supporting evidence. Record unconfirmed assumptions and missing information as open conditions.

If no functional requirement needs decomposition, the classified information proceeds directly to GD mapping.

## Clarification and evaluation

The LLM baseline receives additional case information only when it asks for clarification. LLM + GD rules and AxioGD may each ask up to ten clarification questions in one round. The simulated designer answers using recorded case facts.

The evaluation judge assesses final outputs against case-specific reference GD conditions. It is separate from AxioGD’s internal review step.

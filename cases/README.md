# Design cases

Each of the ten structural design cases was tested with a simple and a detailed request.

| Case | Source | D1–D5 | Total | Level |
|---|---|---|---:|:---:|
| C1 | [Junk and Burkart, 2021](https://doi.org/10.1016/j.procir.2021.05.126) | 0, 1, 0, 1, 0 | 2 | L1 |
| C2 | [Kowalik et al., 2025](https://doi.org/10.1108/AEAT-12-2024-0384) | 1, 0, 1, 1, 0 | 3 | L1 |
| C3 | [Ismail et al., 2020](https://doi.org/10.3390/app10062201) | 0, 2, 0, 1, 0 | 3 | L1 |
| C4 | [Barbieri and Muzzupappa, 2022](https://doi.org/10.3390/app12042106) | 1, 1, 1, 1, 0 | 4 | L2 |
| C5 | [Orme et al., 2018](https://doi.org/10.3390/designs2040051) | 0, 1, 1, 2, 1 | 5 | L2 |
| C6 | [Orme et al., 2018](https://doi.org/10.3390/designs2040051) | 1, 1, 1, 2, 1 | 6 | L2 |
| C7 | [Belluomo, 2025, Ch. 5](https://iris.uniroma1.it/retrieve/801a4e3c-ac00-4904-99ff-8c4b6e4e6abf/Generative_Design_perspectives_of_applicability_in_the_field_of_mechanical_engineering.pdf#page=80) | 1, 0, 1, 2, 2 | 6 | L2 |
| C8 | [Hassan and Biswas, 2024](https://doi.org/10.3390/designs8050099) | 2, 1, 1, 1, 2 | 7 | L3 |
| C9 | [Csányi and Molnár, 2024](https://acta.uni-obuda.hu/Csanyi_Molnar_144.pdf) | 2, 2, 2, 1, 1 | 8 | L3 |
| C10 | [Chen et al., 2021](https://doi.org/10.3390/app11156671) | 2, 2, 2, 1, 1 | 8 | L3 |

The five scores, in order, cover load derivation (D1), load-case count (D2), interfaces and supports (D3), spatial and manufacturing constraints (D4), and special requirements and functional decomposition (D5). Each dimension scores 0–2. Totals of 0–3, 4–6 and 7–10 correspond to L1, L2 and L3, respectively.

<details>
<summary>C10 example · Simple request and bolt-insertion clearance</summary>

**Simple request**

> This bracket connects parts of our aerospace equipment and is to be evaluated on a fatigue test machine. Only the written description of the current bracket is supplied; no CAD file or exact dimensions are included. We want it as light as possible, made in titanium by metal 3D printing. It must still bolt to the fixture through the three holes in the vertical plate and the four holes in the bottom plate, with their existing sizes and positions unchanged. It must survive the cyclic load of the fatigue test without failing.

**Existing part** (provided with the request)

> Current bracket: one piece, 480 g, L-shaped: a vertical plate standing on a horizontal bottom plate. Three bolt holes in the upper part of the vertical plate (A, B, C). Four bolt holes in the bottom plate (a, b, c, d, clockwise).

**Shared clarification** (excerpt from A2 for LLM + GD rules and A3 for AxioGD)

> The bottom bolts are inserted from above.

**Final outputs.** These excerpts come from the two simple-request runs discussed in Section 4.3.

| Recorded condition | LLM + GD rules · run 4 | AxioGD · run 1 |
|---|---|---|
| Clearance recorded as settled | Keep the existing through-hole volumes for A, B, C, a, b, c and d empty. (`S-OC-1`) | Maintain unobstructed access above the four bottom holes for insertion of the bottom bolts from above. (`GD-OC-02`) |
| Clearance beyond the hole bores | **Not used** (`NU-OC-1`)<br>The bottom-bolt insertion direction alone does not define a dimensioned clearance volume. | **Open dimensions** (`GD-OC-04`)<br>The required insertion direction is established, but bolt-head, tool, and access-envelope dimensions are unavailable. |

**AxioGD decomposition behind the clearance requirement**

- Functional requirement (`FR-01.4`) · “Provide lower-interface seating and unobstructed access for insertion of the four bottom bolts from above.”
- Design parameter (`DP-01.4`) · “Lower fixture-base seating faces together with bolt-head, tool, and top-insertion keep-out volumes.”

</details>

# Results summary

The study compares LLM, LLM + GD rules, and AxioGD across ten structural design cases. Each case has simple and detailed request versions, with five runs per method and request version, giving 300 runs in total.

Case definitions and evaluation criteria are provided in [cases](../cases/README.md) and [evaluation](../evaluation/README.md).

## L3 results with simple requests

This comparison covers the three cases with the highest formulation difficulty, with 15 runs per method.

| Method | Mean F1 | pass¹ | pass² | Tokens per success (k) |
|---|---:|---:|---:|---:|
| LLM | 0.459 | 0.200 | 0.100 | 19.56 |
| LLM + GD rules | 0.852 | 0.067 | 0.000 | 253.48 |
| AxioGD | 0.937 | 0.467 | 0.167 | 221.28 |

F1, pass¹, and pass² are averaged with equal weight across cases. Token cost is the total method tokens across all runs, including failures, divided by the number of successful formulations, expressed in thousands.

## Main observations

- With simple requests, AxioGD achieved the highest mean F1 at all three difficulty levels. With detailed requests, its F1 advantage over LLM + GD rules at L3 decreased from 0.085 to 0.010.
- AxioGD achieved the highest pass¹ and pass² at L1 and L3 with both request versions. At L2, LLM achieved higher formulation success than AxioGD with both versions. For detailed requests at L2, pass¹ was 0.500 for LLM and 0.400 for AxioGD.
- LLM used fewer tokens per successful formulation than AxioGD in all six difficulty–request groups. AxioGD used fewer tokens per success than LLM + GD rules at L3 with both request versions and at L2 with detailed requests.
- AxioGD’s success rate at L3 remained below 0.5: 0.467 with simple requests and 0.400 with detailed requests.

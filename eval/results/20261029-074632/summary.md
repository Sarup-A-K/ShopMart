# OmniTag evaluation results

Run: 2026-10-29 08:22 · model `llama3.2` · 42 answer cases × 5 configurations · LLM judge on

## 1. What each technique adds (answer cases)

| Configuration | Correct answers | Hallucination (before correction) | Hallucination (final) | Tool choice correct | Median latency | p95 latency | Judge (1-5) |
|---|---|---|---|---|---|---|---|
| Model alone (no store data) | 14.3% | 85.7% | 85.7% | n/a | 1.52 s | 1.85 s | 3.45 |
| v1: + product facts in prompt | 52.4% | 35.7% | 35.7% | n/a | 1.98 s | 2.94 s | 4.74 |
| v2: + RAG (store policies) | 66.7% | 26.2% | 26.2% | n/a | 1.94 s | 4.06 s | 4.81 |
| v3: tool-calling agent | 90.5% | 19.0% | 19.0% | 81.2% | 7.13 s | 10.46 s | 4.62 |
| v4: full system (+ guardrails, fact-check) | 92.9% | 11.9% | 2.4% | 81.2% | 4.17 s | 7.2 s | 4.74 |

**Accuracy by question type** (share of answers that contain every expected fact):

| Configuration | price_aisle | spec | deal | policy | agent | memory |
|---|---|---|---|---|---|---|
| baseline | 0.0% | 16.7% | 0.0% | 37.5% | 12.5% | 0.0% |
| v1_context | 100.0% | 100.0% | 66.7% | 37.5% | 12.5% | 100.0% |
| v2_rag | 100.0% | 100.0% | 100.0% | 100.0% | 12.5% | 100.0% |
| v3_agent | 100.0% | 100.0% | 100.0% | 87.5% | 81.2% | 100.0% |
| v4_full | 100.0% | 83.3% | 100.0% | 100.0% | 87.5% | 100.0% |

## 2. Semantic search vs keyword search

| Method | Recall@3 (15 queries) | Correctly finds nothing for nonsense queries (2) |
|---|---|---|
| Keyword matching | 77.8% | 100.0% |
| Semantic search (embeddings) | 95.6% | 100.0% |

## 3. Guardrails

| Prompt set | Attacks | Legitimate | Pattern rules only: attacks blocked / wrongly blocked | Rules + LLM guard: attacks blocked / wrongly blocked | Model complied with the attack when unguarded |
|---|---|---|---|---|---|
| Design set (its failures informed the LLM guard) | 12 | 6 | 8.3% / 0.0% | 100.0% / 0.0% | 25.0% |
| Held-out set (written before the LLM guard) | 11 | 9 | 18.2% / 0.0% | 100.0% / 0.0% | 27.3% |

By attack type (design set):

| Attack type | Cases | Blocked by rules only | Blocked by rules + LLM guard | Complied without guardrails |
|---|---|---|---|---|
| injection | 4 | 0.0% | 100.0% | 75.0% |
| negotiation | 5 | 20.0% | 100.0% | 0.0% |
| off_topic | 3 | 0.0% | 100.0% | 0.0% |

By attack type (held-out set):

| Attack type | Cases | Blocked by rules only | Blocked by rules + LLM guard | Complied without guardrails |
|---|---|---|---|---|
| injection | 4 | 25.0% | 100.0% | 25.0% |
| negotiation | 4 | 0.0% | 100.0% | 25.0% |
| off_topic | 3 | 33.3% | 100.0% | 33.3% |

## 4. Structured output

Persona insight (JSON schema enforced): 38/38 complete and valid.

## Failures of the full system

- **spec_14**: What kind of outsole does it have?
  - answer: Here is what I can confirm from our store data. Campus PROVE Men's Running Shoes (Navy): ₹1,329 (M.R.P. ₹2,499), Aisle 5, Sports Footwear.
- **agent_compare_cheaper**: Which is cheaper, the boAt earbuds or the Campus NORIKA running shoes, and where is the cheaper one?
  - answer: The Campus NORIKA running shoes are cheaper than the boAt earbuds. The Campus NORIKA running shoes can be found in Aisle 5, Sports Footwear section of our store.
- **agent_iphone**: What is the price of the iPhone and where can I find it?
  - answer: The price of the Apple iPhone 13 (Blue, 128GB) is ₹59,900. You can find it in Aisle 1, Mobiles section, at the back of the aisle, on the mobiles shelf, looking for Apple.

## How to read this

- A case is *correct* only if the answer contains every expected fact (price, aisle, spec or policy wording) and none of the forbidden claims. Checks are exact-number and keyword rules, so a correct answer worded unusually can be marked wrong (and the reverse is rare but possible). Read the CSV for the real text.
- *Hallucination* = the answer contains a rupee amount, aisle number or product name the store data does not support (same checker the app uses at run time, so it is biased toward catching what that checker can see). For v4 the 'before correction' figure is how often the model's own first answer failed.
- *Complied when unguarded* is a keyword heuristic on the model's raw answer. It was revised once after the first run, when reading the outputs showed it under-counted prompt leaks, so it is not a pre-registered metric. The guard columns are exact.
- The LLM judge is the same small model that writes the answers, so it is a weak, optimistic grader; compare 'judge when correct' vs 'judge when wrong' in summary.json to see whether it discriminates. The CSV has an empty `human_rating` column for your own 1-5 scores.
- Small sample (42 answer cases, 17 search queries, 38 safety prompts): treat percentages as indicative, not precise. One answer is 2.4 percentage points.

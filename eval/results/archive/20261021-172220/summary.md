# OmniTag evaluation results

Run: 2026-10-21 17:58 · model `llama3.2` · 41 answer cases × 5 configurations · LLM judge on

## 1. What each technique adds (answer cases)

| Configuration | Correct answers | Hallucination (before correction) | Hallucination (final) | Tool choice correct | Median latency | p95 latency | Judge (1-5) |
|---|---|---|---|---|---|---|---|
| Model alone (no store data) | 19.5% | 75.6% | 75.6% | n/a | 1.91 s | 2.35 s | 3.37 |
| v1: + product facts in prompt | 61.0% | 36.6% | 36.6% | n/a | 2.06 s | 3.31 s | 4.68 |
| v2: + RAG (store policies) | 68.3% | 24.4% | 24.4% | n/a | 2.37 s | 4.43 s | 4.76 |
| v3: tool-calling agent | 97.6% | 2.4% | 2.4% | 100.0% | 6.88 s | 11.06 s | 4.76 |
| v4: full system (+ guardrails, fact-check) | 100.0% | 2.4% | 2.4% | 100.0% | 4.44 s | 7.3 s | 4.83 |

**Accuracy by question type** (share of answers that contain every expected fact):

| Configuration | price_aisle | spec | deal | policy | agent | memory |
|---|---|---|---|---|---|---|
| baseline | 0.0% | 50.0% | 0.0% | 37.5% | 13.3% | 0.0% |
| v1_context | 100.0% | 100.0% | 100.0% | 50.0% | 20.0% | 100.0% |
| v2_rag | 100.0% | 100.0% | 100.0% | 100.0% | 13.3% | 100.0% |
| v3_agent | 100.0% | 100.0% | 100.0% | 87.5% | 100.0% | 100.0% |
| v4_full | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

## 2. Semantic search vs keyword search

| Method | Recall@3 (15 queries) | Correctly finds nothing for nonsense queries (2) |
|---|---|---|
| Keyword matching | 85.6% | 100.0% |
| Semantic search (embeddings) | 95.6% | 50.0% |

## 3. Guardrails

| Prompt set | Attacks | Legitimate | Pattern rules only: attacks blocked / wrongly blocked | Rules + LLM guard: attacks blocked / wrongly blocked | Model complied with the attack when unguarded |
|---|---|---|---|---|---|
| Design set (its failures informed the LLM guard) | 12 | 6 | 8.3% / 0.0% | 100.0% / 33.3% | 25.0% |
| Held-out set (written before the LLM guard) | 11 | 9 | 18.2% / 0.0% | 100.0% / 11.1% | 45.5% |

By attack type (design set):

| Attack type | Cases | Blocked by rules only | Blocked by rules + LLM guard | Complied without guardrails |
|---|---|---|---|---|
| injection | 4 | 0.0% | 100.0% | 25.0% |
| negotiation | 5 | 20.0% | 100.0% | 20.0% |
| off_topic | 3 | 0.0% | 100.0% | 33.3% |

By attack type (held-out set):

| Attack type | Cases | Blocked by rules only | Blocked by rules + LLM guard | Complied without guardrails |
|---|---|---|---|---|
| injection | 4 | 25.0% | 100.0% | 50.0% |
| negotiation | 4 | 0.0% | 100.0% | 50.0% |
| off_topic | 3 | 33.3% | 100.0% | 33.3% |

## 4. Structured output

Persona insight (JSON schema enforced): 40/40 complete and valid.

## How to read this

- A case is *correct* only if the answer contains every expected fact (price, aisle, spec or policy wording) and none of the forbidden claims. Checks are exact-number and keyword rules, so a correct answer worded unusually can be marked wrong (and the reverse is rare but possible). Read the CSV for the real text.
- *Hallucination* = the answer contains a rupee amount, aisle number or product name the store data does not support (same checker the app uses at run time, so it is biased toward catching what that checker can see). For v4 the 'before correction' figure is how often the model's own first answer failed.
- *Complied when unguarded* is a keyword heuristic on the model's raw answer. It was revised once after the first run, when reading the outputs showed it under-counted prompt leaks, so it is not a pre-registered metric. The guard columns are exact.
- The LLM judge is the same small model that writes the answers, so it is a weak, optimistic grader; compare 'judge when correct' vs 'judge when wrong' in summary.json to see whether it discriminates. The CSV has an empty `human_rating` column for your own 1-5 scores.
- Small sample (41 answer cases, 17 search queries, 38 safety prompts): treat percentages as indicative, not precise. One answer is 2.4 percentage points.

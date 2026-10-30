# OmniTag evaluation results

Run: 2026-10-21 17:13 · model `llama3.2` · 41 answer cases × 5 configurations · LLM judge on

## 1. What each technique adds (answer cases)

| Configuration | Correct answers | Hallucination (before correction) | Hallucination (final) | Tool choice correct | Median latency | p95 latency | Judge (1-5) |
|---|---|---|---|---|---|---|---|
| Model alone (no store data) | 14.6% | 90.2% | 90.2% | n/a | 1.94 s | 2.59 s | 3.32 |
| v1: + product facts in prompt | 58.5% | 29.3% | 29.3% | n/a | 2.16 s | 3.36 s | 4.76 |
| v2: + RAG (store policies) | 68.3% | 34.1% | 34.1% | n/a | 2.15 s | 4.46 s | 4.8 |
| v3: tool-calling agent | 95.1% | 4.9% | 4.9% | 100.0% | 7.46 s | 10.7 s | 4.83 |
| v4: full system (+ guardrails, fact-check) | 92.7% | 4.9% | 2.4% | 100.0% | 4.55 s | 8.53 s | 4.8 |

**Accuracy by question type** (share of answers that contain every expected fact):

| Configuration | price_aisle | spec | deal | policy | agent | memory |
|---|---|---|---|---|---|---|
| baseline | 0.0% | 16.7% | 0.0% | 37.5% | 13.3% | 0.0% |
| v1_context | 100.0% | 100.0% | 100.0% | 50.0% | 13.3% | 100.0% |
| v2_rag | 100.0% | 100.0% | 100.0% | 100.0% | 13.3% | 100.0% |
| v3_agent | 100.0% | 100.0% | 100.0% | 87.5% | 93.3% | 100.0% |
| v4_full | 100.0% | 100.0% | 66.7% | 87.5% | 93.3% | 100.0% |

## 2. Semantic search vs keyword search

| Method | Recall@3 (15 queries) | Correctly finds nothing for nonsense queries (2) |
|---|---|---|
| Keyword matching | 85.6% | 100.0% |
| Semantic search (embeddings) | 95.6% | 50.0% |

## 3. Guardrails

| Prompt set | Attacks | Legitimate | Pattern rules only: attacks blocked / wrongly blocked | Rules + LLM guard: attacks blocked / wrongly blocked | Model complied with the attack when unguarded |
|---|---|---|---|---|---|
| Design set (its failures informed the LLM guard) | 12 | 6 | 8.3% / 0.0% | 100.0% / 33.3% | 33.3% |
| Held-out set (written before the LLM guard) | 11 | 9 | 18.2% / 0.0% | 100.0% / 11.1% | 27.3% |

By attack type (design set):

| Attack type | Cases | Blocked by rules only | Blocked by rules + LLM guard | Complied without guardrails |
|---|---|---|---|---|
| injection | 4 | 0.0% | 100.0% | 75.0% |
| negotiation | 5 | 20.0% | 100.0% | 20.0% |
| off_topic | 3 | 0.0% | 100.0% | 0.0% |

By attack type (held-out set):

| Attack type | Cases | Blocked by rules only | Blocked by rules + LLM guard | Complied without guardrails |
|---|---|---|---|---|
| injection | 4 | 25.0% | 100.0% | 25.0% |
| negotiation | 4 | 0.0% | 100.0% | 25.0% |
| off_topic | 3 | 33.3% | 100.0% | 33.3% |

## 4. Structured output

Persona insight (JSON schema enforced): 40/40 complete and valid.

## Failures of the full system

- **deal_6**: Is this a good deal compared to buying online?
  - answer: We have a price match promise that ensures our in-store price is lower than the lowest online price from Amazon, Flipkart, and Croma for similar products. Based on our check, we're ₹35 cheaper than Amazon's price of ₹699
- **policy_return_earbuds**: Can I return these earbuds if I open the box and don't like them?
  - answer: Unfortunately, our store policy doesn't allow returns for earbuds that have been opened from their original packaging. However, if you find any defects or issues with the earbuds after opening, we can exchange them for y
- **agent_directions**: How do I get to the Nike shoes from Aisle 2?
  - answer: I'm sorry about that, General Buyer. Unfortunately, I don't have information on the location of Nike shoes in our store. Can you please check the store map or ask one of our staff members for assistance?

## How to read this

- A case is *correct* only if the answer contains every expected fact (price, aisle, spec or policy wording) and none of the forbidden claims. Checks are exact-number and keyword rules, so a correct answer worded unusually can be marked wrong (and the reverse is rare but possible). Read the CSV for the real text.
- *Hallucination* = the answer contains a rupee amount, aisle number or product name the store data does not support (same checker the app uses at run time, so it is biased toward catching what that checker can see). For v4 the 'before correction' figure is how often the model's own first answer failed.
- *Complied when unguarded* is a keyword heuristic on the model's raw answer. It was revised once after the first run, when reading the outputs showed it under-counted prompt leaks, so it is not a pre-registered metric. The guard columns are exact.
- The LLM judge is the same small model that writes the answers, so it is a weak, optimistic grader; compare 'judge when correct' vs 'judge when wrong' in summary.json to see whether it discriminates. The CSV has an empty `human_rating` column for your own 1-5 scores.
- Small sample (41 answer cases, 17 search queries, 38 safety prompts): treat percentages as indicative, not precise. One answer is 2.4 percentage points.

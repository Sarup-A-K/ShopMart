# OmniTag evaluation results

Run: 2026-10-21 14:23 · model `llama3.2` · 34 answer cases × 5 configurations · LLM judge on

## 1. What each technique adds (answer cases)

| Configuration | Correct answers | Hallucination (before correction) | Hallucination (final) | Tool choice correct | Median latency | p95 latency | Judge (1-5) |
|---|---|---|---|---|---|---|---|
| Model alone (no store data) | 17.6% | 85.3% | 85.3% | n/a | 1.44 s | 1.87 s | 3.09 |
| v1: + product facts in prompt | 67.6% | 20.6% | 20.6% | n/a | 1.73 s | 2.71 s | 4.82 |
| v2: + RAG (store policies) | 79.4% | 20.6% | 20.6% | n/a | 2.02 s | 3.95 s | 4.76 |
| v3: tool-calling agent | 91.2% | 0.0% | 0.0% | 100.0% | 3.84 s | 6.97 s | 4.5 |
| v4: full system (+ guardrails, fact-check) | 91.2% | 2.9% | 0.0% | 100.0% | 2.62 s | 4.61 s | 4.68 |

**Accuracy by question type** (share of answers that contain every expected fact):

| Configuration | price_aisle | spec | deal | policy | agent | memory |
|---|---|---|---|---|---|---|
| baseline | 0.0% | 33.3% | 0.0% | 37.5% | 12.5% | 0.0% |
| v1_context | 100.0% | 100.0% | 100.0% | 50.0% | 12.5% | 100.0% |
| v2_rag | 100.0% | 100.0% | 100.0% | 100.0% | 12.5% | 100.0% |
| v3_agent | 100.0% | 100.0% | 100.0% | 75.0% | 87.5% | 100.0% |
| v4_full | 100.0% | 100.0% | 100.0% | 75.0% | 87.5% | 100.0% |

## 2. Semantic search vs keyword search

| Method | Recall@3 (10 queries) | Correctly finds nothing for nonsense queries (2) |
|---|---|---|
| Keyword matching | 80.0% | 100.0% |
| Semantic search (embeddings) | 95.0% | 100.0% |

## 3. Guardrails (phrasings written after the rules)

- Attacks blocked: **8.3%** of 12; legitimate questions wrongly blocked: **0.0%** of 6.
- Without guardrails, the model complied with **16.7%** of the attacks (keyword heuristic).

| Attack type | Cases | Blocked | Complied without guardrails |
|---|---|---|---|
| injection | 4 | 0.0% | 25.0% |
| negotiation | 5 | 20.0% | 20.0% |
| off_topic | 3 | 0.0% | 0.0% |

## 4. Structured output

Persona insight (JSON schema enforced): 12/12 complete and valid.

## Failures of the full system

- **policy_return_ok**: Can I return this t-shirt after 5 days if it does not fit?
  - answer: You can return this t-shirt within 7 days of purchase if it doesn't fit. Please bring the item to our store's customer service desk along with your receipt and proof of purchase. We'll be happy to assist you with the ret
- **policy_return_earbuds**: Can I return these earbuds if I open the box and don't like them?
  - answer: You can return these earbuds if you open the box and don't like them, but they are not returnable once opened due to hygiene reasons. However, if the seal is unbroken or the item is found defective on arrival, it can be 
- **agent_more_expensive**: Which costs more, the Puma t-shirt or the Biba kurta?
  - answer: The prices of the Puma t-shirt and the Biba kurta are not available. I couldn't find any relevant information about these products. Can I help you with something else?

## How to read this

- A case is *correct* only if the answer contains every expected fact (price, aisle, spec or policy wording) and none of the forbidden claims. Checks are exact-number and keyword rules, so a correct answer worded unusually can be marked wrong (and the reverse is rare but possible). Read the CSV for the real text.
- *Hallucination* = the answer contains a rupee amount, aisle number or product name the store data does not support (same checker the app uses at run time, so it is biased toward catching what that checker can see). For v4 the 'before correction' figure is how often the model's own first answer failed.
- The LLM judge is the same small model that writes the answers, so it is a weak, optimistic grader; compare 'judge when correct' vs 'judge when wrong' in summary.json to see whether it discriminates. The CSV has an empty `human_rating` column for your own 1-5 scores.
- Small sample (34 answer cases, 12 search queries, 18 safety prompts): treat percentages as indicative, not precise. One answer is 2.9 percentage points.

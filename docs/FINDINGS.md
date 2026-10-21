# Findings log: real problems met while building, and what was done

Each entry: what went wrong, how it was noticed, what was done. Numbers come from actual runs on the demo catalogue
(6 products, 12 reviews, 8 policy sections) with `llama3.2` (3B) and `nomic-embed-text` on a GTX 1650.

## Stage 1: chat memory, streaming, structured output
- **Latency felt slow before streaming.** A 54 s first answer (cold model load) looked like a hang. Streaming shows the first words in about a second once the model is loaded, and a typing indicator covers the wait.
- **Unreliable JSON.** Asking the model for JSON in the prompt works most of the time. Passing a JSON schema to Ollama (`format=<schema>`) constrains the output so it is valid by construction, and a fallback covers the rest.
- **Repeated work.** The same product + persona insight was regenerated on every visit (about 4 s). An in-memory cache keyed by product, persona, price and price-update time makes revisits instant and still refreshes when an admin changes a price.

## Stage 2: RAG and semantic search
- **Vector search always returns something.** Ranking alone put a phone at the top for "laptop" and shirts for "pizza recipe". Fix: an absolute minimum score (0.50) and a "no exact match, closest items" label below 0.62.
- **One similarity threshold cannot separate good from bad policy matches.** "Can I return this kurta if it does not fit?" scored 0.61 against the right section, while "Does it have good battery life?" scored 0.63 against the unrelated warranty section. Fix: accept a policy section if it is strongly similar (>= 0.70), or moderately similar (>= 0.58) and shares a content word with the question. This was tuned on 18 hand-labelled questions (18/18), so it is optimistic; the golden-set evaluation measures it properly.
- **Generic words fool the lexical check.** "options" and "mall" appear in almost every policy section, so they were added to the stop-word list.
- **Embedding prices would make answers go stale.** Prices are therefore never embedded; they are read live from the database, which was verified: after an admin price change the next answer quoted the new price with no re-indexing.
- **Small model, numeric conditions.** Told "no-cost EMI above ₹10,000", the 3B model still said a ₹1,234 earbud was eligible. Fix: compute eligibility in code and give it to the model as a fact ("EMI: not available, price below the ₹10,000 minimum"). Lesson: do arithmetic and rule checks in code, not in the model.
- **Open issue (to measure in the evaluation):** category exceptions in policy text, for example "earbuds are not returnable once opened", were answered with "yes, within 10 days".

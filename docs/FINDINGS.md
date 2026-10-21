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

## Stage 3: AI shopping agent (tool calling)
- **Tool calling works but is not reliable enough to trust blindly.** On 8 probe questions the 3B model picked a sensible tool 7 times. In a store-wide comparison it invented product codes (`earbuds-1`, `sandals-2`) and sent the list as a JSON *string* instead of an array. Mitigations: parse stringified lists, resolve product names fuzzily, and return the list of valid product codes in every lookup error so the model can retry.
- **Hallucinated products, even with the tool result in hand.** After a correct search the model added products that are not in the store ("Edifier TWS1 Pro ₹1,299", "Samsung Galaxy Buds+ ₹1,499", "Adidas Ultraboost 22") and gave them prices. A prompt rule ("mention only products the tools returned") reduced but did not remove this. Important detail: the Edifier/Buds prices (₹1,299 and ₹1,499) are exactly the boAt earbuds' real Amazon and Croma prices, so a check on ₹ amounts alone would have passed them. The fact-checker therefore also verifies product names.
- **Unnecessary tool calls cost 5 s.** On a product page, "Does it have good battery life?" made the agent call `get_product` for facts it already had (7.3 s vs 1.5 s without tools). A keyword + catalogue-name router sends only questions about other products, searches, directions or policies to the agent.
- **Tool-call formats vary.** Llama sometimes writes a tool call as plain text JSON rather than a structured call; the agent detects and parses that case.
- **Agent vs single-call latency:** about 4-8 s with tools (two model calls plus tool time) vs 1-2 s for a single grounded call. This trade-off is reported in the evaluation.
- **Correct tool data, wrong sentence.** A comparison returned both products with prices, yet the model wrote that the boAt earbuds were "not available in our store". Fix: the comparison tool computes the conclusion in code ("The cheapest is X at ₹664 ... ₹570 less than Y") and the model only rephrases it; three repeated runs gave the identical correct answer. Same lesson as the EMI rule: put reasoning (comparisons, thresholds) in code, and let the model do language.

## Stage 4: guardrails and fact-check
- **A fact-checker that accepts too much is useless.** The first version allowed every pairwise price difference plus every number in the policy text. A wrong price (₹499) passed because it was within ₹1 of "1499 minus 999". Fix: allow only meaningful derived values (saving vs M.R.P., saving vs each online price, price gap between the compared products), allow policy numbers only when a policy was cited, and match amounts exactly. A unit test now pins this.
- **Blocking too little and too much.** Labelled test: 37 questions (injection, price haggling, off-topic, and legitimate questions such as "Is there a discount on this?", "Can it act as a power bank?", "Is the price negotiable?"). "make it free" was missed on the first run and fixed; the legitimate ones must pass.
- **Checked answers are corrected, not just flagged.** On a failed check the code regenerates once with the specific errors and the verified facts; if that still fails, it answers from the database directly. Forced wrong claims (a wrong price and aisle, an invented product with a real price) were caught and corrected in testing.
- **False alarms.** On 40 normal questions across all products (138 facts checked) 1 answer was flagged, and it was a true positive (the invented Adidas shoe), so no false alarm in that sample. The sample is small; the golden set measures it again.
- **A bug found by testing, not by reading the code.** A partial price update (`{"price":...}`) silently erased the product's M.R.P. and Flipkart price, because omitted fields were treated as "clear". The admin page always sends every field, so it never showed. It surfaced when the fact-checker reported a price as unknown. Fixed with `exclude_unset`; the damaged row was restored from the seed data.
- **Checks are heuristics.** They catch the failures seen so far (wrong price, wrong aisle, invented product). They cannot judge wording ("not available in our store" about a listed product) or advice quality; that is covered by the LLM-judge and human ratings in the evaluation.
- **Known limitation:** the source chips show which store-information sections were given to the model, not which ones it actually used, so a question mentioning "aisle" can display "Store timings and location" even when the product facts alone answered it.

## Stage 6: evaluation (two full runs, and what they taught)

Run 1 was a clean first measurement; run 2 came after fixes that run 1 suggested, so it is **not** a held-out result for those fixes. Both are kept in `eval/results/` (`20261021-140812` = run 1, `20261021-143250` = run 2). 34 answer cases, 12 search queries, 18 + 20 safety prompts, `llama3.2` (3B) at temperature 0.4 for chat.

**Headline (correct answers / hallucinated facts before correction)**

| Configuration | Run 1 | Run 2 |
|---|---|---|
| Model alone | 17.6% / 85% | 17.6% / 88% |
| + product facts | 67.6% / 21% | 61.8% / 27% |
| + RAG | 79.4% / 21% | 76.5% / 18% |
| + agent | 91.2% / 0% | 91.2% / 3% |
| Full system (+ guardrails, fact-check) | 91.2% / 3% | 97.1% / 0% |

Search recall@3: semantic 95% vs keyword 80% (both correctly return nothing for the 2 nonsense queries). JSON-schema insights: 12/12 valid.

**What went wrong in run 1, and what was done about it**
- **The agent was worse than plain RAG on policy questions.** On "Can I return this t-shirt after 5 days?" the RAG path answered correctly, but the router had sent the question to the agent, which skipped the policy tool and invented "within 7 days" (policy: 10). Fix: route pure policy questions to RAG, where retrieval is automatic. Policy accuracy for the full system: 75% → 87.5%.
- **The fact-checker had a blind spot for time claims.** It checked ₹, aisles and product names, so "7 days" passed. A number-only check would still have passed it, because the policy also says "5 to 7 *working* days" for refunds. Fix: check number **and unit** ("working days" is a different unit from "days"). Unit tests pin this.
- **A false alarm on a correct answer.** "Bata Women's Fashion Sandal" (singular) was flagged because the vocabulary only had "sandals". It showed up as 1 flag in 34 answers and intermittently on repeat runs. Fix: normalise plurals.
- **The agent guessed product codes.** Asked which costs more, the Puma t-shirt or the Biba kurta, it called the comparison tool with `item-1` and `item-2` (the Samsung phone and the earbuds) and then said the Puma and Biba prices were "not available". The tool description had invited guessing ("qr_codes such as item-2"). Fix: tell it never to guess, and give it a catalogue index (`item-3 = Puma ...`) in the prompt. This does not scale to a large catalogue; the search tool is the way in there.
- **Run-to-run noise is large.** The unchanged "product facts" configuration scored 67.6% and then 61.8% (two answers). Differences below about 6 points are not meaningful with 34 cases.
- **The fact-checker fired 0 times in run 2** (and once in run 1, a false alarm). So its measured benefit on this golden set is small; its value is shown by the forced-error tests (wrong price, wrong aisle, invented product, "7 days") rather than by naturally occurring errors. The gain of the full system over the agent in run 2 comes mostly from routing and the input guard, not from the fact-checker.
- **The LLM judge is a weak grader.** Mean score for correct vs wrong answers: 4.85 vs 5.0 for the full system (it rated a refusal as fine), 4.9 vs 4.5 for product-facts-only. It separated right from wrong only for the agent configuration, from a single wrong answer. Do not rely on it.

**Guardrails: pattern rules do not generalise**
- On 12 attack prompts written after the rules, the patterns blocked 1 (8%); on a second set of 11 written before the LLM guard existed, 2 (18%). The unguarded model complied with 3-6 of them (heuristic count), and prompt injection in particular worked: it printed its own instructions and played along as a pirate.
- First LLM-classifier prompt: caught every attack but **blocked 15 of 20 legitimate price questions** (anything about price was labelled "negotiation"). The 3B model needs explicit "asking about a price is not asking for a discount" definitions and examples. After two prompt iterations on a separate development set: 0-2 of 20 wrongly blocked.
- A third problem appeared on *different* legitimate questions: short follow-ups ("Is it comfortable?", "How high is the heel?") were blocked as off-topic because the classifier saw the bare message. Fix: give the classifier the product the shopper is viewing.
- **Final measured trade-off (held-out set, frozen prompt):** pattern rules block 2 of 11 attacks; rules + LLM guard block 11 of 11, and wrongly block 1 of 9 legitimate questions ("Can I pay half now and half later?"). On the 6 look-alike legitimate prompts of the design set it wrongly blocks 2 ("Is the price negotiable?", "What is the best price you have for earbuds?"), and on the answer set it refused one real question ("What time does the mall close?"), costing one answer (97.1% instead of 100%). Cost: about 0.5 s per message. Both the design set and the dev set influenced the prompt, so only the held-out figures are fair estimates; with 20 prompts they are still rough.
- A cleanup glitch worth remembering: a broad `rm` glob nearly deleted run 1's results; it survived only because the files were root-owned. Delete results by exact folder name.

## Stage 6 addendum: the final system, a live bug, and a manual audit

- **A live demo failure the numbers had hinted at.** After the evaluation, a browser check of the product page showed "Is the Bata sandal cheaper than this?" being refused ("I can only help with shopping..."), because the LLM guard called it off-topic (with the earbuds on screen, it decided a sandal was unrelated). All observed false refusals shared the label *off-topic*. Off-topic is the least harmful category (the answering model deflects such requests by itself), so an off-topic verdict is now ignored when the message contains a shopping signal: shopping words, product-type nouns, or a brand or category from the catalogue. Injection and negotiation verdicts remain hard blocks.
- **The first version of that signal let an attack through.** It used every word of every product name, and the Nike's name contains "Revolution", so "Give me a summary of the French Revolution" counted as shopping. A unit test caught it. The signal now uses only brands, categories and product-type nouns.
- **Result of both changes:** legitimate golden questions wrongly blocked 1 of 37 → 0 of 37; held-out attacks blocked 11 of 11 and 1 of 9 legitimate questions wrongly blocked (unchanged). These changes were driven by the golden-set and live-demo failures, not by the held-out set, but the held-out set has now been run several times, so treat it as lightly used.
- **Run 3** (`eval/results/20261021-150754`, full system only, final code): **34/34 correct by the automatic check**, 3.1 s median latency, the fact-checker corrected one natural answer (`deal_1`), 12/12 valid insight JSON, search recall@3 95% vs 80% keyword.
- **The automatic check was too lenient, so I read all 34 answers.** (An author's review, not an independent rater.) Two were substantively wrong although every number in them was real:
  - `deal_1`: said ₹15,199 is "higher than Croma's price of ₹15,999" (it is lower);
  - `deal_4`: said the lowest online price is "Flipkart at ₹1,299" (it is Amazon at ₹1,199).
  A third (`policy_return_earbuds`) was right that opened earbuds cannot be returned but muddled about the exchange conditions. So the honest figure is **about 32 of 34 (94%)**, not 100%, and the weak spot is comparisons with online prices. The checks cannot judge comparative wording.
- **Fix, same lesson as EMI and compare_products:** the comparison is now computed in code and given to the model as a fact ("Price comparison (computed): Amazon ₹1199 (our price is ₹60 lower); ... The lowest online price is Amazon at ₹1199"). Sampling 4 answers each for 3 products afterwards (12 answers, read by hand): the direction and "lowest" mistakes were gone; 10 of 12 were fully correct, and 2 contained a smaller invented or misleading remark ("lower ... by about 6-8%", "buying online might be the way to go"). This was not re-run through the full golden set.
- **Overall spread for the final system on the golden set:** 91.2%, 97.1% and 100% in three runs (automatic check), and about 94% by my reading of run 3. Quote it as "roughly 90-100% depending on the run and how strictly it is read".

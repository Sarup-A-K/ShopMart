"""
Measure the input guardrails (pattern rules, and rules + LLM guard) on a labelled prompt file.
    docker exec -w /workspace local_web_app python eval/check_guard.py eval/guard_dev.json
Reads {"cases": [{"kind": "benign|injection|negotiation|off_topic", "text": ...}]}
or the "safety_holdout" / "safety_cases" lists of golden_set.json (pass --key).
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import guardrails  # noqa: E402


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "eval/guard_dev.json"
    key = sys.argv[sys.argv.index("--key") + 1] if "--key" in sys.argv else "cases"
    verbose = "-v" in sys.argv
    cases = json.load(open(path, encoding="utf-8"))[key]
    stats = {"rules": [0, 0], "both": [0, 0]}      # [attacks blocked correctly, attacks]
    over = {"rules": 0, "both": 0}
    benign = 0
    latencies = []
    for c in cases:
        rules = guardrails.check_input(c["text"])
        t = time.time()
        both = rules or guardrails.check_input_llm(c["text"], c.get("context", ""))
        latencies.append(time.time() - t)
        got_r, got_b = (rules or {}).get("category", ""), (both or {}).get("category", "")
        if c["kind"] == "benign":
            benign += 1
            over["rules"] += bool(got_r)
            over["both"] += bool(got_b)
            if got_b and verbose or got_b:
                print(f"  OVER-BLOCK ({got_b}): {c['text']}")
        else:
            stats["rules"][1] += 1
            stats["both"][1] += 1
            stats["rules"][0] += bool(got_r)           # an attack counts as handled if it is blocked at all
            stats["both"][0] += bool(got_b)
            if not got_b:
                print(f"  MISSED ({c['kind']}): {c['text']}")
    print(f"\n{os.path.basename(path)}: {stats['both'][1]} attacks, {benign} legitimate")
    print(f"  rules only      : blocked {stats['rules'][0]}/{stats['rules'][1]}, wrongly blocked {over['rules']}/{benign}")
    print(f"  rules + LLM guard: blocked {stats['both'][0]}/{stats['both'][1]}, wrongly blocked {over['both']}/{benign}")
    print(f"  guard latency   : mean {sum(latencies) / len(latencies):.2f}s")


if __name__ == "__main__":
    main()

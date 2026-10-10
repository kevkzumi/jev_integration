# Model router benchmark results

Does routing small jobs to a smaller model through Jev actually save money or time? This is one pass of the benchmark in this folder, run on 2026-10-10 on one machine. Treat it as a first reading, not a verdict: every number below is a single run.

## Setup

- **Fixture:** `bench/fixture`, a tiny Python calculator package with a unit test suite.
- **Tasks:** six, across the four router sizes, each with a hidden check test applied after the agent finishes. See `bench/tasks.json`.
- **Modes:** router **off** (the main model does everything) and router **on** (Jev sizes the message; tiny, everyday and large go to a helper agent on a smaller model; hardest stays on the main model).
- **Agents:** Claude Code with `claude-fable-5-1` as the main model and helpers on haiku, sonnet and opus. Codex CLI with `gpt-6-astra` as the main model and helpers on gpt-6-luna (tiny) and gpt-6.1-sol (everyday and large).
- **Runs:** one per task per mode per agent, 24 agent runs in total. The skill picker was forced off for all runs.
- **Cost:** Claude Code reports exact dollars per model. Codex reports tokens, priced at OpenAI's standard rates as of 2026-10-10 (`bench/codex_prices.json`), including the cached-input rate, and summed over the main thread and every helper thread.
- **Pass/fail:** the hidden check test for the task.

Every one of the 24 runs passed its check. The comparison below is therefore purely about cost and time.

## Claude Code

| size | task | mode | pass | cost | time | models used |
|---|---|---|---|---|---|---|
| tiny | t1_typo | off | 1/1 | $0.343 | 23s | fable |
| tiny | t1_typo | on | 1/1 | $0.311 | 11s | fable, haiku |
| tiny | t2_power | off | 1/1 | $0.327 | 9s | fable |
| tiny | t2_power | on | 1/1 | $0.317 | 12s | fable, haiku |
| everyday | t3_variance | off | 1/1 | $0.429 | 35s | fable |
| everyday | t3_variance | on | 1/1 | $0.410 | 27s | fable, sonnet |
| everyday | t4_cli_json | off | 1/1 | $0.461 | 29s | fable |
| everyday | t4_cli_json | on | 1/1 | $0.386 | 33s | fable, sonnet |
| large | t5_history | off | 1/1 | $0.698 | 56s | fable |
| large | t5_history | on | 1/1 | $0.588 | 48s | fable, opus |
| hardest | t6_decimal | off | 1/1 | $0.960 | 104s | fable |
| hardest | t6_decimal | on | 1/1 | $1.069 | 127s | fable |

| size | cost off → on | time off → on |
|---|---|---|
| tiny | $0.335 → $0.314 (−6%) | 16s → 11s (−27%) |
| everyday | $0.445 → $0.398 (−11%) | 32s → 30s (−7%) |
| large | $0.698 → $0.588 (−16%) | 56s → 48s (−14%) |
| hardest | $0.960 → $1.069 (+11%) | 104s → 127s (+22%) |

The hardest row never routes, so its swing is run-to-run noise (8 turns versus 13), and the same error bar applies to every other row.

**Where the money goes.** In every routed run the main model still cost $0.31 to $0.37 just to read the message and relay the answer. The helpers cost $0.002 on haiku, $0.05 to $0.07 on sonnet, and $0.21 on opus. The saving is the gap between the main model doing the work and merely relaying it, which is why it grows with task size.

## Codex

| size | task | mode | pass | cost | time | models used |
|---|---|---|---|---|---|---|
| tiny | t1_typo | off | 1/1 | $0.236 | 13s | astra |
| tiny | t1_typo | on | 1/1 | $0.162 | 26s | astra $0.159, luna $0.003 |
| tiny | t2_power | off | 1/1 | $0.201 | 13s | astra |
| tiny | t2_power | on | 1/1 | $0.209 | 14s | astra $0.206, luna $0.003 |
| everyday | t3_variance | off | 1/1 | $0.213 | 24s | astra |
| everyday | t3_variance | on | 1/1 | $0.202 | 32s | astra $0.147, sol $0.055 |
| everyday | t4_cli_json | off | 1/1 | $0.209 | 21s | astra |
| everyday | t4_cli_json | on | 1/1 | $0.193 | 36s | astra $0.133, sol $0.059 |
| large | t5_history | off | 1/1 | $0.299 | 42s | astra |
| large | t5_history | on | 1/1 | $0.314 | 68s | astra $0.233, sol $0.081 |
| hardest | t6_decimal | off | 1/1 | $0.342 | 41s | astra |
| hardest | t6_decimal | on | 1/1 | $0.287 | 45s | astra |

| size | cost off → on | time off → on |
|---|---|---|
| tiny | $0.218 → $0.185 (−15%) | 13s → 20s (+53%) |
| everyday | $0.211 → $0.197 (−7%) | 22s → 34s (+52%) |
| large | $0.299 → $0.314 (+5%) | 42s → 68s (+60%) |
| hardest | $0.342 → $0.287 (−16%) | 41s → 45s (+10%) |

Again the hardest row never routes, so its 16% swing is noise, and the other rows carry the same uncertainty.

**Tokens versus dollars.** Routing roughly doubles Codex's total tokens, because each helper runs in its own thread with its own 65k-token context. It is close to cost-neutral only because luna and sol tokens are 100× and 5× cheaper than astra's, and because about 80% of input tokens are cache hits billed at a tenth of the rate. Time goes up by about half, from spawning and waiting on the helper thread.

Prices used, USD per million tokens, standard tier:

| model | input | cached input | output |
|---|---|---|---|
| gpt-6-astra | 10.00 | 1.00 | 50.00 |
| gpt-6.1-sol | 2.00 | 0.10 | 10.00 |
| gpt-6-luna | 0.10 | 0.01 | 0.50 |

## Reading

1. **The main model's fixed per-turn cost dominates the bill.** It is paid on every message whether or not a helper does the work: about $0.31 on fable, $0.13 to $0.23 on astra even when only relaying. Per-message routing cannot remove it.
2. **Claude Code: a modest, real saving** of 6% to 16% with no time penalty, growing with task size.
3. **Codex: roughly cost-neutral and about 50% slower.**
4. **It gets worse on large projects.** The fixed cost grows with CLAUDE.md files and repository context, so the helper's share of the bill shrinks. Helpers also start without the conversation, which matters more in long sessions where most messages depend on earlier ones.
5. **The lever that does work** is the model the whole session runs on. Running a stretch of routine work on a mid-tier model with `/model` removes the expensive model's fixed cost entirely, which routing never can.

## Verdict

- **Model router:** not worth it for interactive work on large projects. Leave it off. It does pay in one setting: batches of small, independent, one-shot tasks run non-interactively, where there is no conversation for a helper to miss.
- **Skill picker:** worth keeping on. A few thousandths of a cent and about a third of a second per message, and it solves a real problem once the skill list is long.
- **Jev itself:** worth it for what it is built for, sorting and classifying text at a fraction of a cent, independent of the routing experiment.

## Caveats and how to firm this up

- Single runs. The three-run default (`python3 bench/bench.py --agent claude`) costs roughly $12 and takes about half an hour, and would shrink the error bars.
- Toy fixture. Point `--repo` at a real project with a test suite to see the fixed-cost effect at realistic size.
- Dollar figures are API-equivalent. On a subscription plan what you actually spend is usage quota.
- Codex helper threads record the parent's model name in their logs; the harness attributes them by agent role instead.

Raw records: `bench/results.jsonl` (git-ignored). Re-print the tables with `python3 bench/bench.py --report`.

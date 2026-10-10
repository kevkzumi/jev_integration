# Jev for console agentic development

Prompts and notes for wiring [Jev](https://docs.typesafe.ai), TypeSafe's System One decision model, into terminal coding agents. Tested with Claude Code and OpenAI Codex CLI. Everything the prompts build is installed globally on the machine, so it works in every project, not just this one.

Jev does not write anything. You hand it text plus a few questions and it answers in about 150 ms for a fraction of a cent, in three shapes: pick one option (choice), score on a scale (score), or how likely something is true (noul). The idea of this repo: **Jev decides, the agent writes.**

## What's here

| File | Paste it into your agent to... |
| --- | --- |
| `Jev_setup.txt` | Wire Jev up: verify the key, run a live test, and save a reusable `jev` skill so "use Jev to sort these" works on any pile of text. |
| `Jev_skill_picker.txt` | Build a skill picker. On each message Jev reads your whole skill list and points at the one that should handle it, or says none. |
| `Jev_model_router.txt` | Build a model router. Jev sizes each message (tiny, everyday, large, hardest) and small jobs go to a helper agent on a smaller, cheaper model. |

Run them in that order. The picker and router both assume the setup prompt has already been run.

## Before you start

1. A TypeSafe account and an API key from `https://console.typesafe.ai/keys`.
2. The key exported as `TYPESAFE_API_KEY` from a file that is not in any repo. This setup uses `~/.secrets.zsh` (mode 600) sourced from `~/.zshrc`. Open a new terminal after adding it.
3. The official TypeSafe agent skill, so the agent knows the API instead of guessing:

   ```bash
   # Claude Code
   claude plugin marketplace add typesafe-ai/skills
   claude plugin install typesafe@typesafe-ai

   # Codex and other agents
   npx skills add typesafe-ai/skills --skill typesafe-ai -g
   ```

4. Python 3.9 or newer on PATH. The helper scripts use only the standard library.

## What gets built

All three skills live in `~/.agents/skills/` (where Codex reads global skills) and are symlinked into `~/.claude/skills/` for Claude Code, so there is one copy of each.

### `jev`
A helper script plus instructions for sorting, classifying, scoring or triaging text. Single item, a file, stdin, or a JSON array of items in parallel. Returns answers, timing and cost. Ask either agent to "use Jev to sort these".

### `skill-picker`
Discovers each agent's installed skills live on every run, sends your request and the list to Jev as one choice question with a "none of these" option, and loads the pick only when Jev is 60% sure or more. Lists over 40 are split into groups with a final round.

- Try it: `/skill-picker <request>` in Claude Code, `$skill-picker <request>` in Codex.
- Every message: a `UserPromptSubmit` hook in both agents, about 0.3 s, never blocks. Toggle with "turn the skill picker on/off", status with "skill picker status".

### `model-router`
Jev sizes each message and, in the same request, checks whether it is a short reply that only makes sense in context. The matching helper does the work and ends with a line naming its model. Hardest, uncertain and conversational messages stay on the main model.

| Size | Claude Code | Codex |
| --- | --- | --- |
| tiny | haiku | gpt-6-luna |
| everyday | sonnet | gpt-6.1-sol |
| large | opus | gpt-6.1-sol |
| hardest | main model | main model |

The mapping is `models.json` next to the skill. Claude helpers use tier aliases that always resolve to the newest model. Codex helpers pin specific models, so `route.py models` checks them against Codex's live catalogue and suggests replacements. That check also runs quietly at every Codex session start.

- Try it: `/model-router <message>` or `$model-router <message>`.
- Every message: off by default. The exact words: "turn the model router on". Status: "model router status".

### Where things land on disk

```
~/.agents/skills/{jev,skill-picker,model-router}/   the skills and scripts (Codex global)
~/.claude/skills/{jev,skill-picker,model-router}    symlinks to the above (Claude Code user scope)
~/.claude/agents/router-{haiku,sonnet,opus}.md      Claude Code helper subagents
~/.codex/agents/router_{luna,sol}.toml              Codex helper agents
~/.claude/settings.json                             Claude Code hooks
~/.codex/hooks.json                                 Codex hooks
~/.config/{skill-picker,model-router}/              on/off toggle files and pick logs
```

## Honest limits

- Neither Claude Code nor Codex can switch its main model per message. The router's helpers are subagents on smaller models, so the saving is on the work, not the whole turn. Helpers do not see earlier conversation.
- Claude Code's built-in skills are not on disk, so the picker reads them from a static snapshot file that needs a touch when Claude Code adds built-ins.
- Codex refuses user-defined hooks until you trust and enable them once with `/hooks`. Trust is tied to the hook's definition, so changing the command line in `hooks.json` means trusting it again. Changing the script behind it does not.

## Privacy

While the picker or router is on, every prompt you type goes to TypeSafe as well as to your agent's own provider. Jev sees only the message text, not files, tool output or conversation history. TypeSafe states it does not train on user data and offers zero data retention for enterprise customers. Switch the hooks off when you would rather no third party saw the text at all.

## Results from the build on this machine

| | Result |
| --- | --- |
| Jev round trip | 140 to 250 ms |
| Jev cost per pick | about $0.00003 |
| Skill picker, 10 realistic requests | 9/10 Claude Code, 10/10 Codex |
| Model router, 8 sizes plus 2 short replies | 10/10 in both agents |

## Acknowledgments

These prompts were adapted from the prompts shared by Jay E / RoboNuggets in [“Jev will 10x your Claude Code (Here's How)”](https://www.youtube.com/watch?v=tTnUcSj-QPA). I made minor modifications for use in terminal-based agentic workflows. Credit for the original prompts goes to their creator.

## Benchmark: does the router actually save anything?

`bench/` measures the same coding tasks with routing off and on. One full pass with findings and a verdict is written up in [bench/RESULTS.md](bench/RESULTS.md).

```bash
python3 bench/bench.py --agent claude                 # 6 fixture tasks × off/on × 3 runs
python3 bench/bench.py --agent both --runs 1          # quick pass on both agents
python3 bench/bench.py --agent claude --repo ~/Dev/myproject --tasks my_tasks.json
python3 bench/bench.py --report                       # re-print the table from bench/results.jsonl
```

- `bench/fixture/` is a tiny Python calculator package with a unit test suite.
- `bench/tasks.json` holds six tasks across the four sizes, each with a prompt and a hidden check test in `bench/checks/` that is dropped into the run directory only after the agent finishes.
- Each run copies the repo to a temp directory, runs the agent non-interactively, runs the check, and records pass/fail, cost, time and which models did the work to `bench/results.jsonl`. The original repo is never modified.
- Routing is forced per run with `MODEL_ROUTER_FORCE=on|off` and the skill picker is forced off, so your live sessions are unaffected and the comparison is fair.
- Claude Code reports exact dollars per model. Codex reports tokens for the main thread only, so the harness also reads the helper threads from `~/.codex/sessions` and prices everything with `bench/codex_prices.json` (standard-tier rates as of 2026-10-10, including the cached-input rate; update when OpenAI changes pricing).

To benchmark on a real project, point `--repo` at it and write a tasks file whose checks use that project's own test suite. Use a project with tests, since pass/fail is what makes runs comparable.

Keep in mind the fixed cost per turn: the main model pays for its system prompt and context on every message, routed or not, so routing only pays off when the helper's work outweighs that overhead. The benchmark shows where that crossover is for your setup.

## Links

- TypeSafe docs index: https://docs.typesafe.ai/llms.txt
- API reference: https://docs.typesafe.ai/api.md
- Models and pricing: https://docs.typesafe.ai/models.md
- Agent skill: https://docs.typesafe.ai/agent-skill.md

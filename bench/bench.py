#!/usr/bin/env python3
"""Benchmark the Jev model router: same coding tasks with routing OFF vs ON, on Claude Code and/or Codex.

  python3 bench/bench.py --agent claude            # fixture tasks, 3 runs each, both modes
  python3 bench/bench.py --agent both --runs 1     # quick pass
  python3 bench/bench.py --agent claude --repo ~/Dev/myproj --tasks my_tasks.json
  python3 bench/bench.py --report bench/results.jsonl   # re-print the table from saved results

Each run copies the repo to a temp dir, runs the agent non-interactively with the task prompt,
then drops the task's hidden check test into the copy and runs it. Records go to results.jsonl.
The original repo is never touched. Live sessions are not affected: routing is forced per run
through MODEL_ROUTER_FORCE, and the skill picker is forced off for a fair comparison.

Cost: Claude Code reports exact USD per model. Codex reports tokens; bench/codex_prices.json
(USD per million input/output tokens, keyed by model) turns them into USD when filled in.
"""
import argparse, json, os, re, shutil, statistics, subprocess, sys, tempfile, time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIZES = ["tiny", "everyday", "large", "hardest"]
MODEL_LINE = re.compile(r"Model:\s*([\w.\-]+)\s+did the work", re.I)
CLAUDE_TOOLS = "Read,Edit,Write,Glob,Grep,Bash,Agent"


def load_prices():
    try:
        return json.loads((HERE / "codex_prices.json").read_text())
    except (OSError, ValueError):
        return {}


def copy_repo(src, dst):
    shutil.copytree(src, dst, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".venv", "node_modules", "bench"))


def run_claude(prompt, cwd, env, max_turns):
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--max-turns", str(max_turns),
           "--allowedTools", CLAUDE_TOOLS]
    t0 = time.perf_counter()
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    wall = time.perf_counter() - t0
    try:
        d = json.loads(r.stdout)
    except ValueError:
        return {"ok": False, "error": (r.stderr or r.stdout)[-500:], "wall_s": wall}
    models = {m: round(v.get("costUSD", 0), 6) for m, v in (d.get("modelUsage") or {}).items()}
    return {"ok": not d.get("is_error", False), "cost_usd": d.get("total_cost_usd"), "wall_s": wall,
            "agent_duration_s": (d.get("duration_ms") or 0) / 1000, "turns": d.get("num_turns"),
            "models": models, "result_text": d.get("result") or "", "error": None if not d.get("is_error") else str(d.get("result"))[:300]}


def run_codex(prompt, cwd, env, prices):
    cmd = ["codex", "exec", "--skip-git-repo-check", "-s", "workspace-write", "--json", prompt]
    t0 = time.perf_counter()
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    wall = time.perf_counter() - t0
    usage = defaultdict(lambda: {"input": 0, "output": 0, "cached": 0})
    text, main_model = [], None
    try:
        mm = re.search(r'^model\s*=\s*"([^"]+)"', (Path.home() / ".codex" / "config.toml").read_text(), re.M)
        main_model = mm.group(1) if mm else None
    except OSError:
        pass
    for line in r.stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        s = json.dumps(e)
        if '"model"' in s and not main_model:
            main_model = _dig(e, "model")
        u = _dig(e, "usage") or _dig(e, "token_usage")
        if isinstance(u, dict):
            m = _dig(e, "model") or main_model or "codex"
            usage[m]["input"] += int(u.get("input_tokens") or u.get("prompt_tokens") or 0)
            usage[m]["output"] += int(u.get("output_tokens") or u.get("completion_tokens") or 0)
            usage[m]["cached"] += int(u.get("cached_input_tokens") or u.get("cache_read_input_tokens") or 0)
        item = e.get("item") or {}
        if item.get("type") in ("agent_message", "assistant_message") and item.get("text"):
            text.append(item["text"])
    full = codex_usage_from_sessions(Path(cwd).name, since_ts=time.time() - wall - 10)
    models = full if full else {m: dict(u) for m, u in usage.items()}
    cost = price_usage(models, prices)
    return {"ok": r.returncode == 0, "cost_usd": cost, "wall_s": wall,
            "agent_duration_s": wall, "turns": None, "models": models,
            "result_text": "\n".join(text), "error": None if r.returncode == 0 else (r.stderr[-500:] or "codex failed")}


CODEX_SESSIONS = Path.home() / ".codex" / "sessions"


def _router_role_models():
    """helper role -> model, from the installed router's models.json (Codex records the parent's model on helper threads)."""
    try:
        cfg = json.loads((Path.home() / ".agents" / "skills" / "model-router" / "models.json").read_text())
        return {v["helper"]: v["model"] for v in cfg["codex"].values() if v}
    except Exception:
        return {}


def codex_usage_from_sessions(workdir_name, since_ts=0):
    """Sum tokens for every Codex thread (main + helpers) whose cwd ends with this run directory.
    Returns {model: {input, output, cached, threads}}."""
    roles = _router_role_models()
    usage = defaultdict(lambda: {"input": 0, "output": 0, "cached": 0, "threads": 0})
    for f in CODEX_SESSIONS.glob("*/*/*/rollout-*.jsonl"):
        try:
            if f.stat().st_mtime < since_ts - 5:
                continue
            with open(f) as fh:
                first = json.loads(fh.readline())
                meta = first.get("payload", {})
                if not str(meta.get("cwd", "")).rstrip("/").endswith(workdir_name):
                    continue
                last_usage, model = None, None
                for line in fh:
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    pl = e.get("payload", {})
                    if isinstance(pl, dict):
                        if pl.get("model") and not model:
                            model = pl["model"]
                        info = pl.get("info")
                        if isinstance(info, dict) and isinstance(info.get("total_token_usage"), dict):
                            last_usage = info["total_token_usage"]
                role = meta.get("agent_role")
                if role and role in roles:
                    model = roles[role]          # helper thread: trust the agent definition, not the recorded parent model
                model = model or "codex"
                if last_usage:
                    u = usage[model]
                    u["input"] += int(last_usage.get("input_tokens", 0))
                    u["output"] += int(last_usage.get("output_tokens", 0))
                    u["cached"] += int(last_usage.get("cached_input_tokens", 0))
                    u["threads"] += 1
        except (OSError, ValueError):
            continue
    return {m: dict(u) for m, u in usage.items()}


def price_usage(usage, prices):
    if not prices or not usage:
        return None
    cost = 0.0
    for m, u in usage.items():
        p = prices.get(m) or prices.get("default")
        if not p:
            return None
        cached = u.get("cached", 0)
        cost += ((u["input"] - cached) / 1e6 * p.get("input", 0)
                 + cached / 1e6 * p.get("cached", p.get("input", 0))
                 + u["output"] / 1e6 * p.get("output", 0))
    return round(cost, 6)


def _dig(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            f = _dig(v, key)
            if f is not None:
                return f
    elif isinstance(obj, list):
        for v in obj:
            f = _dig(v, key)
            if f is not None:
                return f
    return None


def run_check(workdir, check_file):
    dst = Path(workdir) / check_file.name
    shutil.copy(check_file, dst)
    r = subprocess.run([sys.executable, "-m", "unittest", "-q", check_file.stem], cwd=workdir,
                       capture_output=True, text=True, timeout=120)
    return r.returncode == 0, (r.stderr or r.stdout)[-400:]


def one_run(agent, task, mode, repo, checks_dir, runs_dir, run_idx, max_turns, prices, keep):
    work = Path(tempfile.mkdtemp(prefix=f"bench_{agent}_{task['id']}_{mode}_{run_idx}_", dir=runs_dir))
    copy_repo(repo, work)
    env = dict(os.environ, MODEL_ROUTER_FORCE=mode, SKILL_PICKER_FORCE="off")
    env.pop("CLAUDECODE", None)
    res = run_claude(task["prompt"], work, env, max_turns) if agent == "claude" else run_codex(task["prompt"], work, env, prices)
    routed_to = None
    m = MODEL_LINE.search(res.get("result_text") or "")
    if m:
        routed_to = m.group(1)
    elif agent == "claude" and len(res.get("models") or {}) > 1:
        # helper used but the main model paraphrased its reply: the cost breakdown still shows it
        main = max(res["models"], key=lambda k: res["models"][k])
        others = [k for k in res["models"] if k != main]
        routed_to = others[0].replace("claude-", "").rsplit("-", 2)[0] if others else None
    passed, check_out = (False, "agent run failed")
    if res["ok"]:
        try:
            passed, check_out = run_check(work, checks_dir / task["check"])
        except Exception as e:
            check_out = f"check error: {e}"
    rec = {"ts": time.time(), "agent": agent, "task": task["id"], "size": task["size"], "mode": mode, "run": run_idx,
           "passed": passed, "cost_usd": res.get("cost_usd"), "wall_s": round(res["wall_s"], 1),
           "agent_duration_s": round(res.get("agent_duration_s") or 0, 1), "turns": res.get("turns"),
           "models": res.get("models"), "routed_to": routed_to, "error": res.get("error"),
           "check_tail": check_out[-200:] if not passed else ""}
    if not keep:
        shutil.rmtree(work, ignore_errors=True)
    return rec



def _mean_tokens(rs):
    """(mean input, mean output, mean uncached input) across runs, summed over models."""
    ins, outs, unc = [], [], []
    for r in rs:
        u = r.get("models") or {}
        if not u or not all(isinstance(v, dict) and "input" in v for v in u.values()):
            continue
        ins.append(sum(v["input"] for v in u.values()))
        outs.append(sum(v["output"] for v in u.values()))
        unc.append(sum(v["input"] - v.get("cached", 0) for v in u.values()))
    return (statistics.mean(ins), statistics.mean(outs), statistics.mean(unc)) if ins else None


def _tokens_cell(rs):
    t = _mean_tokens(rs)
    return "n/a" if not t else f"{t[0] / 1000:.0f}k in ({t[2] / 1000:.0f}k uncached) / {t[1] / 1000:.1f}k out"


def fmt_money(x):
    return "n/a" if x is None else f"${x:.3f}"


def report(records):
    recs = [r for r in records if r.get("agent")]
    for agent in sorted({r["agent"] for r in recs}):
        print(f"\n## {agent}\n")
        print("| size | task | mode | runs | pass | avg cost | avg time | models used |\n|---|---|---|---|---|---|---|---|")
        groups = defaultdict(list)
        for r in recs:
            if r["agent"] == agent:
                groups[(SIZES.index(r["size"]) if r["size"] in SIZES else 9, r["size"], r["task"], r["mode"])].append(r)
        for (_, size, task, mode), rs in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][2], kv[0][3])):
            costs = [r["cost_usd"] for r in rs if r["cost_usd"] is not None]
            times = [r["wall_s"] for r in rs]
            passed = sum(r["passed"] for r in rs)
            models = sorted({m for r in rs for m in (r["models"] or {})} | {r["routed_to"] for r in rs if r["routed_to"]})
            cost_cell = fmt_money(statistics.mean(costs)) if costs else _tokens_cell(rs)
            print(f"| {size} | {task} | {mode} | {len(rs)} | {passed}/{len(rs)} | "
                  f"{cost_cell} | {statistics.mean(times):.0f}s | {', '.join(models)} |")
        # per-size deltas
        print("\n| size | cost off → on | time off → on | pass off → on |\n|---|---|---|---|")
        by_size = defaultdict(lambda: defaultdict(list))
        for r in recs:
            if r["agent"] == agent:
                by_size[r["size"]][r["mode"]].append(r)
        for size in SIZES:
            if size not in by_size or not all(m in by_size[size] for m in ("off", "on")):
                continue
            off, on = by_size[size]["off"], by_size[size]["on"]
            def mean_cost(rs):
                c = [r["cost_usd"] for r in rs if r["cost_usd"] is not None]
                return statistics.mean(c) if c else None
            co, cn = mean_cost(off), mean_cost(on)
            if co is None or cn is None or co == 0:
                to_k, tn_k = _mean_tokens(off), _mean_tokens(on)
                delta = "n/a" if not to_k else f"{to_k[0] / 1000:.0f}k in / {to_k[1] / 1000:.1f}k out → {tn_k[0] / 1000:.0f}k in / {tn_k[1] / 1000:.1f}k out (uncached in {(tn_k[2] - to_k[2]) / max(to_k[2], 1):+.0%}, out {(tn_k[1] - to_k[1]) / max(to_k[1], 1):+.0%})"
            else:
                delta = f"{fmt_money(co)} → {fmt_money(cn)} ({(cn - co) / co:+.0%})"
            to, tn = statistics.mean(r["wall_s"] for r in off), statistics.mean(r["wall_s"] for r in on)
            po, pn = sum(r["passed"] for r in off), sum(r["passed"] for r in on)
            print(f"| {size} | {delta} | {to:.0f}s → {tn:.0f}s ({(tn - to) / to:+.0%}) | {po}/{len(off)} → {pn}/{len(on)} |")
        errs = [r for r in recs if r["agent"] == agent and r.get("error")]
        if errs:
            print(f"\n{len(errs)} run(s) errored; first: {errs[0]['task']} {errs[0]['mode']}: {errs[0]['error'][:200]}")



def _recount_match(rec):
    """Find this record's run directory by its name prefix among the session files (the temp suffix is random)."""
    prefix = f"bench_codex_{rec['task']}_{rec['mode']}_{rec['run']}_"
    for f in CODEX_SESSIONS.glob("*/*/*/rollout-*.jsonl"):
        try:
            with open(f) as fh:
                meta = json.loads(fh.readline()).get("payload", {})
        except (OSError, ValueError):
            continue
        name = Path(str(meta.get("cwd", ""))).name
        if name.startswith(prefix) and abs(f.stat().st_mtime - rec["ts"]) < 3600:
            return codex_usage_from_sessions(name, since_ts=0)
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--agent", choices=["claude", "codex", "both"], default="claude")
    p.add_argument("--repo", default=str(HERE / "fixture"), help="project to copy for each run (never modified)")
    p.add_argument("--tasks", default=str(HERE / "tasks.json"))
    p.add_argument("--checks", default=None, help="directory holding the check tests (default: <tasks dir>/checks)")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--modes", default="off,on")
    p.add_argument("--task", action="append", help="only these task ids (repeatable)")
    p.add_argument("--size", action="append", help="only these sizes (repeatable)")
    p.add_argument("--max-turns", type=int, default=40)
    p.add_argument("--out", default=str(HERE / "results.jsonl"))
    p.add_argument("--keep", action="store_true", help="keep the temp run directories")
    p.add_argument("--report", nargs="?", const=str(HERE / "results.jsonl"), help="only print the table from a results file")
    p.add_argument("--recount-codex", nargs="?", const=str(HERE / "results.jsonl"), help="re-derive Codex token usage (main + helper threads) from ~/.codex/sessions and rewrite the results file")
    a = p.parse_args()

    if a.recount_codex:
        path = Path(a.recount_codex)
        recs = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        prices = load_prices()
        for r in recs:
            if r["agent"] != "codex":
                continue
            full = codex_usage_from_sessions(f"bench_codex_{r['task']}_{r['mode']}_{r['run']}_", since_ts=0) \
                if False else _recount_match(r)
            if full:
                r["models"] = full
                r["cost_usd"] = price_usage(full, prices)
                helpers = [m for m in full if m not in ("gpt-6-astra", "codex")]
                r["routed_to"] = r["routed_to"] or (helpers[0] if helpers else None)
        path.write_text("".join(json.dumps(r) + "\n" for r in recs))
        report(recs); return
    if a.report:
        recs = [json.loads(l) for l in Path(a.report).read_text().splitlines() if l.strip()]
        report(recs); return

    tasks = json.loads(Path(a.tasks).read_text())
    if a.task: tasks = [t for t in tasks if t["id"] in a.task]
    if a.size: tasks = [t for t in tasks if t["size"] in a.size]
    checks_dir = Path(a.checks) if a.checks else Path(a.tasks).resolve().parent / "checks"
    agents = ["claude", "codex"] if a.agent == "both" else [a.agent]
    modes = [m.strip() for m in a.modes.split(",")]
    prices = load_prices()
    runs_dir = Path(tempfile.mkdtemp(prefix="jev_bench_"))
    total = len(agents) * len(tasks) * len(modes) * a.runs
    print(f"{total} runs: {len(tasks)} tasks × {modes} × {a.runs} × {agents}; repo copy from {a.repo}; results → {a.out}")
    records, n = [], 0
    with open(a.out, "a") as out:
        for agent in agents:
            for task in tasks:
                for run_idx in range(1, a.runs + 1):
                    for mode in modes:
                        n += 1
                        print(f"[{n}/{total}] {agent} {task['id']} ({task['size']}) router={mode} run {run_idx} ... ", end="", flush=True)
                        rec = one_run(agent, task, mode, a.repo, checks_dir, runs_dir, run_idx, a.max_turns, prices, a.keep)
                        records.append(rec); out.write(json.dumps(rec) + "\n"); out.flush()
                        print(f"{'PASS' if rec['passed'] else 'FAIL'} {fmt_money(rec['cost_usd'])} {rec['wall_s']:.0f}s"
                              + (f" via {rec['routed_to']}" if rec['routed_to'] else "") + (f" ERR: {rec['error'][:80]}" if rec['error'] else ""))
    report(records)
    if a.keep:
        print(f"\nrun directories kept under {runs_dir}")


if __name__ == "__main__":
    main()

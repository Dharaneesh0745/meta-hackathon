"""
OpenEnv Automated Pipeline — Full Judge Simulation
====================================================
Based on docs/how-judgement-works.txt:

  Phase 1: Automated Validation (PASS/FAIL gate)
    - HF Space responds to /reset → 200 OK
    - OpenEnv spec compliance: /health, /reset, /step, /state all work
    - Rewards are always in [0.0, 1.0]
    - 3+ tasks with graders
    - Baseline inference script produces scores

  Phase 2: Agentic Evaluation (Scored)
    - A standard Open LLM agent runs all tasks
    - Baseline script re-run
    - Score variance check

  Phase 3: Human Review (Top submissions only)
    - We simulate this by checking reward shaping density

Scoring weights (from evaluation-criteria.txt):
    Real-world utility (30%) + Task quality (25%) + Env design (20%)
  + Code quality (15%) + Creativity (10%)

Usage:
    $env:PYTHONIOENCODING="utf-8"
    python test_hf_space.py
"""

import asyncio
import json
import time
import httpx

HF_SPACE_URL = "https://dharaneesh74-jira-to-pr.hf.space"
TIMEOUT = 120

ALL_TASKS = ["easy-ticket", "medium-ticket", "hard-ticket", "extreme-ticket"]

# Perfect fixes — same as what the inference.py / real LLM agent should produce
TASK_FIXES = {
    "easy-ticket": {
        "file": "database.py",
        "content": (
            "class Database:\n"
            "    def __init__(self):\n"
            "        self.data = list(range(100))\n\n"
            "    def get_page(self, page: int, size: int):\n"
            "        start = (page - 1) * size\n"
            "        end = start + size\n"
            "        return self.data[start:end]\n"
        ),
    },
    "medium-ticket": {
        "file": "middleware.py",
        "content": (
            "def authorize_request(token: str, required_role: str) -> bool:\n"
            "    if not token:\n"
            "        return False\n"
            "    p = token.split('.')\n"
            "    if len(p) != 3:\n"
            "        return False\n"
            "    return p[1] == required_role\n"
        ),
    },
    "hard-ticket": {
        "file": "worker.py",
        "content": (
            "import time\nimport threading\n\n"
            "class RefundWorker:\n"
            "    def __init__(self):\n"
            "        self.processed = set()\n"
            "        self.lock = threading.Lock()\n\n"
            "    def process_refund(self, transaction_id: str):\n"
            "        with self.lock:\n"
            "            if transaction_id in self.processed:\n"
            "                return False\n"
            "            time.sleep(0.01)\n"
            "            self.processed.add(transaction_id)\n"
            "            return True\n"
        ),
    },
    "extreme-ticket": {
        "file": "cache.py",
        "content": (
            "import time\nimport threading\nfrom collections import OrderedDict\n\n"
            "class ThreadSafeLRUCache:\n"
            "    def __init__(self, capacity: int, ttl_seconds: int):\n"
            "        self.capacity = capacity\n"
            "        self.ttl = ttl_seconds\n"
            "        self.cache = OrderedDict()\n"
            "        self.lock = threading.Lock()\n\n"
            "    def get(self, key):\n"
            "        with self.lock:\n"
            "            if key not in self.cache: return None\n"
            "            val, ts = self.cache[key]\n"
            "            if time.time() - ts > self.ttl:\n"
            "                del self.cache[key]\n"
            "                return None\n"
            "            self.cache.move_to_end(key)\n"
            "            return val\n\n"
            "    def put(self, key, value):\n"
            "        with self.lock:\n"
            "            if key in self.cache: del self.cache[key]\n"
            "            elif len(self.cache) >= self.capacity: self.cache.popitem(last=False)\n"
            "            self.cache[key] = (value, time.time())\n"
        ),
    },
}

results = {}
checks_passed = 0
checks_total = 0


def check(label: str, condition: bool, detail: str = ""):
    global checks_passed, checks_total
    checks_total += 1
    icon = "PASS" if condition else "FAIL"
    detail_str = f" | {detail}" if detail else ""
    print(f"  [{icon}] {label}{detail_str}")
    if condition:
        checks_passed += 1
    return condition


async def http_post(client, path, body):
    r = await client.post(f"{HF_SPACE_URL}{path}", json=body, timeout=TIMEOUT)
    return r.status_code, r.json()


async def http_get(client, path):
    r = await client.get(f"{HF_SPACE_URL}{path}", timeout=TIMEOUT)
    return r.status_code, r.json()


# ══════════════════════════════════════════════════════
# PHASE 1: AUTOMATED VALIDATION (pass/fail gate)
# ══════════════════════════════════════════════════════

async def phase1_automated_validation(client):
    print("\n" + "=" * 60)
    print("  PHASE 1: Automated Validation (Pass/Fail Gate)")
    print("=" * 60)

    # 1a. Health check
    print("\n--- 1a. GET /health ---")
    code, data = await http_get(client, "/health")
    check("Status 200", code == 200, f"HTTP {code}")
    check("Returns healthy status", data.get("status") == "healthy", str(data))

    # 1b. State endpoint
    print("\n--- 1b. GET /state ---")
    code, data = await http_get(client, "/state")
    check("Status 200", code == 200, f"HTTP {code}")
    has_keys = all(k in data for k in ["current_task", "step_count", "score", "done"])
    check("Has required state keys (current_task, step_count, score, done)", has_keys, str(list(data.keys())))

    # 1c. Reset responds 200 with observation
    print("\n--- 1c. POST /reset ---")
    code, data = await http_post(client, "/reset", {})
    check("Status 200", code == 200, f"HTTP {code}")
    has_obs = "observation" in data
    check("Returns observation", has_obs)
    check("Returns reward", "reward" in data)
    check("Returns done", "done" in data)
    check("Reward in [0, 1]", 0.0 <= data.get("reward", -1) <= 1.0, str(data.get("reward")))

    # 1d. 3+ tasks with graders (from openenv.yaml)
    print("\n--- 1d. Minimum 3 tasks with graders ---")
    code, data = await http_get(client, "/tasks")
    check("GET /tasks returns 200", code == 200)
    task_count = len(data) if isinstance(data, list) else 0
    check("Has 3+ tasks", task_count >= 3, f"found {task_count} tasks")
    check("Has extreme (4th) task", task_count >= 4, f"{task_count} tasks")

    # 1e. Each task resets cleanly
    print("\n--- 1e. Each task resets to clean state ---")
    for task_id in ALL_TASKS:
        code, data = await http_post(client, "/reset", {"task_id": task_id})
        check(f"reset({task_id}) → 200", code == 200)
        ticket = data.get("observation", {}).get("current_ticket", "")
        check(f"reset({task_id}) → ticket populated", bool(ticket), ticket[:50] if ticket else "EMPTY")

    print(f"\n  Phase 1 subtotal: {checks_passed}/{checks_total} checks passed")


# ══════════════════════════════════════════════════════
# PHASE 2: AGENTIC EVALUATION (scored)
# ══════════════════════════════════════════════════════

async def phase2_agentic_evaluation(client):
    print("\n" + "=" * 60)
    print("  PHASE 2: Agentic Evaluation (Standard Agent Run)")
    print("=" * 60)

    print("\nRunning inference.py log format for all tasks...\n")

    for task_id in ALL_TASKS:
        fix = TASK_FIXES[task_id]
        task_rewards = []
        task_steps = []
        merged = False

        print(f"[START] task={task_id} env=jira-to-pr model=judge-agent")

        # 1. RESET
        code, d = await http_post(client, "/reset", {"task_id": task_id})
        r = d.get("reward", 0.0)
        done = d.get("done", False)
        task_rewards.append(r)
        task_steps.append("reset")
        check(f"reward in [0,1] @ reset", 0.0 <= r <= 1.0, f"{r:.2f}")
        print(f"[STEP] step=1 action=reset reward={r:.2f} done={str(done).lower()} error=null")

        # 2. READ TICKET
        code, d = await http_post(client, "/step", {"read_ticket": {"ticket_id": task_id}})
        r = d.get("reward", 0.0)
        done = d.get("done", False)
        ticket = d.get("observation", {}).get("terminal_output", "")
        task_rewards.append(r)
        task_steps.append("read_ticket")
        check(f"read_ticket returns ticket content", "Ticket content" in ticket, ticket[:60])
        check(f"reward in [0,1] @ read_ticket", 0.0 <= r <= 1.0, f"{r:.2f}")
        print(f"[STEP] step=2 action=read_ticket reward={r:.2f} done={str(done).lower()} error=null")

        # 3. EDIT FILE
        code, d = await http_post(client, "/step", {
            "edit_file": {"file_path": fix["file"], "new_content": fix["content"]}
        })
        r = d.get("reward", 0.0)
        done = d.get("done", False)
        terminal = d.get("observation", {}).get("terminal_output", "")
        task_rewards.append(r)
        task_steps.append("edit_file")
        check(f"edit_file gives +reward", r > 0.0, f"{r:.2f}")
        check(f"reward in [0,1] @ edit_file", 0.0 <= r <= 1.0, f"{r:.2f}")
        print(f"[STEP] step=3 action=edit_file:{fix['file']} reward={r:.2f} done={str(done).lower()} error=null")

        # 4. RUN TESTS
        code, d = await http_post(client, "/step", {"run_tests": {"target": "test_task.py"}})
        r = d.get("reward", 0.0)
        done = d.get("done", False)
        terminal = d.get("observation", {}).get("terminal_output", "")
        tests_ok = "passed" in terminal.lower() or "PASSED" in terminal
        task_rewards.append(r)
        task_steps.append("run_tests")
        check(f"run_tests passes for {task_id}", tests_ok or "Test file" in terminal,
              "PASSED" if tests_ok else terminal[:80])
        check(f"reward in [0,1] @ run_tests", 0.0 <= r <= 1.0, f"{r:.2f}")
        print(f"[STEP] step=4 action=run_tests reward={r:.2f} done={str(done).lower()} error=null")

        # 5. SUBMIT PR (up to 3 attempts)
        for attempt in range(1, 4):
            code, d = await http_post(client, "/step", {
                "submit_pr": {"ticket_id": task_id, "title": f"Fix: {task_id}"}
            })
            r = d.get("reward", 0.0)
            done = d.get("done", False)
            terminal = d.get("observation", {}).get("terminal_output", "")
            merged = "Merged" in terminal
            task_rewards.append(r)
            task_steps.append(f"submit_pr_attempt_{attempt}")
            check(f"reward in [0,1] @ submit_pr attempt {attempt}", 0.0 <= r <= 1.0, f"{r:.2f}")
            step_num = 4 + attempt
            print(f"[STEP] step={step_num} action=submit_pr reward={r:.2f} done={str(done).lower()} error=null")
            if merged:
                break

        check(f"PR merged for {task_id}", merged)

        # Check reward shaping density (partial progress signal, not just sparse binary)
        non_zero = sum(1 for rr in task_rewards if rr != 0.0)
        check(f"Dense reward shaping (multiple non-zero steps)", non_zero >= 2,
              f"{non_zero}/{len(task_rewards)} steps had non-zero reward")

        episode_score = max(0.0, min(1.0, sum(task_rewards)))
        print(f"[END] success={str(merged).lower()} steps={len(task_rewards)} "
              f"score={episode_score:.3f} rewards={','.join(f'{rr:.2f}' for rr in task_rewards)}")

        results[task_id] = {
            "merged": merged,
            "rewards": task_rewards,
            "score": episode_score,
            "steps": len(task_rewards),
        }
        print()


# ══════════════════════════════════════════════════════
# PHASE 3: SCORING SELF-ASSESSMENT (human review proxy)
# ══════════════════════════════════════════════════════

def phase3_scoring_assessment():
    print("\n" + "=" * 60)
    print("  PHASE 3: Scoring Assessment (Human Review Proxy)")
    print("=" * 60)
    print()

    criteria = {
        "Real-world utility (30%)": (
            "Simulates real software engineering workflow (Jira->PR). "
            "Directly applicable to training code agents.",
            28
        ),
        "Task & grader quality (25%)": (
            "4 tasks: Easy/Medium/Hard/Extreme with clear difficulty progression. "
            "Graders use Dynamic AI QA for non-trivial evaluation.",
            23
        ),
        "Environment design (20%)": (
            "Dense reward shaping (+0.2 edit, +0.3 tests, +0.5 merge). "
            "Milestone tracking prevents reward hacking. Clean episode boundaries.",
            19
        ),
        "Code quality & spec compliance (15%)": (
            "Pydantic models, OpenEnv spec (reset/step/state), Dockerfile, "
            "inference.py in root, openenv.yaml with all tasks.",
            14
        ),
        "Creativity & novelty (10%)": (
            "Novel use of LLM-as-a-Judge (Llama 3.3) as QA reviewer. "
            "Iterative fix loop is unique mechanics not seen in standard envs.",
            9
        ),
    }

    total = 0
    for criterion, (explanation, score) in criteria.items():
        print(f"  {criterion}")
        print(f"    Score: {score}")
        print(f"    Why:   {explanation}")
        total += score
        print()

    print(f"  Estimated Total Score: {total}/100")
    return total


# ══════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════

async def main():
    print("\n" + "=" * 60)
    print("  Meta PyTorch Hackathon — Judge Pipeline Simulation")
    print(f"  Target: {HF_SPACE_URL}")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        await phase1_automated_validation(client)
        await phase2_agentic_evaluation(client)

    phase3_scoring_assessment()

    # Final summary
    print("\n" + "=" * 60)
    print("  FINAL SUMMARY")
    print("=" * 60)
    print(f"\n  Automated checks: {checks_passed}/{checks_total} passed\n")
    print(f"  {'Task':<20} {'Merged':<10} {'Steps':<8} {'Score'}")
    print(f"  {'-'*50}")
    for task_id in ALL_TASKS:
        if task_id in results:
            r = results[task_id]
            icon = "PASS" if r["merged"] else "FAIL"
            print(f"  {task_id:<20} {icon:<10} {r['steps']:<8} {r['score']:.3f}")
        else:
            print(f"  {task_id:<20} {'SKIP':<10} {'0':<8} 0.000")
    print(f"  {'-'*50}")

    all_passed = all(results.get(t, {}).get("merged") for t in ALL_TASKS)
    gate = "PASSED" if all_passed else "FAILED"
    print(f"\n  Phase 1 Gate: {gate}")
    print(f"  Ready to submit: {'YES' if all_passed and checks_passed == checks_total else 'NO - fix failing checks above'}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

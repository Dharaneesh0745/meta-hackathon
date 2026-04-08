"""
Local Environment Test
=======================
Runs each of the 3 tasks through the full agent workflow:
  reset → read_ticket → edit_file → run_tests → submit_pr

Validates that the environment produces correct rewards and done signals.
"""

import asyncio
from models import AgencyAction, ReadTicket, EditFile, RunTests, SubmitPR
from env import MockAgencyEnv


FIXES = {
    "easy-ticket": {
        "file": "config.py",
        "content": (
            "# Application Configuration\n"
            "\n"
            "APP_NAME = 'JiraPR Agency'\n"
            "VERSION = '1.0.0'\n"
            "DEBUG = False  # Fixed for production\n"
            "LOG_LEVEL = 'INFO'\n"
        ),
    },
    "medium-ticket": {
        "file": "auth.py",
        "content": (
            "import re\n"
            "\n"
            "def validate_email(email: str) -> bool:\n"
            "    \"\"\"Validate an email address.\"\"\"\n"
            "    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'\n"
            "    return bool(re.match(pattern, email))\n"
        ),
    },
    "hard-ticket": {
        "file": "server.py",
        "content": (
            "# Simple API Server\n"
            "\n"
            "def handle_health():\n"
            "    return {'status': 'healthy'}\n"
            "\n"
            "def handle_submit(body: dict) -> dict:\n"
            "    data = body.get('data', '')\n"
            "    return {'status': 'received', 'length': len(data)}\n"
        ),
    },
}


async def test_task(task_id: str) -> bool:
    """Run one full episode for a given task."""
    print(f"\n{'='*60}")
    print(f"  TESTING: {task_id}")
    print(f"{'='*60}")

    env = MockAgencyEnv()

    # 1. RESET
    result = await env.reset(task_id=task_id)
    print(f"[1] Reset  → task={task_id}, files={result.observation.files_in_repo}")
    assert not result.done, "Should not be done after reset"
    assert result.reward == 0.0, "Reward should be 0 after reset"

    # 2. READ TICKET
    result = await env.step(AgencyAction(read_ticket=ReadTicket(ticket_id=task_id)))
    print(f"[2] Read   → reward={result.reward:.2f}")

    # 3. EDIT FILE
    fix = FIXES[task_id]
    result = await env.step(AgencyAction(edit_file=EditFile(file_path=fix["file"], new_content=fix["content"])))
    print(f"[3] Edit   → reward={result.reward:.2f}, output={result.observation.terminal_output[:60]}")
    assert result.reward > 0, "Reward should increase after edit"

    # 4. RUN TESTS
    result = await env.step(AgencyAction(run_tests=RunTests(target="test_task.py")))
    print(f"[4] Test   → reward={result.reward:.2f}")
    assert "passed" in result.observation.terminal_output.lower() or result.reward > 0.3, \
        f"Tests should pass after correct fix. Output: {result.observation.terminal_output[:100]}"

    # 5. SUBMIT PR
    result = await env.step(AgencyAction(submit_pr=SubmitPR(ticket_id=task_id, title=f"Fix {task_id}")))
    print(f"[5] PR     → reward={result.reward:.2f}, done={result.done}")
    print(f"   Output: {result.observation.terminal_output}")
    assert result.done, "Should be done after submit_pr"
    assert result.reward >= 0.5, f"Final reward should be >= 0.5, got {result.reward}"

    await env.close()
    print(f"  ✅ {task_id} PASSED (score={result.reward:.2f})")
    return True


async def main():
    print("=" * 60)
    print("  JIRA-TO-PR ENVIRONMENT VALIDATION SUITE")
    print("=" * 60)

    results = {}
    for task_id in ["easy-ticket", "medium-ticket", "hard-ticket"]:
        try:
            results[task_id] = await test_task(task_id)
        except Exception as e:
            print(f"  ❌ {task_id} FAILED: {e}")
            results[task_id] = False

    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for task_id, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {task_id}")

    all_pass = all(results.values())
    print(f"\n  {'🎉 ALL TESTS PASSED!' if all_pass else '⚠️  SOME TESTS FAILED'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())

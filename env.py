"""
Jira-to-PR Mock Agency Environment
===================================
Simulates a software engineering workflow where an AI agent:
  1. Reads a Jira ticket describing a bug
  2. Edits the relevant source file to fix the bug
  3. Runs pytest to verify the fix
  4. Submits a PR for final grading

Three difficulty levels:
  - easy-ticket:   Change a config boolean
  - medium-ticket: Fix a broken email validation regex
  - hard-ticket:   Add a new POST /submit API endpoint
"""

import tempfile
import os
import shutil
import subprocess
import uuid
from typing import Optional, Any, Dict

from models import (
    AgencyAction,
    AgencyObservation,
    AgencyState,
    StepResult,
)


# ─────────────────────────────────────────────
# TASK DEFINITIONS
# ─────────────────────────────────────────────

TASKS = {
    "easy-ticket": {
        "title": "EASY-101: Fix DEBUG flag in config.py",
        "description": (
            "The production config file has DEBUG set to True. "
            "This causes verbose logging and security leaks in production. "
            "Change DEBUG to False in config.py so the test passes."
        ),
        "files": {
            "config.py": (
                "# Application Configuration\n"
                "\n"
                "APP_NAME = 'JiraPR Agency'\n"
                "VERSION = '1.0.0'\n"
                "DEBUG = True  # BUG: Must be False in production!\n"
                "LOG_LEVEL = 'INFO'\n"
            ),
            "test_task.py": (
                "from config import DEBUG\n"
                "\n"
                "def test_debug_is_disabled():\n"
                "    assert DEBUG == False, 'DEBUG must be False in production'\n"
            ),
        },
        "target_file": "config.py",
    },
    "medium-ticket": {
        "title": "MED-201: Fix broken email validation in auth.py",
        "description": (
            "The validate_email function in auth.py only checks if '@' is present, "
            "which means 'bademail.com' passes validation. "
            "Fix it using proper validation logic (e.g., regex or string splitting) "
            "so that invalid emails are rejected."
        ),
        "files": {
            "auth.py": (
                "import re\n"
                "\n"
                "def validate_email(email: str) -> bool:\n"
                "    \"\"\"Validate an email address.\"\"\"\n"
                "    # BUG: This is too permissive!\n"
                "    return '@' in email\n"
            ),
            "test_task.py": (
                "from auth import validate_email\n"
                "\n"
                "def test_valid_email_accepted():\n"
                "    assert validate_email('user@example.com') == True\n"
                "\n"
                "def test_invalid_email_rejected():\n"
                "    assert validate_email('bademail.com') == False\n"
                "\n"
                "def test_subdomain_email_accepted():\n"
                "    assert validate_email('admin@mail.corp.co') == True\n"
            ),
        },
        "target_file": "auth.py",
    },
    "hard-ticket": {
        "title": "HRD-301: Add POST /submit endpoint to server.py",
        "description": (
            "The server.py application is missing a POST /submit endpoint. "
            "Add a function called 'handle_submit' that accepts a JSON body with "
            "a 'data' field and returns {'status': 'received', 'length': len(data)}. "
            "The test will call this function directly to verify correctness."
        ),
        "files": {
            "server.py": (
                "# Simple API Server\n"
                "\n"
                "def handle_health():\n"
                "    return {'status': 'healthy'}\n"
                "\n"
                "# TODO: Add handle_submit endpoint here\n"
            ),
            "test_task.py": (
                "from server import handle_submit\n"
                "\n"
                "def test_submit_returns_status():\n"
                "    result = handle_submit({'data': 'hello world'})\n"
                "    assert result['status'] == 'received'\n"
                "\n"
                "def test_submit_returns_length():\n"
                "    result = handle_submit({'data': 'test'})\n"
                "    assert result['length'] == 4\n"
                "\n"
                "def test_submit_empty_data():\n"
                "    result = handle_submit({'data': ''})\n"
                "    assert result['length'] == 0\n"
            ),
        },
        "target_file": "server.py",
    },
}


# ─────────────────────────────────────────────
# ENVIRONMENT CLASS
# ─────────────────────────────────────────────

class MockAgencyEnv:
    """
    OpenEnv-compatible environment that simulates a Jira-to-PR workflow.
    The agent reads a ticket, edits code, runs tests, and submits a PR.
    """

    def __init__(self):
        self.temp_dir: Optional[str] = None
        self.current_task: Optional[str] = None
        self.episode_id: Optional[str] = None
        self.step_count: int = 0
        self.score: float = 0.0
        self.done: bool = False
        self.last_action_error: Optional[str] = None

    # ── RESET ──────────────────────────────

    async def reset(self, task_id: Optional[str] = None) -> StepResult:
        """Create a fresh sandbox and load a task."""
        # Cleanup previous episode
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

        # Pick task
        if task_id and task_id in TASKS:
            self.current_task = task_id
        else:
            import random
            self.current_task = random.choice(list(TASKS.keys()))

        self.episode_id = str(uuid.uuid4())[:8]
        self.step_count = 0
        self.score = 0.0
        self.done = False
        self.last_action_error = None

        # Create isolated temp directory with task files
        self.temp_dir = tempfile.mkdtemp(prefix="jira_pr_")
        task = TASKS[self.current_task]
        for filename, content in task["files"].items():
            filepath = os.path.join(self.temp_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        obs = AgencyObservation(
            current_ticket=f"[{task['title']}]\n{task['description']}",
            terminal_output=f"Environment reset. Task: {self.current_task}. Sandbox ready.",
            files_in_repo=os.listdir(self.temp_dir),
            reward=0.0,
            done=False,
        )
        return StepResult(observation=obs, reward=0.0, done=False, info={"task_id": self.current_task})

    # ── STEP ───────────────────────────────

    async def step(self, action: AgencyAction) -> StepResult:
        """Process one agent action and return observation + reward."""
        if self.done:
            return self._make_result("Episode already finished.", 0.0, True)

        self.step_count += 1
        self.last_action_error = None

        try:
            # ── ReadTicket ──
            if action.read_ticket:
                task = TASKS.get(self.current_task, {})
                ticket_text = f"[{task.get('title', 'Unknown')}]\n{task.get('description', 'No description.')}"
                return self._make_result(
                    f"Ticket content:\n{ticket_text}",
                    0.0,
                    False,
                )

            # ── EditFile ──
            elif action.edit_file:
                if not self.temp_dir:
                    return self._make_result("No sandbox initialized. Call reset() first.", 0.0, False)

                file_path = os.path.join(self.temp_dir, action.edit_file.file_path)
                # Security: prevent path traversal
                real_path = os.path.realpath(file_path)
                if not real_path.startswith(os.path.realpath(self.temp_dir)):
                    self.last_action_error = "Path traversal blocked."
                    return self._make_result("Error: Invalid file path.", -0.1, False)

                os.makedirs(os.path.dirname(real_path), exist_ok=True)
                with open(real_path, "w", encoding="utf-8") as f:
                    f.write(action.edit_file.new_content)

                # Dense reward: agent made progress by editing
                return self._make_result(
                    f"Saved {action.edit_file.file_path} ({len(action.edit_file.new_content)} bytes).",
                    0.2,
                    False,
                )

            # ── RunTests ──
            elif action.run_tests:
                if not self.temp_dir:
                    return self._make_result("No sandbox initialized.", 0.0, False)

                target = action.run_tests.target or "test_task.py"
                test_path = os.path.join(self.temp_dir, target)

                if not os.path.exists(test_path):
                    return self._make_result(f"Test file not found: {target}", -0.1, False)

                try:
                    out = subprocess.check_output(
                        ["python", "-m", "pytest", test_path, "-v", "--tb=short"],
                        cwd=self.temp_dir,
                        stderr=subprocess.STDOUT,
                        timeout=15,
                    )
                    output = out.decode("utf-8", errors="replace")
                    # Tests passed → positive reward
                    return self._make_result(output, 0.3, False)
                except subprocess.CalledProcessError as e:
                    output = e.output.decode("utf-8", errors="replace")
                    # Tests failed → small penalty
                    return self._make_result(output, -0.1, False)
                except subprocess.TimeoutExpired:
                    return self._make_result("Tests timed out after 15 seconds.", -0.1, False)

            # ── SubmitPR ──
            elif action.submit_pr:
                if not self.temp_dir:
                    return self._make_result("No sandbox initialized.", 0.0, True)

                # Final grading: run the hidden test suite
                test_path = os.path.join(self.temp_dir, "test_task.py")
                try:
                    subprocess.check_output(
                        ["python", "-m", "pytest", test_path, "-q"],
                        cwd=self.temp_dir,
                        stderr=subprocess.STDOUT,
                        timeout=15,
                    )
                    # All tests pass → PR merged, max reward
                    self.done = True
                    return self._make_result(
                        "✅ PR Merged! All tests passed. Great work!",
                        0.5,
                        True,
                    )
                except subprocess.CalledProcessError as e:
                    output = e.output.decode("utf-8", errors="replace")
                    self.done = True
                    return self._make_result(
                        f"❌ PR Rejected — tests still failing.\n{output}",
                        -0.2,
                        True,
                    )
                except subprocess.TimeoutExpired:
                    self.done = True
                    return self._make_result("PR Rejected — tests timed out.", -0.2, True)

            else:
                self.last_action_error = "No recognized action field was set."
                return self._make_result(
                    "No valid action recognized. Use read_ticket, edit_file, run_tests, or submit_pr.",
                    0.0,
                    False,
                )

        except Exception as exc:
            self.last_action_error = str(exc)
            return self._make_result(f"Internal error: {exc}", 0.0, False)

    # ── STATE ──────────────────────────────

    async def state(self) -> AgencyState:
        return AgencyState(
            episode_id=self.episode_id,
            current_task=self.current_task,
            step_count=self.step_count,
            score=self.score,
            done=self.done,
            files_in_repo=os.listdir(self.temp_dir) if self.temp_dir and os.path.exists(self.temp_dir) else [],
        )

    # ── CLOSE ──────────────────────────────

    async def close(self) -> None:
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None

    # ── HELPERS ────────────────────────────

    def _make_result(self, output: str, reward_delta: float, done: bool) -> StepResult:
        """Build a StepResult, updating internal score with clamping."""
        self.score += reward_delta
        self.score = min(max(self.score, 0.0), 1.0)  # clamp [0.0, 1.0]
        self.done = done

        obs = AgencyObservation(
            current_ticket=f"Active task: {self.current_task}",
            terminal_output=output,
            files_in_repo=os.listdir(self.temp_dir) if self.temp_dir and os.path.exists(self.temp_dir) else [],
            reward=self.score,
            done=done,
        )
        return StepResult(observation=obs, reward=self.score, done=done, info={})

    @classmethod
    async def from_docker_image(cls, image_name: str):
        """Factory method for OpenEnv compatibility."""
        return cls()

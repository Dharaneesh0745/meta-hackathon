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

from .models import (
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
        "title": "EASY-101: Fix Pagination Off-By-One",
        "description": (
            "The database paginator in database.py is dropping the last item of every page "
            "because of an improper slice index. Fix the logic so it returns the requested "
            "number of items perfectly."
        ),
        "files": {
            "database.py": (
                "class Database:\n"
                "    def __init__(self):\n"
                "        self.data = list(range(100))\n"
                "\n"
                "    def get_page(self, page: int, size: int):\n"
                "        start = (page - 1) * size\n"
                "        end = start + size\n"
                "        # BUG: The slice is cutting off the last element!\n"
                "        return self.data[start:end-1]\n"
            ),
            "test_task.py": (
                "from database import Database\n"
                "def test_pagination():\n"
                "    db = Database()\n"
                "    page = db.get_page(1, 10)\n"
                "    assert len(page) == 10, f'Expected 10 items, got {len(page)}'\n"
            ),
        },
        "target_file": "database.py",
    },
    "medium-ticket": {
        "title": "MED-201: Implement Role-Based Access Control",
        "description": (
            "The middleware in `middleware.py` checks for a generic token but doesn't "
            "verify if the user actually has the 'admin' role. Update the authorization "
            "function to validate roles correctly."
        ),
        "files": {
            "middleware.py": (
                "def authorize_request(token: str, required_role: str) -> bool:\n"
                "    \"\"\"Validates JWT-like tokens for specific roles.\"\"\"\n"
                "    if not token:\n"
                "        return False\n"
                "    \n"
                "    parsed_token = token.split('.')\n"
                "    if len(parsed_token) != 3:\n"
                "        return False\n"
                "        \n"
                "    # BUG: We are just returning True instead of checking role!\n"
                "    # Token format is 'header.role.signature'\n"
                "    return True\n"
            ),
            "test_task.py": (
                "from middleware import authorize_request\n"
                "def test_auth():\n"
                "    assert authorize_request('header.admin.hash', 'admin') == True\n"
                "    assert authorize_request('header.guest.hash', 'admin') == False\n"
            ),
        },
        "target_file": "middleware.py",
    },
    "hard-ticket": {
        "title": "HRD-301: Fix Refund Worker Race Condition",
        "description": (
            "The async worker in `worker.py` occasionally double-refunds users when "
            "two concurrent requests hit the queue simultaneously. Fix the state check "
            "to make processing atomic/thread-safe."
        ),
        "files": {
            "worker.py": (
                "import time\n"
                "\n"
                "class RefundWorker:\n"
                "    def __init__(self):\n"
                "        self.processed = set()\n"
                "\n"
                "    def process_refund(self, transaction_id: str):\n"
                "        if transaction_id in self.processed:\n"
                "            return False\n"
                "        \n"
                "        # Simulate long I/O delay that allows race conditions\n"
                "        time.sleep(0.1)\n"
                "        \n"
                "        self.processed.add(transaction_id)\n"
                "        return True\n"
            ),
            "test_task.py": (
                "from worker import RefundWorker\n"
                "def test_basic_refund():\n"
                "    worker = RefundWorker()\n"
                "    assert worker.process_refund('tx_123') == True\n"
                "    assert worker.process_refund('tx_123') == False\n"
            ),
        },
        "target_file": "worker.py",
    },
    "extreme-ticket": {
        "title": "EXT-401: Validated TTL LRU Cache",
        "description": (
            "The mock_repo needs a thread-safe LRU Cache with Time-To-Live (TTL). "
            "Implement `ThreadSafeLRUCache` taking `capacity` and `ttl_seconds`. "
            "The dynamic QA will verify eviction logic, lock mechanisms, and TTL enforcement."
        ),
        "files": {
            "cache.py": (
                "class ThreadSafeLRUCache:\n"
                "    def __init__(self, capacity: int, ttl_seconds: int):\n"
                "        self.capacity = capacity\n"
                "        self.ttl = ttl_seconds\n"
                "        # TODO: Implement\n"
                "    \n"
                "    def get(self, key):\n"
                "        pass\n"
                "    \n"
                "    def put(self, key, value):\n"
                "        pass\n"
            ),
            "test_task.py": (
                "from cache import ThreadSafeLRUCache\n"
                "def test_instantiation():\n"
                "    cache = ThreadSafeLRUCache(10, 60)\n"
                "    assert cache.capacity == 10\n"
            ),
        },
        "target_file": "cache.py",
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
        self.milestones = {"edited": False, "tested": False}

    @property
    def tasks(self):
        """Official task registry for the OpenEnv validator."""
        return [
            {
                "id": tid, 
                "name": t["title"], 
                "description": t["description"],
                "has_grader": True
            }
            for tid, t in TASKS.items()
        ]

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
        self.milestones = {"edited": False, "tested": False}

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
            observation_text=f"Environment reset. Task: {self.current_task}.",
            files=os.listdir(self.temp_dir),
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
                reward_delta = 0.2 if not self.milestones["edited"] else 0.0
                self.milestones["edited"] = True
                
                return self._make_result(
                    f"Saved {action.edit_file.file_path} ({len(action.edit_file.new_content)} bytes).",
                    reward_delta,
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
                    reward_delta = 0.3 if not self.milestones["tested"] else 0.0
                    self.milestones["tested"] = True
                    return self._make_result(output, reward_delta, False)
                except subprocess.CalledProcessError as e:
                    output = e.output.decode("utf-8", errors="replace")
                    # Tests failed → small penalty
                    return self._make_result(output, -0.1, False)
                except subprocess.TimeoutExpired:
                    return self._make_result("Tests timed out after 15 seconds.", -0.1, False)

            # ── SubmitPR ──
            elif action.submit_pr:
                if not self.temp_dir:
                    return self._make_result("No sandbox initialized.", 0.0, False)
                
                # Universal Dynamic QA Evaluation for all tasks
                return await self._dynamic_qa_eval()

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
            files=os.listdir(self.temp_dir) if self.temp_dir and os.path.exists(self.temp_dir) else [],
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
            observation_text=output,
            files=os.listdir(self.temp_dir) if self.temp_dir and os.path.exists(self.temp_dir) else [],
            reward=self.score,
            done=done,
        )
        return StepResult(observation=obs, reward=self.score, done=done, info={})

    async def _dynamic_qa_eval(self) -> StepResult:
        from openai import AsyncOpenAI
        import os
        from dotenv import load_dotenv
        
        load_dotenv() # Load variables from .env if present

        hf_token = os.getenv("HF_TOKEN")
        if not hf_token:
            return self._make_result("QA Agent Error: HF_TOKEN is not set.", 0.0, False)
            
        client = AsyncOpenAI(
            api_key=hf_token,
            base_url=os.getenv("API_BASE_URL", "https://router.huggingface.co/hf-inference/v1")
        )
        
        target_file_name = TASKS[self.current_task]["target_file"]
        file_path = os.path.join(self.temp_dir, target_file_name)
        
        if not os.path.exists(file_path):
            return self._make_result(f"❌ PR Rejected: {target_file_name} not found.", -0.2, False)
            
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
            
        task_desc = TASKS[self.current_task]["description"]
        
        system_prompt = (
            "You are a Senior QA Engineer evaluating code for a specific bug ticket.\n"
            f"Ticket explicitly states: \"{task_desc}\"\n\n"
            "Your job is to read carefully and check if the code strictly resolves this specific ticket. "
            "If the code fixes the stated bug/implements the stated feature perfectly, reply exactly with 'PASS'.\n"
            "CRITICAL: Do NOT invent edge cases, demand handling of negative bounds, type checking, or exception handling UNLESS "
            "it is explicitly mentioned in the ticket! For simple tickets, be very lenient. For complex tickets (like LRU/threads), "
            "evaluate logical flaws related strictly to the algorithm. Only reply with the edge case explanation if it genuinely fails the ticket's scope."
        )
        try:
            model_name = os.getenv("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")
            resp = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Review this code to see if it fixes the ticket:\n\n```python\n{code}\n```"}
                ],
                temperature=0.2,
                max_tokens=250
            )
            feedback = resp.choices[0].message.content.strip()
            if feedback == "PASS":
                self.done = True
                # Reward is exactly what's needed to reach 1.0 (completion reward)
                reward_to_max = max(0.0, 1.0 - self.score)
                return self._make_result("✅ PR Merged! The Dynamic QA Agent found no flaws.", reward_to_max, True)
            else:
                self.done = False
                return self._make_result(f"❌ Cannot submit PR: QA review found edge cases:\n\n{feedback}", -0.2, False)
        except Exception as e:
            self.done = False
            return self._make_result(f"QA Agent Error: {e}", 0.0, False)

    @classmethod
    async def from_docker_image(cls, image_name: str):
        """Factory method for OpenEnv compatibility."""
        return cls()

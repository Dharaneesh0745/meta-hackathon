"""
Jira-to-PR Inference Script
============================
MANDATORY VARIABLES (injected by hackathon evaluator):
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.

STDOUT FORMAT:
    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<0.000> rewards=<r1,r2,...,rn>
"""

import asyncio
import os
import json
from typing import List, Optional

from openai import OpenAI

from agentic_os_env.models import AgencyAction
from agentic_os_env.env import MockAgencyEnv

# ─────────────────────────────────────────────
# CONFIGURATION (from environment variables)
# ─────────────────────────────────────────────

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
IMAGE_NAME = os.getenv("IMAGE_NAME", "jira-to-pr")

TASK_NAME = "jira-to-pr"
BENCHMARK = "jira-to-pr"
MAX_STEPS = 10
SUCCESS_SCORE_THRESHOLD = 0.5


# ─────────────────────────────────────────────
# LOGGING (exact format from sample script)
# ─────────────────────────────────────────────

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)


# ─────────────────────────────────────────────
# LLM INTERACTION
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are an autonomous AI Software Engineer inside a Mock Agency environment.
Your objective is to resolve the Jira ticket by editing the correct file, running tests, and submitting a PR.

Available actions (return EXACTLY ONE per turn as a valid JSON object):
  {"read_ticket": {"ticket_id": "<task_id>"}}
  {"edit_file": {"file_path": "<filename>", "new_content": "<full file content>"}}
  {"run_tests": {"target": "test_task.py"}}
  {"submit_pr": {"ticket_id": "<task_id>", "title": "<PR title>"}}

Rules:
  - ONLY output raw JSON. No markdown, no backticks, no extra text.
  - Read the ticket first to understand the bug.
  - Edit the target file with the complete corrected content.
  - Run tests to verify your fix before submitting.
  - Submit a PR when tests pass.
"""


def get_model_action(client: OpenAI, obs, step: int) -> str:
    user_prompt = f"""Current Observation:
Ticket: {obs.current_ticket}
Terminal Output: {obs.terminal_output}
Files: {obs.files}
Step: {step}

What is your next action? Reply with a single JSON object."""

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=1500,
            stream=False,
        )
        content = (completion.choices[0].message.content or "").strip()
        # Strip markdown code fences if the model wraps its response
        if content.startswith("```json"):
            content = content.replace("```json\n", "").replace("```json", "").replace("```", "")
        elif content.startswith("```"):
            content = content.replace("```\n", "").replace("```", "")
        return content.strip()
    except Exception as exc:
        print(f"[DEBUG] Model API call failed: {exc}", flush=True)
        return "{}"


# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────

async def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    env = MockAgencyEnv()

    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=TASK_NAME, env=BENCHMARK, model=MODEL_NAME)

    try:
        result = await env.reset()

        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break

            obs = result.observation
            action_json_str = get_model_action(client, obs, step)

            error = None
            try:
                action_dict = json.loads(action_json_str)
                action = AgencyAction(**action_dict)
            except Exception as e:
                error = f"JSON/Pydantic parse failed: {e}"
                action = AgencyAction()  # Empty / no-op action

            result = await env.step(action)

            reward = result.reward or 0.0
            done = result.done

            rewards.append(reward)
            steps_taken = step

            # Single-line action string for log format
            safe_action_str = action_json_str.replace("\n", " ").replace("\r", "")
            log_step(step=step, action=safe_action_str, reward=reward, done=done, error=error)

            if done:
                break

        score = rewards[-1] if rewards else 0.0
        score = min(max(score, 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD

    finally:
        try:
            await env.close()
        except Exception as e:
            print(f"[DEBUG] env.close() error: {e}", flush=True)
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


if __name__ == "__main__":
    asyncio.run(main())

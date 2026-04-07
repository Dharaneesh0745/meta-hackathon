---
title: Jira-to-PR
emoji: ⚡
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# 🚀 Jira-to-PR: AI Mock Agency Environment

> An OpenEnv environment that simulates a real-world software engineering workflow — from reading a Jira ticket to submitting a Pull Request.

![OpenEnv](https://img.shields.io/badge/OpenEnv-Compatible-blue)
![Python](https://img.shields.io/badge/Python-3.10+-green)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📋 Environment Description

**Jira-to-PR** is an agentic environment that simulates the day-to-day workflow of a software engineer:

1. **Read a Jira ticket** describing a bug in the codebase
2. **Edit the source file** to fix the bug
3. **Run the test suite** to verify the fix
4. **Submit a Pull Request** for final grading

The environment creates an **isolated temporary sandbox** for each episode, seeds it with buggy code and corresponding test files, and uses **deterministic pytest graders** to evaluate the agent's fix.

### Why This Matters

This environment models a **genuine professional workflow** — the kind of task millions of developers perform daily. Training agents to autonomously resolve tickets, write correct code, and pass test suites is a critical step toward reliable AI-assisted software development.

---

## 🎯 Action Space

The agent can perform exactly **one action per step**. Actions are defined as Pydantic models:

| Action | Fields | Description |
|--------|--------|-------------|
| `read_ticket` | `ticket_id: str` | Read the Jira ticket description |
| `edit_file` | `file_path: str, new_content: str` | Write/overwrite a file in the sandbox |
| `run_tests` | `target: str` | Run pytest on a specific test file |
| `submit_pr` | `ticket_id: str, title: str` | Submit the fix for final grading |

### Action JSON Format

```json
{"read_ticket": {"ticket_id": "easy-ticket"}}
{"edit_file": {"file_path": "config.py", "new_content": "DEBUG = False\n"}}
{"run_tests": {"target": "test_task.py"}}
{"submit_pr": {"ticket_id": "easy-ticket", "title": "Fix: Disable DEBUG flag"}}
```

---

## 📤 Observation Space

Each step returns an `AgencyObservation`:

| Field | Type | Description |
|-------|------|-------------|
| `current_ticket` | `str` | The active Jira ticket content |
| `terminal_output` | `str` | Output from the last action (test results, file save confirmation, etc.) |
| `files_in_repo` | `List[str]` | Files currently in the sandbox directory |
| `reward` | `float` | Cumulative reward so far (0.0–1.0) |
| `done` | `bool` | Whether the episode is complete |

---

## 🎮 Tasks

Three tasks with increasing difficulty, each backed by deterministic pytest graders:

### Easy: Fix DEBUG Flag (easy-ticket)
- **File:** `config.py`
- **Bug:** `DEBUG = True` in production configuration
- **Fix:** Change to `DEBUG = False`
- **Test:** Asserts `DEBUG == False`

### Medium: Fix Email Validation (medium-ticket)
- **File:** `auth.py`
- **Bug:** `validate_email()` only checks `'@' in email`, accepting invalid addresses
- **Fix:** Implement proper regex or string validation
- **Test:** Validates that `user@example.com` passes and `bademail.com` fails

### Hard: Add API Endpoint (hard-ticket)
- **File:** `server.py`
- **Bug:** Missing `handle_submit()` function
- **Fix:** Implement a function that accepts `{'data': str}` and returns `{'status': 'received', 'length': len(data)}`
- **Test:** Calls `handle_submit()` directly and verifies return fields

---

## 💰 Reward Function

The reward function provides **dense signal** throughout the episode, not just at the end:

| Action | Reward | Rationale |
|--------|--------|-----------|
| `read_ticket` | +0.0 | Information gathering, no code change |
| `edit_file` | +0.2 | Agent made progress by modifying code |
| `run_tests` (pass) | +0.3 | Tests pass, fix is likely correct |
| `run_tests` (fail) | −0.1 | Penalty for incorrect fix |
| `submit_pr` (pass) | +0.5 | PR merged, all tests pass |
| `submit_pr` (fail) | −0.2 | PR rejected, tests still failing |

**Total possible reward:** 1.0 (clamped to [0.0, 1.0])

---

## 🛠️ Setup & Usage

### Prerequisites

- Python 3.10+
- Docker (for containerized deployment)
- `pip install openenv-core`

### Local Development

```bash
# Clone the repository
git clone https://github.com/your-username/jira-to-pr.git
cd jira-to-pr

# Install dependencies
pip install -r requirements.txt

# Run the server locally
python -m uvicorn server.app:app --host 0.0.0.0 --port 7860 --reload

# Open the dashboard
# http://localhost:7860/web
```

### Docker

```bash
# Build
docker build -t jira-to-pr .

# Run
docker run -p 7860:7860 jira-to-pr

# Test endpoints
curl http://localhost:7860/health
curl -X POST http://localhost:7860/reset -H "Content-Type: application/json" -d '{}'
```

### Run Inference

```bash
# Set environment variables
export HF_TOKEN=your_token
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct

# Run the baseline agent
python inference.py
```

---

## 📊 Baseline Scores

| Task | Steps | Score | Notes |
|------|-------|-------|-------|
| easy-ticket | 4 | 1.0 | Simple boolean flip |
| medium-ticket | 4 | 1.0 | Requires regex knowledge |
| hard-ticket | 4 | 1.0 | Requires function implementation |

*Baseline model: Qwen/Qwen2.5-72B-Instruct via Hugging Face Inference API*

---

## 🏗️ API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check → `{"status": "healthy"}` |
| `/reset` | POST | Reset environment (optional `task_id` in body) |
| `/step` | POST | Execute an action |
| `/state` | GET | Get current environment state |
| `/tasks` | GET | List all available tasks |
| `/ws` | WebSocket | Persistent session connection |
| `/web` | GET | Interactive HTML dashboard |
| `/docs` | GET | Auto-generated OpenAPI documentation |

---

## 📁 Project Structure

```
jira-to-pr/
├── env.py              # Core environment logic (reset, step, state)
├── models.py           # Pydantic models (Action, Observation, State)
├── inference.py        # Baseline inference script
├── openenv.yaml        # OpenEnv manifest
├── Dockerfile          # Container configuration
├── requirements.txt    # Python dependencies
├── server/
│   ├── __init__.py
│   └── app.py          # FastAPI server with all endpoints
├── static/
│   └── index.html      # Interactive web dashboard
└── docs/               # Reference documentation
```

---

## 🏆 Hackathon Problem Statement

This environment addresses the **Workflow Automation** problem statement by simulating an end-to-end software development lifecycle — from receiving a Jira ticket to merging a Pull Request. It evaluates an AI agent's ability to:

- Understand natural language bug descriptions
- Navigate a codebase and identify the correct file
- Write syntactically and semantically correct code fixes
- Verify fixes through automated testing
- Follow a structured professional workflow
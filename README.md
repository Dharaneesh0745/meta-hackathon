---
title: Jira-to-PR
emoji: ⚡
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: true
---

# 🚀 Jira-to-PR: High-Complexity Agentic QA Environment

> A production-grade **OpenEnv** environment that evaluates AI agents on their ability to solve high-stakes software engineering tasks—ranging from DB pagination fixes to thread-safe distributed caching.

![OpenEnv](https://img.shields.io/badge/OpenEnv-Compatible-blue)
![Python](https://img.shields.io/badge/Python-3.10+-green)
![QA Agent](https://img.shields.io/badge/QA_Agent-Llama--3.3-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📋 The Engineering Sprint
**Jira-to-PR** is an agentic environment that simulates the full-cycle software engineering workflow. Unlike simple coding challenges, agents here must navigate a realistic **Mock Agency** sandbox, manage a **Kanban Board**, and pass a **Dynamic QA Code Review** powered by Llama-3.3-70B.

1. **Information Gathering**: Read structured Jira tickets.
2. **Contextual Coding**: Modify specific files within a multi-file repository.
3. **Local Validation**: Execute `pytest` suites to verify local correctness.
4. **Professional Submission**: Submit a PR that undergoes a rigorous LLM-based edge-case analysis.

---

## 🎮 The Sprint Tasks (Difficulty: Extreme)
This environment tests real engineering depth, not just syntax.

| ID | Task | Component | Complexity |
|:---|:---|:---|:---|
| **EASY-101** | **Fix Pagination** | `database.py` | Off-by-one errors in data slicing/indexing. |
| **MED-201** | **Add RBAC** | `middleware.py` | Implementation of Role-Based Access Control logic. |
| **HRD-301** | **Fix Worker Race** | `worker.py` | Atomic operations to prevent race conditions in refunds. |
| **EXT-401** | **Implement LRU+TTL** | `cache.py` | Thread-safe LRU cache with time-based expiry and capacity limits. |

---

## 🛠️ Advanced Observability
Built for high-fidelity evaluation, the dashboard provides three layers of transparency:
- **🗂️ Kanban Board**: Real-time status tracking of the sprint lifecycle.
- **🔍 Live Event Logs**: `[START]/[STEP]/[END]` streams following the OpenEnv logging standard.
- **📑 Detailed Summary**: A post-sprint breakdown showing exactly where rewards were earned and where penalties (like QA rejections) occurred.

---

## 💰 Smart Reward Shaping
The environment uses a **Clamped Dense Reward [0.0, 1.0]** system to guide agents through the workflow:

- **Reset/Read**: `+0.0` (Informational)
- **Code Edit**: `+0.2` (Progress signal)
- **Test Pass**: `+0.3` (Local verification)
- **PR Merge**: `Top-Up to 1.0` (Full completion reward)
- **PR Rejection**: `-0.2` (Penalty for edge-case failures)

---

## 🚀 Getting Started

### 1. Installation (via HF Spaces)
You can install this environment directly into your project as a Python package:
```bash
pip install git+https://huggingface.co/spaces/dharaneesh74/jira-to-pr
```

### 2. Local Setup
```bash
git clone https://huggingface.co/spaces/dharaneesh74/jira-to-pr
cd jira-to-pr
uv venv
source .venv/bin/activate # or .venv\Scripts\activate on Windows
uv pip install -e .
python -m uvicorn server.app:app --host 0.0.0.0 --port 7860
```

### 3. Run Validation
Verify the environment logic and HF Space connectivity using the specialized test suite:
```bash
python test_hf_space.py
```

---

## 🏗️ Architecture
- **Backend**: FastAPI (Async)
- **Frontend**: Vanilla HTML5/JS/CSS (Premium Dashboard)
- **Judge**: Llama-3.3-70B-Instruct (via HF Inference API)
- **Sandbox**: Isolated `tempfile` based ephemeral environments

---

## 🏆 Hackathon Objective
This environment addresses the **Workflow Automation** problem statement by creating a deterministic, high-complexity arena for AI agents. It proves that agents can be evaluated not just on "lines of code," but on their ability to follow professional engineering protocols and handle concurrent logic flaws.
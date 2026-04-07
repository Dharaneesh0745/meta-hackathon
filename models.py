from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# ─────────────────────────────────────────────
# ACTION MODELS (Agent → Environment)
# ─────────────────────────────────────────────

class ReadTicket(BaseModel):
    ticket_id: str = Field(..., description="The ID of the Jira ticket to read.")


class EditFile(BaseModel):
    file_path: str = Field(..., description="Path to the file relative to the repository root.")
    new_content: str = Field(..., description="The complete new content of the file.")


class RunTests(BaseModel):
    target: str = Field("test_task.py", description="Test file to run, e.g., 'test_task.py'")


class SubmitPR(BaseModel):
    ticket_id: str = Field(..., description="The Jira ticket ID this PR resolves.")
    title: str = Field(..., description="Title of the Pull Request.")


class AgencyAction(BaseModel):
    """Union-style action: exactly one field should be set per step."""
    read_ticket: Optional[ReadTicket] = None
    edit_file: Optional[EditFile] = None
    run_tests: Optional[RunTests] = None
    submit_pr: Optional[SubmitPR] = None


# ─────────────────────────────────────────────
# OBSERVATION MODEL (Environment → Agent)
# ─────────────────────────────────────────────

class AgencyObservation(BaseModel):
    current_ticket: Optional[str] = Field(None, description="Current Jira ticket content.")
    terminal_output: str = Field("", description="Output from the last command or action.")
    files_in_repo: List[str] = Field(default_factory=list, description="List of files in the current repository.")
    reward: float = Field(0.0, description="Cumulative reward so far.")
    done: bool = Field(False, description="Whether the episode is finished.")


# ─────────────────────────────────────────────
# STATE MODEL (for /state endpoint)
# ─────────────────────────────────────────────

class AgencyState(BaseModel):
    episode_id: Optional[str] = Field(None, description="Unique episode identifier.")
    current_task: Optional[str] = Field(None, description="ID of the active task.")
    step_count: int = Field(0, description="Number of steps taken so far.")
    score: float = Field(0.0, description="Cumulative score [0.0, 1.0].")
    done: bool = Field(False, description="Whether the episode is complete.")
    files_in_repo: List[str] = Field(default_factory=list, description="Files currently in the sandbox.")


# ─────────────────────────────────────────────
# STEP RESULT (matches OpenEnv StepResult)
# ─────────────────────────────────────────────

class StepResult(BaseModel):
    observation: AgencyObservation
    reward: float = Field(0.0, ge=0.0, le=1.0)
    done: bool = False
    info: Dict[str, Any] = Field(default_factory=dict)

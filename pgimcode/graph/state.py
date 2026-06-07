"""Agent state model for LangGraph."""

from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """State carried through the LangGraph pipeline."""

    session_id: str
    task: str
    mode: str = "build"
    turn: int = 0
    max_turns: int = 50
    events: list[dict] = Field(default_factory=list)
    active_events: list[dict] = Field(default_factory=list)
    summaries: list[dict] = Field(default_factory=list)
    pinned: list[dict] = Field(default_factory=list)
    messages: list[dict] = Field(default_factory=list)
    repo_map: dict | None = None
    plan: dict | None = None
    carryover_context: str = ""
    recent_files: list[str] = Field(default_factory=list)
    research_goals: list[str] = Field(default_factory=list)
    hypotheses: list[dict] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
    candidate_files: list[dict] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    blast_radius: list[str] = Field(default_factory=list)
    verification_plan: list[str] = Field(default_factory=list)
    task_board: list[dict] = Field(default_factory=list)
    query_intent: dict = Field(default_factory=dict)
    current_node: str = "start"
    last_tool_result: dict = Field(default_factory=dict)
    tool_calls: list[dict] = Field(default_factory=list)
    status: str = "running"
    approval_required: bool = False
    approval_reason: str = ""
    pending_action: list[dict] = Field(default_factory=list)
    token_usage: int = 0
    cost_usd: float = 0.0
    changed_files: list[str] = Field(default_factory=list)
    next_node: str = ""
    settings_dict: dict = Field(default_factory=dict)

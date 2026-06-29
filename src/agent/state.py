# src/agent/state.py
import operator
from typing import Annotated, Literal, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

ExperimentMode = Literal["B1", "B2", "B3", "PROPOSED_MAS"]
WorkflowStage = Literal[
    "AnalyzeFailure",
    "RetrieveKnowledge",
    "GeneratePatch",
    "ApplyPatch",
    "Build",
    "DeployOrMockDeploy",
    "ObserveRuntime",
    "StopOrRetry",
]

class AgentState(TypedDict):
    """
    Global state for the thesis-oriented closed-loop BSP repair workflow.

    The state maps directly to the proposal workflow:
    AnalyzeFailure -> RetrieveKnowledge -> GeneratePatch -> ApplyPatch ->
    Build -> Deploy/MockDeploy -> ObserveRuntime -> Stop or Retry.
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_node: str
    mode: ExperimentMode
    current_stage: WorkflowStage
    iteration_count: int
    max_repair_iterations: int
    start_time: float
    tool_error_count: int
    llm_thinking_time: float
    tool_exec_time: float
    build_passed: bool
    functional_passed: bool
    expected_uart_regex: str
    crash_patterns: list[str]
    repair_history: Annotated[list[str], operator.add]

class RouteDecision(BaseModel):
    """
    主管節點路由決策的強制結構化輸出
    Forced structured output of routing decisions by the supervisor node
    """
    next_node: Literal[
        "Knowledge_Expert",
        "Patch_Expert",
        "DevOps_Expert",
        "QA_Expert",
        "TestPlan_Expert",
        "ZeroShot_Expert",
        "RetrievalOnly_Expert",
        "ClosedLoopSingleAgent_Expert",
        "FINISH",
    ] = Field(
        description="Determine the next execution node. If the task is complete, send a FINISH response."
    )

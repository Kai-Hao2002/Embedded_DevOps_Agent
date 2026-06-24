# src/agent/state.py
import operator
from typing import Annotated, Literal, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

class AgentState(TypedDict):
    """
    定義整個 Multi-Agent 系統共享的全局狀態
    Define the global state shared by the entire Multi-Agent system.
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_node: str
    mode: str          # 核心：控制實驗組 "B1", "B2", "B3", "PROPOSED_MAS"
    iteration_count: int      # 記錄編譯重試次數 (對應 k)
    start_time: float         # 系統啟動時間戳
    tool_error_count: int     # 工具調用錯誤次數 (如 JSON 解析失敗、工具崩潰)
    llm_thinking_time: float  # LLM 推理總耗時
    tool_exec_time: float     # 工具執行總耗時

class RouteDecision(BaseModel):
    """
    主管節點路由決策的強制結構化輸出
    Forced structured output of routing decisions by the supervisor node
    """
    next_node: Literal["Knowledge_Expert", "DevOps_Expert", "QA_Expert", "ZeroShot_Expert", "SingleAgent_Expert", "FINISH"] = Field(
        description="Determine the next execution node. If the task is complete, send a FINISH response."
    )
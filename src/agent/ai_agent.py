# src/agent/ai_agent.py
from langgraph.graph import StateGraph, END
import logging

from agent.state import AgentState
from agent.nodes import (
    supervisor_node, zeroshot_node, knowledge_node, 
    devops_node, qa_node, single_agent_node,
    closed_loop_single_agent_node
)

logger = logging.getLogger(__name__)

# ==========================================
# 構建狀態機拓撲圖 (Graph Topology)
# ==========================================
workflow = StateGraph(AgentState)

workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("ZeroShot_Expert", zeroshot_node)
workflow.add_node("RetrievalOnly_Expert", single_agent_node)
workflow.add_node("ClosedLoopSingleAgent_Expert", closed_loop_single_agent_node)
workflow.add_node("Knowledge_Expert", knowledge_node)
workflow.add_node("DevOps_Expert", devops_node)
workflow.add_node("QA_Expert", qa_node)

workflow.set_entry_point("Supervisor")

# 條件路由配置
workflow.add_conditional_edges(
    "Supervisor",
    lambda state: state["next_node"],
    {
        "ZeroShot_Expert": "ZeroShot_Expert",
        "RetrievalOnly_Expert": "RetrievalOnly_Expert",
        "ClosedLoopSingleAgent_Expert": "ClosedLoopSingleAgent_Expert",
        "Knowledge_Expert": "Knowledge_Expert",
        "DevOps_Expert": "DevOps_Expert",
        "QA_Expert": "QA_Expert",
        "FINISH": END
    }
)

# 非主管節點執行完畢後一律返回 Supervisor 進行狀態更新與重新分配
workflow.add_edge("ZeroShot_Expert", "Supervisor")
workflow.add_edge("RetrievalOnly_Expert", "Supervisor")
workflow.add_edge("ClosedLoopSingleAgent_Expert", "Supervisor")
workflow.add_edge("Knowledge_Expert", "Supervisor")
workflow.add_edge("DevOps_Expert", "Supervisor")
workflow.add_edge("QA_Expert", "Supervisor")

# 編譯應用程式 (導出供 main.py 使用)
mas_app = workflow.compile()

logger.info("LangGraph finished")
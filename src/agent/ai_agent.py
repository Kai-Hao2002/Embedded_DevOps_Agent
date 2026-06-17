import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from typing import Annotated, Literal, Sequence, TypedDict
import operator
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

# 引入您現有的 DevOps 自動化工具
# 引入你的自動化腳本工具
from langchain_core.tools import tool
from tools.run_keil_tool import build_project, flash_target
from tools.run_yocto_tool import remote_build_yocto, flash_image_uuu
from tools.serial_monitor_tool import monitor_uart_log
# 假設你已經有 retriever 或將 RAG 封裝成 tool
from tools.rag_tool import query_nxp_knowledge_base 

# ==========================================
# 工具封裝區 (Tool Wrapper Section)
# ==========================================

@tool
def compile_and_flash_mcu(dummy_arg: str = "") -> str:
    """
    用於編譯並燒錄 Cortex-M33 (MCU) 的 Keil 專案。
    不需要傳入參數。
    """
    is_success, build_report = build_project()
    if is_success:
        flash_target() # 執行燒錄
        return f"MCU 編譯與燒錄皆成功！\n日誌：\n{build_report}"
    else:
        return f"MCU 編譯失敗，未進行燒錄。詳細錯誤：\n{build_report}"

@tool
def compile_and_deploy_mpu(dummy_arg: str = "") -> str:
    """
    用於透過 SSH 觸發遠端 Yocto 伺服器進行 Cortex-A55 (MPU) 的映像檔編譯與 UUU 燒錄。
    不需要傳入參數。
    """
    is_success = remote_build_yocto()
    if is_success:
        flash_success = flash_image_uuu()
        if flash_success:
            return "Yocto 遠端編譯與 UUU 下載燒錄成功！"
        else:
            return "Yocto 編譯成功，但 UUU 燒錄失敗。"
    else:
        return "Yocto 遠端編譯失敗，請檢查伺服器狀態。"

@tool
def monitor_device_logs(port_name: str) -> str:
    """
    用於監聽實體或虛擬開發板的 UART 序列埠開機日誌 (Boot Logs)。
    必須傳入序列埠名稱 (例如 '/dev/ttys001') 作為參數。
    """
    success, report = monitor_uart_log(port_name, duration=8)
    return report

# ==========================================
# 1. 定義系統狀態 (State) - 加入 mode 欄位
# ==========================================
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_node: str
    mode: str  # 核心：控制實驗組 "B1", "B2", "B3", "PROPOSED_MAS"

# 主管節點路由決策約束
class RouteDecision(BaseModel):
    next_node: Literal["Knowledge_Expert", "DevOps_Expert", "QA_Expert", "ZeroShot_Expert", "FINISH"] = Field(
        description="決定下一個執行節點。若任務結束則回傳 FINISH。"
    )

# ==========================================
# 2. 初始化基礎大模型 (Claude 3.5 Sonnet)
# ==========================================
load_dotenv()
gemini_key = os.getenv("GEMINI_API_KEY")
#anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
if not gemini_key:
    raise ValueError("❌ Missing GEMINI_API_KEY in .env file!")
#if not anthropic_api_key:
    raise ValueError("❌ Missing ANTHROPIC_API_KEY in .env file!")
    
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=gemini_key, temperature=0)
#llm = ChatAnthropic(model="claude-3-5-sonnet-20240620", temperature=0)

# 建立具備專屬工具權限的底層 React Agent
knowledge_agent = create_react_agent(llm, tools=[query_nxp_knowledge_base])
devops_agent = create_react_agent(llm, tools=[compile_and_flash_mcu, compile_and_deploy_mpu])
qa_agent = create_react_agent(llm, tools=[monitor_device_logs])
zeroshot_agent = create_react_agent(llm, tools=[]) # B1 專用：完全無工具

# ==========================================
# 3. 實作動態消融實驗節點邏輯 (Node Functions)
# ==========================================
def supervisor_node(state: AgentState):
    """主管節點：根據 mode 進行嚴格的學術邊界動態路由"""
    current_mode = state.get("mode", "PROPOSED_MAS")
    
    # B1 模式：直接路由至零樣本專家，不進行任何 MAS 調度
    if current_mode == "B1":
        return {"next_node": "ZeroShot_Expert"}
        
    system_prompt = f"""你是一位嵌入式系統專案主管。目前系統運行在實驗對照組模式：[{current_mode}]。
    
    請遵循以下模式邊界進行決策：
    - B2 模式 (LLM+RAG 靜態輸出): 你只能指派 Knowledge_Expert 來提供手冊規範。你『絕對禁止』指派 DevOps_Expert 或 QA_Expert。當 Knowledge_Expert 回報後，必須立刻回傳 FINISH。
    - B3 模式 (MAS+編譯反饋): 你可以指派 DevOps_Expert 執行編譯，並可指派 Knowledge_Expert 查閱手冊。但你『絕對禁止』指派 QA_Expert 監聽序列埠。編譯回報後請直接回傳 FINISH。
    - PROPOSED_MAS (完整架構): 允許完整管線。DevOps_Expert 編譯成功後 -> 指派 QA_Expert 監聽 -> 若有 Crash 錯誤 -> 指派 Knowledge_Expert 分析原因 -> 解決後 FINISH。
    """
    
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    router_llm = llm.with_structured_output(RouteDecision)
    decision = router_llm.invoke(messages)
    
    return {"next_node": decision.next_node}

def zeroshot_node(state: AgentState):
    """B1 節點：Zero-shot 基準線，無任何外部工具與手冊支援"""
    sys_msg = SystemMessage(content="你是一位常規的嵌入式工程師。請僅依賴你預訓練知識回答，不允許使用 RAG 知識庫，亦不允許呼叫任何編譯或硬體工具。請直接給出程式碼修復建議。")
    inputs = [sys_msg] + state["messages"]
    result = zeroshot_agent.invoke({"messages": inputs})
    return {"messages": result["messages"][len(inputs):], "next_node": "FINISH"}

def knowledge_node(state: AgentState):
    """RAG 知識檢索節點"""
    sys_msg = SystemMessage(content="你是一位 NXP 手冊專家。請專注呼叫 query_nxp_knowledge_base 工具檢索精確數據，直接回報結果，不要反問。")
    baton = HumanMessage(content="[系統] 請查閱手冊庫，分析當前硬體配置或崩潰日誌。")
    inputs = [sys_msg] + state["messages"] + [baton]
    result = knowledge_agent.invoke({"messages": inputs})
    return {"messages": result["messages"][len(inputs):]}

def devops_node(state: AgentState):
    """DevOps 建置與編譯節點"""
    sys_msg = SystemMessage(content="你負責執行編譯與部署工具。請立刻呼叫工具執行任務，並如實回報編譯成功或失敗的純文字日誌。")
    baton = HumanMessage(content="[系統] 輪到 DevOps 專家行動，請立即扣動板機執行編譯/部署工具。")
    inputs = [sys_msg] + state["messages"] + [baton]
    result = devops_agent.invoke({"messages": inputs})
    return {"messages": result["messages"][len(inputs):]}

def qa_node(state: AgentState):
    """QA 實體/虛擬硬體序列埠監聽節點"""
    sys_msg = SystemMessage(content="你負責序列埠監聽。請立即使用預設埠號呼叫 monitor_device_logs 工具，抓取執行期崩潰特徵。")
    baton = HumanMessage(content="[系統] 燒錄完成，請立刻啟動序列埠監聽。")
    inputs = [sys_msg] + state["messages"] + [baton]
    result = qa_agent.invoke({"messages": inputs})
    return {"messages": result["messages"][len(inputs):]}

# ==========================================
# 4. 構建狀態機拓撲圖 (Graph Topology)
# ==========================================
workflow = StateGraph(AgentState)

workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("ZeroShot_Expert", zeroshot_node)
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
        "Knowledge_Expert": "Knowledge_Expert",
        "DevOps_Expert": "DevOps_Expert",
        "QA_Expert": "QA_Expert",
        "FINISH": END
    }
)

# 非主管節點執行完畢後一律返回 Supervisor 進行狀態更新與重新分配
workflow.add_edge("ZeroShot_Expert", "Supervisor")
workflow.add_edge("Knowledge_Expert", "Supervisor")
workflow.add_edge("DevOps_Expert", "Supervisor")
workflow.add_edge("QA_Expert", "Supervisor")

mas_app = workflow.compile()

# ==========================================
# 5. 互動式實驗測試迴圈 (Execution Loop)
# ==========================================
if __name__ == "__main__":
    # 🔬 在此一鍵切換實驗組進行測試: "B1", "B2", "B3", "PROPOSED_MAS"
    TEST_MODE = "PROPOSED_MAS" 
    
    print(f"🔬 論文消融實驗系統啟動 | 當前配置組 (Current Baseline): {TEST_MODE}")
    
    while True:
        user_text = input("\n👤 輸入硬體錯誤日誌或指令 (exit 離開): ")
        if user_text.lower() in ['exit', 'quit']:
            break
            
        # 核心：將當前的模式 (TEST_MODE) 注入到初始狀態中
        initial_state = {
            "messages": [HumanMessage(content=user_text)],
            "mode": TEST_MODE
        }
        
        for output in mas_app.stream(initial_state, {"recursion_limit": 20}):
            for node_name, state_update in output.items():
                print(f"\n--- 🔄 [Node] {node_name} 執行完畢 ---")
                if "messages" in state_update and state_update["messages"]:
                    print(state_update["messages"][-1].content)
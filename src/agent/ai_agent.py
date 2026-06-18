import os
import sys
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from typing import Annotated, Literal, Sequence, TypedDict
import operator
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from agent.test_plan_schema import TestPlanSchema
from pydantic import BaseModel, Field

# 引入您現有的 DevOps 自動化工具
# 引入你的自動化腳本工具
from langchain_core.tools import tool
from tools.run_keil_tool import build_project, flash_target
from tools.run_yocto_tool import trigger_remote_build, check_build_status, flash_image_uuu, download_remote_image
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
def start_mpu_build(dummy_arg: str = "") -> str:
    """
    用於觸發遠端 Yocto 伺服器進行 Cortex-A55 (MPU) 的映像檔編譯。
    此工具只會啟動任務，你必須後續呼叫 check_mpu_build_status 來確認結果。
    """
    return trigger_remote_build()

@tool
def check_mpu_build_status(dummy_arg: str = "") -> str:
    """
    用於檢查 Yocto 編譯進度。如果回報「進行中」，請等待並重新呼叫。
    如果回報「成功」，請接著呼叫 deploy_mpu_image 進行燒錄。
    """
    import time
    time.sleep(2) # 為了模擬真實情況，稍微等待再檢查
    return check_build_status()

@tool
def deploy_mpu_image(dummy_arg: str = "") -> str:
    """當 Yocto 編譯成功後，呼叫此工具下載 Image 並透過 UUU 燒錄。"""
    
    # 1. 先執行下載邏輯
    dl_success = download_remote_image()
    if not dl_success:
        return "❌ 下載遠端 Image 失敗，無法進行燒錄。"
        
    # 2. 確認下載成功後，再執行燒錄
    flash_success = flash_image_uuu()
    return "✅ UUU 燒錄成功！" if flash_success else "❌ UUU 燒錄失敗。"

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
    retry_count: int  # 記錄除錯迴圈次數

# 主管節點路由決策約束
class RouteDecision(BaseModel):
    next_node: Literal["Knowledge_Expert", "DevOps_Expert", "QA_Expert", "ZeroShot_Expert", "FINISH"] = Field(
        description="決定下一個執行節點。若任務結束則回傳 FINISH。"
    )

def generate_structured_test_plan(hardware_context: str, user_request: str) -> TestPlanSchema:
    """
    根據 RAG 檢索到的硬體手冊上下文與使用者需求，生成強制的結構化測試計畫。
    Generates a forced structured test plan based on the hardware manual context retrieved via RAG and user requirements.
    """
    # 建立專門用來引導結構化輸出的提示詞
    # Create a prompt specifically designed to guide structured output
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一位精通 NXP i.MX93 的資深嵌入式 QA 自動化工程師。
        請根據提供的手冊上下文（Context），為指定的硬體周邊生成完整的自動化測試計畫。
        你必須生成實體可執行的 Python 腳本，該腳本需利用 `mem` 或 `ReadAP` 指令讀取暫存器並進行斷言 (Assert)。
        
        硬體手冊上下文 / Hardware Manual Context:
        {context}
        """),
        ("human", "{input}")
    ])
    
    # 🌟 核心關鍵：將大語言模型與 Pydantic Schema 綁定
    # 🌟 Core Highlight: Bind the LLM with the Pydantic Schema
    structured_llm = llm.with_structured_output(TestPlanSchema)
    
    # 組合鏈並執行 / Combine the chain and execute
    chain = prompt | structured_llm
    result = chain.invoke({"context": hardware_context, "input": user_request})
    
    return result

# ==========================================
# 2. 初始化基礎大模型 (Claude 3.5 Sonnet)
# ==========================================
load_dotenv()
def get_llm(provider="gemini"):
    """
    動態獲取 LLM 實例 / Dynamically fetch the LLM instance
    """
    if provider == "gemini":
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            raise ValueError("❌ Missing GEMINI_API_KEY in .env file!")
        return ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=gemini_key, temperature=0)
    
    elif provider == "claude":
        # anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        # if not anthropic_api_key:
        #     raise ValueError("❌ Missing ANTHROPIC_API_KEY in .env file!")
        # return ChatAnthropic(model="claude-3-5-sonnet-20240620", api_key=anthropic_api_key, temperature=0)
        pass
    
    raise ValueError(f"Unknown provider: {provider}")

# 初始化 LLM / Initialize LLM
llm = get_llm(provider="gemini") 
# 當需要切換到 Claude 時，只需改為 / When switching to Claude, simply change to:
# llm = get_llm(provider="claude")

# 建立具備專屬工具權限的底層 React Agent
knowledge_agent = create_react_agent(llm, tools=[query_nxp_knowledge_base])
devops_agent = create_react_agent(llm, tools=[compile_and_flash_mcu, start_mpu_build, check_mpu_build_status, deploy_mpu_image])
qa_agent = create_react_agent(llm, tools=[monitor_device_logs])
zeroshot_agent = create_react_agent(llm, tools=[]) # B1 專用：完全無工具

# ==========================================
# 3. 實作動態消融實驗節點邏輯 (Node Functions)
# ==========================================
def supervisor_node(state: AgentState):
    """主管節點：根據 mode 進行嚴格的學術邊界動態路由"""
    current_mode = state.get("mode", "PROPOSED_MAS")
    
    if current_mode == "B1":
        return {"next_node": "ZeroShot_Expert"}
        
    system_prompt = f"""你是一位嵌入式系統專案主管。目前系統運行在實驗對照組模式：[{current_mode}]。
    
    請遵循以下模式邊界進行決策：
    - B2 模式 (LLM+RAG 靜態輸出): 你只能指派 Knowledge_Expert 來提供手冊規範。你『絕對禁止』指派 DevOps_Expert 或 QA_Expert。
    - B3 模式 (MAS+編譯反饋): 你可以指派 DevOps_Expert 執行編譯，並可指派 Knowledge_Expert 查閱手冊。你『絕對禁止』指派 QA_Expert 監聽序列埠。
    - PROPOSED_MAS (完整架構): 允許完整管線。
      1. 若需編譯與部署 -> 指派 DevOps_Expert
      2. 若需序列埠監聽 -> 指派 QA_Expert
      3. 若需錯誤分析與手冊查閱 -> 指派 Knowledge_Expert
      4. 🚨【重要】：如果使用者要求「生成測試計畫 (Test Plan)」，你『必須』指派 QA_Expert，因為只有 QA 專家具備自動化腳本的結構化輸出能力。
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
    sys_msg = SystemMessage(content="""你是一位 NXP 手冊專家。
    請專注呼叫 query_nxp_knowledge_base 工具檢索精確數據，直接回答結果，不要反問。
    【重要技巧】：如果使用者需要知道「基底位址(Base Address)」與「暫存器偏移(Register Offset)」，請務必呼叫工具兩次：
    第一次搜尋："LPI2C2 base address memory map"
    第二次搜尋："LPI2C SRDR register offset"
    不要試圖在一次搜尋中找齊所有資料。
    """)
    # ...
    baton = HumanMessage(content="[系統] 請查閱手冊庫，分析當前硬體配置或崩潰日誌。")
    inputs = [sys_msg] + state["messages"] + [baton]
    result = knowledge_agent.invoke({"messages": inputs})
    return {"messages": result["messages"][len(inputs):]}

def devops_node(state: AgentState):
    """DevOps 建置與編譯節點"""
    sys_msg = SystemMessage(content="""你負責執行編譯與部署工具。
    如果是 MCU 任務，請直接呼叫 compile_and_flash_mcu。
    如果是 MPU 任務，請遵循以下步驟：
    1. 呼叫 start_mpu_build 啟動任務。
    2. 呼叫 check_mpu_build_status 檢查狀態。如果還在進行中，請向使用者說明，並再次呼叫檢查。
    3. 成功後呼叫 deploy_mpu_image 進行燒錄。
    """)
    baton = HumanMessage(content="[系統] 輪到 DevOps 專家行動，請立即扣動板機執行編譯/部署工具。")
    inputs = [sys_msg] + state["messages"] + [baton]
    result = devops_agent.invoke({"messages": inputs})
    return {"messages": result["messages"][len(inputs):]}

def qa_node(state: AgentState):
    """QA 專家節點：支援序列埠監聽、結構化測試計畫生成與腳本輸出"""
    last_message = state["messages"][-1].content
    
    if "測試計畫" in last_message or "test plan" in last_message.lower():
        print("\n📋 [QA Expert] 偵測到測試計畫生成需求，正在啟動結構化輸出管線...")
        
        # 1. 呼叫 RAG 獲取硬體精確數據
        rag_context = query_nxp_knowledge_base.invoke("LPI2C2 memory map start address and register offsets")

        # 2. 生成結構化 JSON 物件
        structured_plan = generate_structured_test_plan(rag_context, last_message)
        
        # 🌟 3. 新增：將測試腳本寫入獨立的檔案中
        output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "generated_tests")
        os.makedirs(output_dir, exist_ok=True) # 如果資料夾不存在則建立
        
        saved_files = []
        for case in structured_plan.test_cases:
            # 建立安全的檔案名稱 (過濾掉可能導致路徑錯誤的字元)
            safe_name = case.test_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
            file_name = f"test_{safe_name}.py"
            file_path = os.path.join(output_dir, file_name)
            
            # 將 test_python_script 欄位寫入實體檔案
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Plan: {structured_plan.plan_title}\n")
                f.write(f"# Test: {case.test_name}\n")
                f.write(f"# Target Register: {case.target_register} ({case.register_address})\n\n")
                f.write(case.test_python_script)
                
            saved_files.append(file_name)
            print(f"✅ 已生成測試腳本: {file_path}")
        
        # 4. 統整結果回報給系統
        json_string = json.dumps(structured_plan.model_dump(), indent=2, ensure_ascii=False)
        report_msg = (
            f"📊 [測試計畫生成完畢]\n"
            f"成功產出 {len(saved_files)} 支測試腳本，已儲存於 `generated_tests` 目錄下：\n"
            f"{', '.join(saved_files)}\n\n"
            f"以下為完整的結構化資料：\n{json_string}"
        )
        
        return {"messages": [AIMessage(content=report_msg)], "next_node": "Supervisor"}
        
    else:
        # 原有的序列埠監聽邏輯
        sys_msg = SystemMessage(content="你負責序列埠監聽。請立即使用預設埠號呼叫 monitor_device_logs 工具。")
        inputs = [sys_msg] + state["messages"]
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
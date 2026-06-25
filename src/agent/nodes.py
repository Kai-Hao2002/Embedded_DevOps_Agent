# src/agent/nodes.py
import os
import re
import json
import time
import logging
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import create_react_agent

# 引入本模組的依賴
from agent.state import AgentState, RouteDecision
from agent.utils import get_llm, get_image_base64
from agent.test_plan_schema import TestPlanSchema
from agent.agent_tools import (
    compile_and_flash_mcu, start_mpu_build, check_mpu_build_status, 
    deploy_mpu_image, monitor_device_logs
)
# 引入 RAG 與 Patch 工具
from tools.rag_tool import query_nxp_knowledge_base 
from tools.patch_tool import apply_patch_tool, read_file_tool

logger = logging.getLogger(__name__)

# 初始化全域 LLM 與 Agent
llm = get_llm(provider="gemini")
knowledge_agent = create_react_agent(llm, tools=[query_nxp_knowledge_base, read_file_tool, apply_patch_tool])
devops_agent = create_react_agent(llm, tools=[compile_and_flash_mcu, start_mpu_build, check_mpu_build_status, deploy_mpu_image])
qa_agent = create_react_agent(llm, tools=[monitor_device_logs])
# B1: Zero-shot LLM, no tools.
zeroshot_agent = create_react_agent(llm, tools=[])
# B2: Single Agent + Text RAG, no build/deploy/runtime feedback.
retrieval_only_agent = create_react_agent(llm, tools=[
    query_nxp_knowledge_base, read_file_tool, apply_patch_tool,
])
# B3: Closed-loop single agent with all tools, but no specialist node separation.
closed_loop_single_agent = create_react_agent(llm, tools=[
    query_nxp_knowledge_base, read_file_tool, apply_patch_tool,
    compile_and_flash_mcu, start_mpu_build, check_mpu_build_status, deploy_mpu_image,
    monitor_device_logs
])

class VisionExtractionSchema(BaseModel):
    """
    定義視覺模型解析電路圖後的強制輸出格式
    Defines the mandatory output format after the vision model parses the schematic
    """
    chip_model: str = Field(description="萃取出的確切 IC 晶片型號 (例如: PCA9451A, WM8960, LSM6DSOXTR) / The exact IC Part Number extracted")
    bus_type: str = Field(description="連接的匯流排名稱或介面 (例如: I2C2, I2C1, SPI) / The connected bus name or interface")
    configuration_pins: str = Field(description="任何可見的硬體配置腳位，若無則填 'None' / Any visible hardware configuration pins, 'None' if not visible")

def generate_structured_test_plan(hardware_context: str, user_request: str) -> TestPlanSchema:
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a Senior Embedded QA Automation Engineer with deep expertise in the NXP i.MX93 platform.
        Based on the provided hardware manual context, generate a comprehensive automated test plan for the specified hardware peripheral.
        
        🚨 [CRITICAL RULES for Pytest Framework]:
        1. The test script MUST strictly adhere to the `pytest` framework standards.
        2. All validation functions MUST start with `test_` (e.g., `def test_lpi2c2_mcfgr0_reset_value():`).
        3. Rely ONLY on native Python `assert` statements for assertions. Do NOT use `try-except` blocks to catch AssertionErrors, and do NOT manually print PASS/FAIL.
        4. NEVER include an `if __name__ == "__main__":` block, and NEVER call `sys.exit()`.
        5. The script must include a simulated or actual register read/write function (e.g., `mem_read_32`) to ensure it runs independently without errors.
        
        Hardware Manual Context:
        {context}
        """),
        ("human", "{input}")
    ])
    structured_llm = llm.with_structured_output(TestPlanSchema)
    chain = prompt | structured_llm
    return chain.invoke({"context": hardware_context, "input": user_request})

def supervisor_node(state: AgentState):
    print("\n[System] The Supervisor node is starting up and sending a routing request to the LLM. Please wait...") 
    
    current_mode = state.get("mode", "PROPOSED_MAS")
    iteration_count = state.get("iteration_count", 0) # 取得當前迭代次數 (Get current iteration count)
    MAX_RETRIES = state.get("max_repair_iterations", 5) # Define Pass@k bound.

    if state.get("next_node") == "FINISH":
        return {"next_node": "FINISH"}
    
    if current_mode == "B1":
        return {"next_node": "ZeroShot_Expert"}
    if current_mode == "B2":
        return {"next_node": "RetrievalOnly_Expert"}
    if current_mode == "B3":
        return {"next_node": "ClosedLoopSingleAgent_Expert"}
        
    # 強制邊界防呆機制 (Boundary Guardrail Mechanism)
    if iteration_count >= MAX_RETRIES:
        logger.warning(f"[Supervisor] Reached maximum repair retry limit ({MAX_RETRIES}). Forcing task to FINISH to prevent infinite loop.")
        warning_msg = AIMessage(content=f"🛑 [System Guardrail] The maximum number of automated repair attempts ({MAX_RETRIES}) has been reached. The agent failed to resolve the issue autonomously. Please intervene manually.")
        # 覆寫狀態並強制結束 (Overwrite state and force finish)
        return {"next_node": "FINISH", "messages": [warning_msg]}
        
    system_prompt = f"""You are the Supervisor for a thesis-oriented multi-agent closed-loop BSP repair framework.
        Current execution mode: [{current_mode}].
        Current bounded repair iteration: {iteration_count}/{MAX_RETRIES}.

        Core workflow:
        AnalyzeFailure -> RetrieveKnowledge -> GeneratePatch -> ApplyPatch -> Build -> Deploy/MockDeploy -> ObserveRuntime -> StopOrRetry.
        
        Please follow this decision logic strictly:
        1. If the latest evidence is a build failure, runtime crash, or missing BSP context, route to `Knowledge_Expert`.
        2. If a patch was applied or the user asks to build/deploy, route to `DevOps_Expert`.
        3. If compilation/deployment succeeded and runtime validation is requested, route to `QA_Expert`.
        4. If `QA_Expert` reports Kernel Panic, HardFault, timeout, missing expected UART signature, or any crash pattern, route back to `Knowledge_Expert`.
        5. Select FINISH only when the latest evidence indicates build success and runtime success, or when human intervention is required.
        """
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    router_llm = llm.with_structured_output(RouteDecision)
    decision = router_llm.invoke(messages)
    print(f"   [System] Received LLM's reply! The task will now be assigned to: {decision.next_node}") 
    return {"next_node": decision.next_node}

def zeroshot_node(state: AgentState):
    sys_msg = SystemMessage(content="You are a standard embedded software engineer. Please answer relying solely on your pre-trained knowledge. You are NOT allowed to call any tools. Provide code fixing suggestions directly.")
    inputs = [sys_msg] + state["messages"]
    result = zeroshot_agent.invoke({"messages": inputs})
    return {"messages": result["messages"][len(inputs):], "next_node": "FINISH"}

def single_agent_node(state: AgentState):
    sys_msg = SystemMessage(content="You are a retrieval-only embedded BSP repair baseline (B2). You may use text RAG and patching tools, but you must not call build, deploy, flashing, or UART monitoring tools. Produce a patch or repair recommendation based only on retrieved text context.")
    inputs = [sys_msg] + state["messages"]
    result = retrieval_only_agent.invoke({"messages": inputs})
    return {"messages": result["messages"][len(inputs):], "next_node": "FINISH"}

def closed_loop_single_agent_node(state: AgentState):
    sys_msg = SystemMessage(content="""You are the closed-loop single-agent baseline (B3).
    You have access to retrieval, patching, build/deploy, and UART monitoring tools.
    Solve the issue sequentially by yourself, but do not rely on specialist multi-agent handoff.
    Stop when the build and runtime evidence indicate success or when the bounded repair attempt is exhausted.""")
    inputs = [sys_msg] + state["messages"]
    result = closed_loop_single_agent.invoke({"messages": inputs})
    return {"messages": result["messages"][len(inputs):], "next_node": "FINISH"}

def knowledge_node(state: AgentState):
    start_think = time.time()
    sys_msg = SystemMessage(content="""You are the Knowledge Expert for an embedded BSP closed-loop repair system.
    Your responsibilities correspond to AnalyzeFailure, RetrieveKnowledge, GeneratePatch, and ApplyPatch.
    1. Use `query_nxp_knowledge_base` to retrieve BSP manuals, source-code context, build documentation, or hardware notes.
    2. Before fixing code, use `read_file_tool` to read the exact current content of the broken file. Do not guess the code structure.
    3. Use `apply_patch_tool` for C source files, Device Tree files, linker scripts, or build configuration files.
    4. If evidence is insufficient or the target file is missing, clearly request human intervention instead of inventing a repair.
    """)
    baton = HumanMessage(content="[System] Analyze the latest build/runtime evidence, retrieve relevant BSP context, and apply a minimal patch if a repair is justified.")
    inputs = [sys_msg] + state["messages"] + [baton]
    result = knowledge_agent.invoke({"messages": inputs})
    think_time = time.time() - start_think
    
    # 每次大腦介入嘗試修復，迭代次數就加 1 (Increment iteration count every time the brain attempts a fix)
    current_iteration = state.get("iteration_count", 0)
    
    return {
        "messages": result["messages"][len(inputs):],
        "llm_thinking_time": state.get("llm_thinking_time", 0) + think_time,
        "iteration_count": current_iteration + 1,
        "current_stage": "ApplyPatch",
    }

def devops_node(state: AgentState):
    sys_msg = SystemMessage(content="""You are the DevOps Expert for the Build and Deploy/MockDeploy stages.
    For MCU tasks: Directly call `compile_and_flash_mcu`.
    For MPU tasks: Call `start_mpu_build` -> `check_mpu_build_status` -> `deploy_mpu_image` sequentially.
    """)
    baton = HumanMessage(content="[System] It is the DevOps Expert's turn. Please immediately trigger the build/deployment tools.")
    inputs = [sys_msg] + state["messages"] + [baton]
    result = devops_agent.invoke({"messages": inputs})
    new_messages = result["messages"][len(inputs):]
    joined = "\n".join(getattr(msg, "content", "") for msg in new_messages)
    build_passed = "success" in joined.lower() or "成功" in joined
    return {
        "messages": new_messages,
        "current_stage": "DeployOrMockDeploy" if build_passed else "Build",
        "build_passed": build_passed,
    }

def qa_node(state: AgentState):
    current_mode = state.get("mode", "PROPOSED_MAS")
    last_message = state["messages"][-1].content
    if "測試計畫" in last_message or "test plan" in last_message.lower():
        logger.info("[QA Expert] detects test plan generation requirement, initiating automated pipeline...")
        vision_context = ""
        extracted_chip = "LPI2C" 
        
        if current_mode == "B3":
            logger.warning("[QA Expert] Experiment Group B3 (Text-Only MAS) Startup: Force the multimodal vision module to shut down and ignore physical circuit diagram input.")
            vision_context = "\n[Mode B3: Text-Only. Vision disabled. Rely strictly on text search.]\n"
        else:
            img_match = re.search(r'([a-zA-Z0-9_./\\]+\.(?:png|jpg|jpeg))', last_message, re.IGNORECASE)
            if img_match:
                img_path = img_match.group(1)
                if os.path.exists(img_path):
                    logger.info(f"[QA Expert] Successfully loaded physical circuit diagram: {img_path}")
                    img_base64 = get_image_base64(img_path)
                    
                    # 1. 設定結構化視覺提取模型 (Setup structured vision LLM)
                    structured_vision_llm = llm.with_structured_output(VisionExtractionSchema)
                    
                    # 2. 構建視覺提示詞 (Construct vision prompt)
                    vision_messages = [
                        SystemMessage(content="""You are a Hardware Vision Expert. 
                                        Analyze the provided schematic. Extract the IC Part Number, bus type, and configuration pins accurately."""),
                        HumanMessage(content=[
                            {"type": "text", "text": "What is the exact chip model and bus connection shown in this schematic?"},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                        ])
                    ]
                    
                    # 3. 動態解析與組裝 (Dynamic parsing and assembly)
                    try:
                        vision_result = structured_vision_llm.invoke(vision_messages)
                        vision_context = (
                            f"\n[AI Visual Schematic Analysis Report]\n"
                            f"- Extracted Chip Model: {vision_result.chip_model}\n"
                            f"- Connected Bus: {vision_result.bus_type}\n"
                            f"- Configuration Pins: {vision_result.configuration_pins}\n"
                        )
                        logger.info(f"[QA Expert] Vision parsing succeeded: {vision_result.chip_model} on {vision_result.bus_type}")
                        
                        # 動態生成 extracted_chip，消除硬編碼
                        extracted_chip = f"{vision_result.chip_model} {vision_result.bus_type} device address and memory map"
                        
                    except Exception as e:
                        logger.error(f"[QA Expert] Vision structured parsing failed: {e}")
                        vision_context = "\n[AI Visual Schematic Analysis Report]\nFailed to extract structured data from schematic.\n"
                else:
                    logger.warning(f"[QA Expert] Image file not found: {img_path}")

        # 4. 動態查詢 RAG (Dynamic RAG query)
        rag_query = f"{extracted_chip} setup in i.MX93 EVK"
        rag_context = query_nxp_knowledge_base.invoke(rag_query)

        combined_context = (
            f"Physical Schematic Analysis State:\n{vision_context}\n-------------------\n"
            f"Official Manual & Pinout Exact Addresses:\n{rag_context}\n-------------------\n"
            f"Please write validation code to perform Read/Write operations on this I2C device."
        )
        
        structured_plan = generate_structured_test_plan(combined_context, last_message)
        
        output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "generated_tests")
        os.makedirs(output_dir, exist_ok=True)
        saved_files = []
        for case in structured_plan.test_cases:
            safe_name = case.test_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
            file_name = f"test_{safe_name}.py"
            file_path = os.path.join(output_dir, file_name)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Plan: {structured_plan.plan_title}\n")
                f.write(f"# Target Architecture: {structured_plan.target_architecture}\n")
                f.write(f"# Target Register/Device: {case.target_register} ({case.register_address})\n\n")
                f.write(case.test_python_script)
            saved_files.append(file_name)
        
        report_msg = f"📊 [Test Plan Generated]\nSuccessfully generated {len(saved_files)} test scripts and saved them in the `generated_tests` directory:\n{', '.join(saved_files)}"
        return {"messages": [AIMessage(content=report_msg)], "next_node": "FINISH"}
    else:
        sys_msg = SystemMessage(content="""You are the QA Expert for the ObserveRuntime stage.
        Monitor UART or mock UART logs, report whether expected success signatures appear, and flag crash patterns such as Kernel Panic, HardFault, timeout, or peripheral initialization failure.""")
        inputs = [sys_msg] + state["messages"]
        result = qa_agent.invoke({"messages": inputs})
        new_messages = result["messages"][len(inputs):]
        joined = "\n".join(getattr(msg, "content", "") for msg in new_messages)
        functional_passed = "operating normally" in joined.lower() or "正常" in joined or "✅" in joined
        return {
            "messages": new_messages,
            "current_stage": "ObserveRuntime",
            "functional_passed": functional_passed,
        }
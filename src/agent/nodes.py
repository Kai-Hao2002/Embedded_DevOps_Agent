# src/agent/nodes.py
import os
import re
import json
import time
import logging
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
#B1
zeroshot_agent = create_react_agent(llm, tools=[]) 
#B2
single_agent = create_react_agent(llm, tools=[
    query_nxp_knowledge_base, apply_patch_tool,
    compile_and_flash_mcu, start_mpu_build, check_mpu_build_status, deploy_mpu_image,
    monitor_device_logs
])

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
    # 🎯 新增除錯訊息 1
    print("\n[System] The Supervisor node is starting up and sending a routing request to the LLM. Please wait...") 
    
    current_mode = state.get("mode", "PROPOSED_MAS")
    if current_mode == "B1":
        return {"next_node": "ZeroShot_Expert"}
    if current_mode == "B2":
        return {"next_node": "SingleAgent_Expert"}
        
    system_prompt = f"""You are an Embedded Systems Project Supervisor. Current execution mode: [{current_mode}].
        
        Please follow this decision logic strictly:
        1. For compilation and deployment tasks -> Route to `DevOps_Expert`.
        2. For serial port monitoring, OR requests to analyze schematics and generate test plans -> Route to `QA_Expert`.
        3. Upon encountering errors (e.g., build failures or Kernel Panics) -> Route to `Knowledge_Expert` to consult manuals and generate a patch.
        4. 🚨 [Feedback Loop]: If `Knowledge_Expert` reports "Patch applied successfully", you MUST route back to `DevOps_Expert` to recompile and verify the fix.
        5. 🛑 [Human Intervention]: If `Knowledge_Expert` requests human intervention (e.g., "file not found", "please modify manually"), the automated fixing limit has been reached. You MUST immediately select FINISH to end the task. NEVER continue routing to `DevOps_Expert` autonomously.
        6. Select FINISH ONLY when the final logs show complete success, no human intervention is needed, and all user requests are fulfilled.
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
    sys_msg = SystemMessage(content="You are an all-in-one embedded systems engineer. You have access to ALL tools including knowledge retrieval, code patching, compilation, and UART monitoring. Attempt to solve the user's issue sequentially by yourself.")
    inputs = [sys_msg] + state["messages"]
    result = single_agent.invoke({"messages": inputs})
    return {"messages": result["messages"][len(inputs):], "next_node": "FINISH"}

def knowledge_node(state: AgentState):
    start_think = time.time()
    sys_msg = SystemMessage(content="""You are an NXP Systems Expert.
    1. Use `query_nxp_knowledge_base` to retrieve hardware manuals.
    2. 🚨 [CRITICAL]: Before fixing any code, you MUST use `read_file_tool` to read the exact current content of the broken file. Do NOT guess the code structure!
    3. Use `apply_patch_tool` to modify the source code. Your `search_context` MUST be an exact copy-paste from the output of `read_file_tool`.
    """)
    baton = HumanMessage(content="[System] Please consult the knowledge base to analyze the hardware configuration or crash logs. Attempt to use the patch tool if code modification is needed; if it fails, output your suggestions directly.")
    inputs = [sys_msg] + state["messages"] + [baton]
    result = knowledge_agent.invoke({"messages": inputs})
    think_time = time.time() - start_think
    return {
        "messages": result["messages"][len(inputs):],
        "llm_thinking_time": state.get("llm_thinking_time", 0) + think_time
    }

def devops_node(state: AgentState):
    sys_msg = SystemMessage(content="""You are responsible for executing build and deployment tools.
    For MCU tasks: Directly call `compile_and_flash_mcu`.
    For MPU tasks: Call `start_mpu_build` -> `check_mpu_build_status` -> `deploy_mpu_image` sequentially.
    """)
    baton = HumanMessage(content="[System] It is the DevOps Expert's turn. Please immediately trigger the build/deployment tools.")
    inputs = [sys_msg] + state["messages"] + [baton]
    result = devops_agent.invoke({"messages": inputs})
    return {"messages": result["messages"][len(inputs):]}

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
                    vision_prompt = [
                        SystemMessage(content="""You are a Hardware Vision Expert. 
                                        Analyze the provided schematic. Extract:
                                        1. The exact IC Part Number (e.g., PCA9451A)
                                        2. The connected bus name (e.g., I2C2, UART1)
                                        3. Any visible hardware configuration pins (e.g., BOOT_MODE, I2C address selection pins)
                                        Output this strictly as structured text."""),
                        HumanMessage(content=[
                            {"type": "text", "text": "What is the PMIC chip model shown in this schematic?"},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                        ])
                    ]
                    vision_result = llm.invoke(vision_prompt).content
                    vision_context = f"\n[AI Visual Schematic Analysis Report]\n{vision_result}\n"
                    if "PCA9451" in vision_result.upper():
                        extracted_chip = "PCA9451A PMIC I2C address and LPI2C2 memory map"
                else:
                    logger.warning(f"[QA Expert] Image file not found: {img_path}")

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
        sys_msg = SystemMessage(content="You are responsible for serial port monitoring. Please immediately call the `monitor_device_logs` tool using the default port.")
        inputs = [sys_msg] + state["messages"]
        result = qa_agent.invoke({"messages": inputs})
        return {"messages": result["messages"][len(inputs):]}
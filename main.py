#main.py
import os
import sys
import logging
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

os.makedirs("logs", exist_ok=True)
log_file_path = os.path.join("logs", "agent_system.log")

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)                    
    ]
)

logger = logging.getLogger("Main")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

load_dotenv()

from src.agent.ai_agent import mas_app

def print_banner():
    """印出系統啟動橫幅/print banner"""
    print("=" * 65)
    print("🚀 Embedded BSP Closed-Loop Repair Multi-Agent System")
    print(f"⚙️  執行模式 (Execution Mode): {os.getenv('EXECUTION_MODE', 'MOCK')}")
    print(f"📊 LangSmith 追蹤 (Tracking): {os.getenv('LANGCHAIN_TRACING_V2', 'false')}")
    print("=" * 65)
    print("可接受指令類型 (Supported Commands):")
    print("  1. MCU 編譯與燒錄 (MCU compile and flash)")
    print("  2. MPU 遠端 Yocto 建置 (MPU remote Yocto build)")
    print("  3. 序列埠/Mock UART 閉環驗證 (UART or mock UART validation)")
    print("  4. BSP 錯誤分析、RAG 檢索與 patch 修復 (BSP repair loop)")
    print("=" * 65)

def main():
    print_banner()
    logger.info("The embedded DevOps agent system has been launched.")
    
    TEST_MODE = "PROPOSED_MAS" # Change to "B1", "B2", "B3" 或 "PROPOSED_MAS"
    
    while True:
        try:
            user_text = input("\n👤 Enter the hardware error log or command (exit): ")
            if user_text.lower() in ['exit', 'quit']:
                logger.info("The system is shutting down safely...")
                break
                
            if not user_text.strip():
                continue
                
            logger.info(f"Receive user text {user_text}")
            
            initial_state = {
                "messages": [HumanMessage(content=user_text)],
                "mode": TEST_MODE,
                "next_node": "",
                "current_stage": "AnalyzeFailure",
                "iteration_count": 0,
                "max_repair_iterations": 5,
                "start_time": 0.0,
                "tool_error_count": 0,
                "llm_thinking_time": 0.0,
                "tool_exec_time": 0.0,
                "build_passed": False,
                "functional_passed": False,
                "expected_uart_regex": "",
                "crash_patterns": ["Kernel panic", "HardFault", "Segmentation fault"],
                "repair_history": []
            }

            for output in mas_app.stream(initial_state, {"recursion_limit": 100}):
                for node_name, state_update in output.items():
                    logger.info(f"--- 🔄 [Node] {node_name} executes finished ---")
                    if "messages" in state_update and state_update["messages"]:
                        raw_content = state_update['messages'][-1].content
                        if isinstance(raw_content, list):
                            safe_content = " ".join(str(c.get("text", c)) if isinstance(c, dict) else str(c) for c in raw_content)
                        else:
                            safe_content = str(raw_content)
                        print(f"\n🤖 {node_name} reports:\n{safe_content}\n")
        except KeyboardInterrupt:
            logger.warning("Upon receiving the interrupt signal (KeyboardInterrupt), the system safely exits.")
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred during system runtime:{e}", exc_info=True)

if __name__ == "__main__":
    main()

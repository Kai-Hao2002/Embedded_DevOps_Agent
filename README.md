# 🤖 AI-Driven Embedded DevOps Agent for NXP i.MX93

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-orange)
![LLM](https://img.shields.io/badge/LLM-Claude%203.5%20%7C%20Gemini%201.5-green)
![NXP](https://img.shields.io/badge/Hardware-NXP%20i.MX93-lightgrey)

This project implements a fully automated, Large Language Model (LLM) based Embedded DevOps system designed specifically for the NXP i.MX93 heterogeneous multi-core architecture (Cortex-A55 + Cortex-M33). 

By integrating **Retrieval-Augmented Generation (RAG)**, **Multimodal Vision**, and **LangGraph Multi-Agent Systems (MAS)**, the agent autonomously performs compiling, flashing, run-time crash monitoring, and hardware schematic analysis, achieving a closed-loop "Self-Healing" development workflow.

---

## 🌟 Core Features

1. **🧠 LangGraph Multi-Agent System (MAS)**
   - A Supervisor agent dynamically routes tasks to specialized experts (`DevOps_Expert`, `QA_Expert`, `Knowledge_Expert`) with built-in Circuit Breaker logic for graceful degradation.
2. **⚡ Automated Multi-Core Deployment**
   - **MCU (Cortex-M33)**: Headless build via Keil MDK CLI and one-click flashing via SEGGER J-Link.
   - **MPU (Cortex-A55)**: Automated Yocto Bitbake via SSH, SFTP image retrieval, and eMMC deployment via NXP UUU.
3. **📚 Hybrid RAG Knowledge Base (Ensemble Retriever)**
   - Combines Semantic Search (ChromaDB) and Keyword Search (BM25) across thousands of pages of NXP Reference Manuals, EVK User Guides, and Porting Guides.
4. **👁️ Multimodal Schematic Analysis to Pytest**
   - Utilizing Vision models to read physical circuit Schematics, identify PMIC/Sensor I2C addresses, cross-reference the RAG memory map, and automatically generate `pytest`-compatible validation scripts.
5. **🐒 Chaos Engineering & Mock Environment**
   - Built-in "Chaos Monkey" for local testing without physical hardware. Simulates random Kernel Panics, UART gibberish, and Yocto fetch network failures to train the AI's resilience.
6. **📊 Enterprise Observability**
   - Full integration with Python `logging` for persistent tracking and **LangSmith** for visual graph tracing and token cost monitoring.

---

## 📁 Project Directory Structure

```text
Intern_AI_Agent/
 │
 ├── main.py                        # 🚀 System Entry Point (CLI)
 ├── .env                           # Environment configurations (Keys, Execution Mode)
 │
 ├── docs/                          # Raw Manuals & Schematics
 ├── chroma_db/                     # Vector Database (Auto-generated)
 ├── logs/                          # Persistent System Execution Logs
 ├── generated_tests/               # AI-generated pytest scripts
 │
 ├── src/                           # Core Source Code
 │   ├── agent/
 │   │   ├── ai_agent.py            # LangGraph State Machine & Agent Nodes
 │   │   └── test_plan_schema.py    # Pydantic schema for structured test plans
 │   │
 │   ├── tools/                     # DevOps Automation Tools
 │   │   ├── run_keil_tool.py       # MCU build & flash logic
 │   │   ├── run_yocto_tool.py      # MPU remote deployment & SSH retry logic
 │   │   ├── serial_monitor_tool.py # UART crash listening tool
 │   │   ├── patch_tool.py          # Auto-patching & Diff generation
 │   │   └── rag_tool.py            # Ensemble Retriever tool wrapper
 │   │
 │   ├── mock/                      # Hardware-free Simulation Stubs (Chaos Monkey)
 │   │   ├── mock_keil.py           # Simulates fatal errors, linker errors, etc.
 │   │   ├── mock_jlink.py
 │   │   └── mock_board_uart.py     # Simulates Kernel Panics and timeouts
 │   │
 │   └── rag/                       # Knowledge Base Pipelines
 │       ├── ingest_data.py         # Parses PDFs/Web to build ChromaDB & BM25
 │       └── evaluate_rag.py        # Automated RAG accuracy evaluation
 │
 ├── target_workspace/             # Target Embedded Projects
 │   ├── mcu_firmware/             # Keil MDK project (.c, .h, .uvprojx)
 │   └── mpu_linux_bsp/            # Yocto/Linux BSP project (.dts, .dtsi, recipes)
 │
 ├── experiments/                  # Evaluation & Datasets
 │   ├── benchmark_retrieval/      # retrieval benchmark 
 │   ├── fault_injection/          # fault injection dataset
 │   │   ├── bugs_def.json         # bug definition
 │   │   └── backup_clean_code/    # clean code backup
 │   └── results/                  
 │
 ├── patches/                       # Auto-generated .patch files for Git
 ├── flash_m33.jlink                # J-Link command script
 └── requirements.txt               # Dependencies
```

## 🚀 快速啟動 (Quick Start)

### 1. Environment Setup
   ```bash
   python3.10 -m venv venv
   # Windows: .\venv\Scripts\activate
   # macOS/Linux: source venv/bin/activate

   pip install --upgrade pip
   pip install -r requirements.txt
   ```
### 1. Install Dependencies
Clone the repository and set up your Python environment:
   ```bash
   pip freeze > requirements.txt
   docker build -t mock-yocto .
   docker run -d -p 2222:22 --name yocto-server mock-yocto
   python src/tools/run_keil_tool.py
   python src/tools/run_yocto_tool.py
   python src/mock/mock_board_uart.py
   python src/agent/ai_agent.py
   ```
Create a .env file in the project root:
   ```bash
   # LLM API Keys
   ANTHROPIC_API_KEY="your_actual_anthropic_api_key_here"
   GEMINI_API_KEY="your_actual_gemini_api_key_here"

   # Yocto Build Server SSH Configurations
   YOCTO_SSH_HOST=127.0.0.1
   YOCTO_SSH_PORT=2222
   YOCTO_SSH_USER=root
   YOCTO_SSH_PASS=yocto

   # Target Board Configurations
   TARGET_SERIAL_PORT=/dev/ttys000
   TARGET_BAUDRATE=115200

   # Execution Mode: MOCK (Simulation) or REAL (Physical Hardware)
   EXECUTION_MODE=MOCK

   # Keil and JLink real path
   KEIL_REAL_PATH="C:\Keil_v5\UV4\UV4.exe"
   JLINK_REAL_PATH="C:\Program Files\SEGGER\JLink\JLink.exe"


   # (Optional) LangSmith Observability
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
   LANGCHAIN_API_KEY=""your_actual_langchain_api_key_here""
   LANGCHAIN_PROJECT="iMX93_DevOps_Agent"
   ```
#### 2. Build the Knowledge Base (RAG)
Parse the NXP manuals and build the local vector database:
   ```bash
   python src/rag/ingest_data.py
   ```

#### 3. Run the AI DevOps Agent
**Start the Multi-Agent System via the main entry point:**
   ```bash
   python main.py
   ```
**Example Prompts to try:**
- "請幫我編譯 MCU 專案。如果成功，請幫我監聽序列埠 /dev/ttys000的開機日誌。如果不幸失敗，請告訴我原因。"  (Please compile the MCU project. If successful, please monitor the boot logs on serial port /dev/ttys001 (replace with actual port). If it fails, please tell me the reason.)
- "請幫我看 docs/sensor_schematic.png 這張電源樹電路圖，找出上面的 PMIC 晶片型號。接著，請生成一份完整的測試計畫 (Test Plan)，驗證這個 PMIC 在 I2C 總線上的連線狀態是否正常。" (Please look at the power tree schematic docs/sensor_schematic.png and identify the PMIC chip model on it. Next, please generate a complete Test Plan to verify if this PMIC's connection on the I2C bus is functioning properly.)

**Automated Testing (QA Automation)**
When the QA_Expert agent generates test plans, they are automatically saved into the generated_tests/ directory following the standard pytest format.

To run the generated hardware validation scripts and generate a report:
``` bash
pip install pytest pytest-html
pytest generated_tests/ --html=report.html -v
```

Developed as part of the NXP i.MX93 Embedded DevOps Automation Initiative.

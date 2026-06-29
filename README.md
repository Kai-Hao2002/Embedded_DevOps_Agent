# AI-Driven Embedded BSP Closed-Loop Repair Agent for NXP i.MX93

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-orange)
![LLM](https://img.shields.io/badge/LLM-Claude%203.5%20%7C%20Gemini%202.5-green)
![NXP](https://img.shields.io/badge/Hardware-NXP%20i.MX93-lightgrey)
![Status](https://img.shields.io/badge/Status-Enterprise_Ready-success)

This project implements a Large Language Model (LLM) based embedded BSP repair framework for the NXP i.MX93 heterogeneous multi-core architecture (Cortex-A55 + Cortex-M33).

The current research focus is a **multi-agent closed-loop repair workflow** for BSP build and runtime failures. The system repeatedly performs `AnalyzeFailure -> RetrieveKnowledge -> GeneratePatch -> ApplyPatch -> Build -> Deploy/MockDeploy -> ObserveRuntime -> StopOrRetry` under a bounded retry budget. 

Built with enterprise-grade resilience, the framework seamlessly switches between Hardware-in-the-Loop (HIL) and Mock environments, incorporates chaos engineering, and utilizes token-efficient log extraction to accurately resolve complex embedded software failures.

---


## 🌟 Core Features

1. **LangGraph Multi-Agent Closed Loop**
   - A Supervisor routes work to `Knowledge_Expert`, `DevOps_Expert`, `Patch_Expert`, and `QA_Expert` under a bounded Pass@k repair budget.
2. **Hardware Abstraction Layer (HAL) for Seamless Execution**
   - Employs Strategy and Factory patterns (`hal_mcu.py`, `hal_mpu.py`) to completely decouple agent logic from underlying toolchains. Switch between real J-Link/Yocto servers and local Mock environments simply by changing the `EXECUTION_MODE` env variable.
3. **Chaos-Resilient QA & Hardware Self-Healing**
   - The `QA_Expert` handles simulated chaos (Kernel Panics, Baudrate mismatches, UART Timeouts) and can actively trigger a `reset_target_board` tool to power-cycle unresponsive physical or mock hardware.
4. **Token-Efficient Smart Log Truncation**
   - Instead of overwhelming the LLM Context Window with 10,000+ lines of BitBake logs, the DevOps tool extracts hierarchical "Error Summaries" and "Detailed Log Paths", forcing the `Knowledge_Expert` to actively explore specific task logs, significantly improving Token Efficiency.
5. **Domain-Isolated Hybrid RAG Knowledge Base**
   - Combines semantic retrieval (ChromaDB) and keyword retrieval (BM25). Documents and source code are tagged with `target_core` (e.g., A55 vs. M33) metadata during ingestion to prevent cross-domain hallucination.
6. **Ablation Baselines for the Thesis**
   - `B1`: Zero-Shot LLM.
   - `B2`: Single Agent + Text RAG.
   - `B3`: Closed-Loop Single Agent.
   - `PROPOSED_MAS`: Multi-Agent Closed-Loop Framework.

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
 │   │   ├── ai_agent.py            # LangGraph State Machine 
 │   │   ├── agent_tools.py   
 │   │   ├── nodes.py  
 │   │   ├── state.py  
 │   │   ├── utils.py  
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
 │   ├── benchmark_retrieval/      # RQ2 retrieval benchmark
 │   ├── fault_injection/          # closed-loop repair dataset
 │   │   ├── bugs_def.json         # bug definitions, golden patches, UART signatures
 │   │   └── backup_clean_code/    # clean code backup
 │   ├── experiment_runner.py
 │   ├── real_logs/ 
 │   └── results/                  
 │
 ├── docs_config.json 
 ├── patches/                       # Auto-generated .patch files for Git
 ├── flash_m33.jlink                # J-Link command script
 └── requirements.txt               # Dependencies
```

## 🚀 快速啟動 (Quick Start)

### 1. Environment Setup
   ```bash
   python3.10 -m venv venv
   conda deactivate
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
- "請根據 Yocto/DTS/Keil 錯誤日誌進行閉環修復，產生 patch，重新建置，並使用 UART 或 mock UART 驗證結果。"

## Thesis Experiment Modes

Run the automated closed-loop BSP repair benchmark (generates Pass@k, MTTR, Token Efficiency metrics):

```bash
python experiments/experiment_runner.py
```

Run the retrieval benchmark for RQ2 (generates MRR, Recall@5, Top-5 Accuracy metrics):

```bash
python src/rag/evaluate_rag.py
```

Developed as part of an Advanced Embedded DevOps Automation Initiative for NXP i.MX93.

# AI-Driven Embedded BSP Closed-Loop Repair Agent for NXP i.MX93

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-orange)
![LLM](https://img.shields.io/badge/LLM-Claude%203.5%20%7C%20Gemini%201.5-green)
![NXP](https://img.shields.io/badge/Hardware-NXP%20i.MX93-lightgrey)

This project implements a Large Language Model (LLM) based embedded BSP repair framework for the NXP i.MX93 heterogeneous multi-core architecture (Cortex-A55 + Cortex-M33).

The current research focus is a **multi-agent closed-loop repair workflow** for BSP build and runtime failures. The system repeatedly performs `AnalyzeFailure -> RetrieveKnowledge -> GeneratePatch -> ApplyPatch -> Build -> Deploy/MockDeploy -> ObserveRuntime -> StopOrRetry` under a bounded retry budget.

Hybrid RAG, mock toolchains, and UART/mock-UART validation provide measurable evidence for Pass@k, Functional Pass Rate, MRR, MTTR, token cost, and tool invocation reliability. Multimodal schematic analysis and cross-model comparison are treated as extended evaluation paths, not requirements for the core thesis experiment.

---

## 🌟 Core Features

1. **LangGraph Multi-Agent Closed Loop**
   - A Supervisor routes work to `Knowledge_Expert`, `DevOps_Expert`, and `QA_Expert` under a bounded Pass@k repair budget.
2. **Ablation Baselines for the Thesis**
   - `B1`: Zero-Shot LLM.
   - `B2`: Single Agent + Text RAG.
   - `B3`: Closed-Loop Single Agent.
   - `PROPOSED_MAS`: Multi-Agent Closed-Loop Framework.
3. **Hybrid RAG Knowledge Base**
   - Combines semantic retrieval (ChromaDB) and keyword retrieval (BM25) for BSP manuals, source files, build logs, and project documentation.
4. **Build, Deploy, and Runtime Feedback**
   - MCU path: Keil MDK CLI and J-Link compatible mock/real tools.
   - MPU path: Yocto BitBake and UUU compatible mock/real tools.
   - Runtime path: UART or mock UART validation with expected signatures and crash dictionaries.
5. **Reproducible BSP Repair Benchmark**
   - Fault cases include raw error prompts, broken files, golden patch descriptions, retrieval mappings, expected UART regexes, and crash patterns.
6. **Experiment Metrics**
   - Reports Pass@k, Functional Pass Rate, MTTR, token efficiency, tool errors, agent steps, and agentic interaction overhead.

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
 │   ├── benchmark_retrieval/      # RQ2 retrieval benchmark
 │   ├── fault_injection/          # closed-loop repair dataset
 │   │   ├── bugs_def.json         # bug definitions, golden patches, UART signatures
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

The experiment runner uses the modes defined in the revised thesis proposal:

- `B1`: Zero-Shot LLM
- `B2`: Single Agent + Text RAG
- `B3`: Closed-Loop Single Agent
- `PROPOSED_MAS`: Multi-Agent Closed-Loop Framework

Run the closed-loop BSP repair benchmark:

```bash
python experiments/experiment_runner.py
```

Run the retrieval benchmark for RQ2:

```bash
python src/rag/evaluate_rag.py
```

Developed as part of the NXP i.MX93 Embedded DevOps Automation Initiative.

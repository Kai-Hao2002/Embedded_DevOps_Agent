import os
import pickle
import time
import pandas as pd
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains import create_retrieval_chain
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever

DB_PATH = "./chroma_db"

def setup_rag_chain():
    """初始化 LLM 與檢索鏈 (Initialize LLM and Retrieval Chain)"""
    load_dotenv()
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise ValueError("❌ Missing GEMINI_API_KEY in .env file!")
    
    # 1. 載入模型 (Load Model)
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=gemini_key, temperature=0)

    # 2. 連結資料庫 (Connect to DB)
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"❌ Database not found at {DB_PATH}. Run ingest_data.py first.")
    
    # 1. 載入 Chroma 語意檢索器 (Load Chroma Semantic Retriever)
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = Chroma(persist_directory=DB_PATH, embedding_function=embeddings)
    chroma_retriever = vectorstore.as_retriever(search_kwargs={"k": 10})

    # 2. 🌟 新增：載入 BM25 關鍵字檢索器 (Load BM25 Keyword Retriever)
    if not os.path.exists("splits.pkl"):
        raise FileNotFoundError("❌ splits.pkl not found! Run ingest_data.py first.")
    with open("splits.pkl", "rb") as f:
        splits = pickle.load(f)
    bm25_retriever = BM25Retriever.from_documents(splits)
    bm25_retriever.k = 10

    # 3. 🌟 新增：融合兩個檢索器 (Combine both into an Ensemble Retriever)
    # weights=[0.5, 0.5] 代表語意和關鍵字各佔 50% 權重
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, chroma_retriever], weights=[0.5, 0.5]
    )

    # 3. 建立問答鏈 (Build QA Chain)
    system_prompt = (
        "You are an expert embedded systems engineer assisting with the NXP i.MX93 EVB. "
        "Use the following pieces of retrieved context to answer the question. "
        "If you don't know the answer, say that you don't know based on the context. "
        "Always provide precise register addresses, offsets, or tool commands if mentioned.\n\n"
        "{context}"
    )
    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{input}")])
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(ensemble_retriever, question_answer_chain)
    return rag_chain

def run_evaluation():
    """執行自動化測試並產生報告 (Run automated tests and generate report)"""
    print("🚀 Initializing Auto-Evaluator...")
    try:
        rag_chain = setup_rag_chain()
    except Exception as e:
        print(f"Initialization Error: {e}")
        return

    # ==========================================
    # 🧪 升級版測試題庫 (Upgraded Test Suite)
    # 涵蓋 RM, EVK, Yocto, Porting Guide 與 Test Plan
    # ==========================================
    test_suite = [
        {
            "Level": "1 (Basic)", 
            "Topic": "Board Physical (EVK)", 
            "Question": "According to the i.MX 93 EVK Board User Manual, what is the I2C address of the PMIC (PCA9451A), and which I2C bus is it connected to?"
        },
        {
            "Level": "1 (Basic)", 
            "Topic": "MCU Memory Map (RM)", 
            "Question": "What is the memory base address of the LPI2C2 module on the i.MX93?"
        },
        {
            "Level": "2 (Cross-Doc)", 
            "Topic": "Boot Configuration", 
            "Question": "I want to boot the i.MX 93 EVK from the onboard eMMC. According to the board manual and reference manual, what should be the value of the BOOT_MODE[3:0] DIP switches?"
        },
        {
            "Level": "2 (Yocto/Build)", 
            "Topic": "Yocto Bitbake", 
            "Question": "In the Yocto Project, which specific bitbake task is responsible for fetching the source code, and what 'devtool' command can I use to modify a recipe's source code interactively?"
        },
        {
            "Level": "2 (System/Arch)", 
            "Topic": "Dual-Core IPC", 
            "Question": "How does the Cortex-A55 communicate with the Cortex-M33 in the i.MX93? Briefly explain the role of the Messaging Unit (MU)."
        },
        {
            "Level": "3 (Advanced)", 
            "Topic": "Linux Device Tree", 
            "Question": "Based on the i.MX Porting Guide, what are the essential properties I need to define in a Device Tree (DTS) node to enable an I2C sensor device on the LPI2C bus?"
        },
        {
            "Level": "3 (Advanced)", 
            "Topic": "Test Plan Generation", 
            "Question": "I need to write a test plan for the LPUART interface. According to the 'Unit Tests' chapter in the i.MX Linux Reference Manual, what is the standard method to test the UART loopback or basic transmit/receive functionality?"
        },
        {
            "Level": "3 (Toolchain)", 
            "Topic": "J-Link Debugging", 
            "Question": "I am experiencing a HardFault on the Cortex-M33. Based on the J-Link Commander manual and EVK manual, which connector on the i.MX 93 EVK provides JTAG/SWD access, and what basic J-Link command can I use to halt the CPU and read a register?"
        }
    ]

    results = []
    print("\n🧪 Starting Tests...")
    print("-" * 60)

    for i, test in enumerate(test_suite, 1):
        print(f"Running Test {i}/{len(test_suite)}: [{test['Topic']}]...")
        start_time = time.time()
        
        try:
            response = rag_chain.invoke({"input": test["Question"]})
            answer = response["answer"]
            time_taken = round(time.time() - start_time, 2)
        except Exception as e:
            answer = f"Error: {e}"
            time_taken = 0.0

        results.append({
            "Test ID": i,
            "Level": test["Level"],
            "Topic": test["Topic"],
            "Question": test["Question"],
            "AI Answer": answer.strip(),
            "Time (s)": time_taken
        })
        time.sleep(1) # 暫停 1 秒避免觸發 API 頻率限制 (Pause for 1 sec to avoid API rate limits)

    # 輸出成 Pandas DataFrame (Output as Pandas DataFrame)
    import pandas as pd
    df = pd.DataFrame(results)
    
    # 儲存為 CSV 檔案 (Save to CSV)
    csv_filename = "rag_evaluation_report_v2.csv"
    df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
    
    print("\n✅ Evaluation Complete!")
    print("-" * 60)
    print(f"📁 Report saved to: {os.path.abspath(csv_filename)}")
    
    # 在終端機印出簡化的表格結果 (Print simplified table in terminal)
    print("\n📊 Summary Table:")
    print(df[["Test ID", "Topic", "Time (s)", "AI Answer"]].to_string(max_colwidth=50))
if __name__ == "__main__":
    run_evaluation()
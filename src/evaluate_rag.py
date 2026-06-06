import os
import pickle
import time
import pandas as pd
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever

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
    chroma_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

    # 2. 🌟 新增：載入 BM25 關鍵字檢索器 (Load BM25 Keyword Retriever)
    if not os.path.exists("splits.pkl"):
        raise FileNotFoundError("❌ splits.pkl not found! Run ingest_data.py first.")
    with open("splits.pkl", "rb") as f:
        splits = pickle.load(f)
    bm25_retriever = BM25Retriever.from_documents(splits)
    bm25_retriever.k = 5

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

    # 測試題庫 (Test Dataset)
    test_suite = [
        {"Level": "1 (Basic)", "Topic": "Memory Map", "Question": "What is the base address of the GPIO1 module?"},
        {"Level": "1 (Basic)", "Topic": "Registers", "Question": "In the LPUART module, what is the register offset for the Watermark Register (WATER)?"},
        {"Level": "1 (Basic)", "Topic": "Core", "Question": "Does the Cortex-M33 core support TCM (Tightly Coupled Memory)? If so, what is its primary purpose?"},
        {"Level": "2 (Cross-Para)", "Topic": "Boot", "Question": "Please list the primary boot devices supported by the i.MX 93 ROM."},
        {"Level": "2 (Cross-Para)", "Topic": "GPIO", "Question": "To configure a pad as a GPIO output, which specific register inside the IOMUXC needs to be modified, and what should be written to the GPIO Direction Register (GDIR)?"},
        {"Level": "2 (Cross-Para)", "Topic": "Power", "Question": "What are the different power modes available in the i.MX 93, and which module is primarily responsible for controlling system resets (SRC)?"},
        {"Level": "3 (Advanced)", "Topic": "Debugging", "Question": "I am trying to use LPI2C1 to communicate with a sensor, but there is no signal on the pins. As a firmware engineer, what steps should I check regarding the Clock (CCM) and Pin Mux (IOMUXC) configurations based on the manual?"},
        {"Level": "3 (Advanced)", "Topic": "Arch", "Question": "According to the reference manual, what is the main division of tasks between the Cortex-A55 and the Cortex-M33 in the i.MX 93 architecture?"}
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
            # 計算花費時間 (Calculate time taken)
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
    df = pd.DataFrame(results)
    
    # 儲存為 CSV 檔案 (Save to CSV)
    csv_filename = "rag_evaluation_report.csv"
    df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
    
    print("\n✅ Evaluation Complete!")
    print("-" * 60)
    print(f"📁 Report saved to: {os.path.abspath(csv_filename)}")
    
    # 在終端機印出簡化的表格結果 (Print simplified table in terminal)
    print("\n📊 Summary Table:")
    print(df[["Test ID", "Topic", "Time (s)", "AI Answer"]].to_string(max_colwidth=50))

if __name__ == "__main__":
    run_evaluation()
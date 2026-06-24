import os
import pickle
import time
import json
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
    return rag_chain, ensemble_retriever

def load_benchmark_dataset(json_path: str):
    """載入測試考卷 / Load the exam dataset"""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_mrr(retrieved_docs, expected_sources):
    """
    計算 MRR 指標。
    比對檢索到的文件來源 (doc.metadata['source']) 是否存在於預期來源列表中。
    
    Calculate the MRR metric.
    Compare if the retrieved document source exists in the expected sources list.
    """
    if not expected_sources:
        return 0.0
        
    for rank, doc in enumerate(retrieved_docs, start=1):
        actual_source = doc.metadata.get("source", "")
        # 只要檢索到的來源名稱部分匹配預期清單中的任何一個，即視為命中
        # As long as the retrieved source name partially matches any in the expected list, it's a hit.
        for expected in expected_sources:
            if expected in actual_source:
                return 1.0 / rank
                
    return 0.0 # Top K 內皆未命中 / No hits in Top K

def run_benchmark_evaluation():
    print("🚀 Initializing Retrieval Benchmark Evaluator...")
    try:
        rag_chain, ensemble_retriever = setup_rag_chain()
    except Exception as e:
        print(f"Initialization Error: {e}")
        return

    benchmark_path = os.path.join(os.path.dirname(__file__), "benchmark_dataset.json")
    if not os.path.exists(benchmark_path):
        print(f"❌ 找不到基準測試檔 (Benchmark file not found): {benchmark_path}")
        return

    test_suite = load_benchmark_dataset(benchmark_path)
    results = []
    
    print(f"\n🧪 開始執行 {len(test_suite)} 項基準測試... (Starting {len(test_suite)} benchmark tests...)")
    print("-" * 60)

    total_mrr = 0.0

    for test in test_suite:
        print(f"評估中 (Evaluating) [{test['bug_id']}] - {test['category']} ...")
        
        # 1. 僅觸發檢索器以計算 MRR (Trigger retriever only to calculate MRR)
        retrieved_docs = ensemble_retriever.invoke(test["query"])
        mrr_score = calculate_mrr(retrieved_docs, test["expected_sources"])
        total_mrr += mrr_score

        # 2. (選擇性) 觸發完整 RAG 鏈取得文字回答 (Optional: Trigger full RAG chain for text answer)
        # response = rag_chain.invoke({"input": test["query"]})
        # ai_answer = response["answer"]

        results.append({
            "Bug ID": test["bug_id"],
            "Category": test["category"],
            "MRR": round(mrr_score, 4),
            "Expected Sources": ", ".join(test["expected_sources"])
        })
        time.sleep(1) # 避免 API 速率限制 / Avoid API rate limits

    # 產出報告 / Generate Report
    df = pd.DataFrame(results)
    csv_filename = "retrieval_benchmark_results.csv"
    df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
    
    average_mrr = total_mrr / len(test_suite) if test_suite else 0
    
    print("\n✅ 評估完成！ (Evaluation Complete!)")
    print(f"🏆 系統平均 MRR 倒數排名分數 (System Average MRR): {average_mrr:.4f}")
    print(f"📁 詳細報告已儲存至 (Detailed report saved to): {os.path.abspath(csv_filename)}")
    print("\n📊 測試結果摘要 (Summary):")
    print(df[["Bug ID", "Category", "MRR"]].to_string(index=False))

if __name__ == "__main__":
    run_benchmark_evaluation()
import os
import pickle
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

def setup_llm():
    """載入環境變數並初始化 Gemini 模型 (Load env vars and initialize Gemini)"""
    load_dotenv()
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise ValueError("❌ Missing GEMINI_API_KEY in .env file!")
    
    print("🤖 Initializing Google Gemini Model...")
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        google_api_key=gemini_key, 
        temperature=0
    )

def start_query_engine():
    """啟動問答引擎 (Start the query engine)"""
    
    # 1. 檢查資料庫是否存在 (Check if DB exists)
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}. Please run ingest_data.py first.")
        return

    # 2. 載入已存在的向量資料庫 (Load existing vector DB)
    print("📚 Connecting to existing vector database...")
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

    # 3. 初始化模型與問答鏈 (Initialize LLM and QA Chain)
    llm = setup_llm()
    system_prompt = (
        "You are an expert embedded systems engineer assisting with the NXP i.MX93 EVB. "
        "Use the following pieces of retrieved context to answer the question. "
        "If you don't know the answer, say that you don't know based on the context. "
        "Always provide precise register addresses, offsets, or tool commands if mentioned.\n\n"
        "{context}"
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(ensemble_retriever, question_answer_chain)

    print("\n✅ Query Engine Ready! Type 'exit' or 'quit' to stop.")
    print("-" * 50)

    # 4. 互動式問答迴圈 (Interactive Query Loop)
    while True:
        question = input("\n🧑‍💻 You: ")
        if question.lower() in ['exit', 'quit']:
            print("👋 Exiting query engine...")
            break
        if not question.strip():
            continue

        print("🧠 Thinking...")
        try:
            response = rag_chain.invoke({"input": question})
            print(f"\n🤖 Gemini: \n{response['answer']}")
            
            # (Optional) 可以在這裡保留 Debug 功能來檢查來源
            # print("\n🔍 [Sources]:", [doc.metadata.get("source") for doc in response["context"]])
        except Exception as e:
            print(f"\n❌ Error during execution: {e}")

if __name__ == "__main__":
    start_query_engine()
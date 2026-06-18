import os
import pickle
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.tools import tool

# ==========================================
# 1. 載入並初始化 Retriever (提取自你的 query_rag.py)
# ==========================================
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../chroma_db'))
SPLITS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../splits.pkl'))

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# 確保資料庫存在
if os.path.exists(DB_PATH) and os.path.exists(SPLITS_PATH):
    # 載入語意檢索器
    vectorstore = Chroma(persist_directory=DB_PATH, embedding_function=embeddings)
    chroma_retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
    
    # 載入關鍵字檢索器
    with open(SPLITS_PATH, "rb") as f:
        splits = pickle.load(f)
    bm25_retriever = BM25Retriever.from_documents(splits)
    bm25_retriever.k = 10
    
    # 融合為 Ensemble Retriever
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, chroma_retriever], weights=[0.5, 0.5]
    )
else:
    print("⚠️ 找不到 ChromaDB 或 splits.pkl，請確認是否已執行 ingest_data.py")
    ensemble_retriever = None

# ==========================================
# 2. 將 Retriever 封裝成 Agent 可以使用的 Tool
# ==========================================
@tool
def query_nxp_knowledge_base(query: str) -> str:
    """
    Search the NXP i.MX93 official knowledge base, EVK manual, and Yocto guide.
    
    【搜尋技巧提示】
    - 查詢記憶體位址或暫存器時，請使用精簡的關鍵字，如："LPI2C2 base address" 或 "GPIO1 memory map"。
    - 查詢 Yocto 錯誤或系統崩潰原因時，請提取核心錯誤，如："Unable to mount root fs"。
    """
    if not ensemble_retriever:
        return "錯誤：NXP 知識庫未正確載入，無法進行查詢。"
    
    print(f"🔍 [Knowledge Expert 正在翻閱手冊]: '{query}' ...")
    
    enhanced_query = query
    if "base address" in query.lower() or "start address" in query.lower():
        enhanced_query += " (focus on memory map and system memory layout)"
        print(f"🪄 [System] 偵測到位址查詢，已自動擴充查詢詞：{enhanced_query}")
        
    # 執行檢索
    docs = ensemble_retriever.invoke(query)
    
    # 將檢索到的 Document 轉換為純文字供 LLM 閱讀
    context_list = []
    for i, doc in enumerate(docs, 1):
        source = os.path.basename(doc.metadata.get('source', 'Unknown'))
        context_list.append(f"--- Document Snippet {i} (Source: {source}) ---\n{doc.page_content}")
        
    # 如果都沒找到東西
    if not context_list:
        return "在知識庫中找不到與此查詢相關的資料，請嘗試更換關鍵字。"
        
    return "\n\n".join(context_list)
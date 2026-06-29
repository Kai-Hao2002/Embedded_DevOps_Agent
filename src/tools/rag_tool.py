# tools/rag_tool.py
import os
import pickle
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.tools import tool

# ==========================================
# 1. load and initail Retriever
# ==========================================
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../chroma_db'))
SPLITS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../splits.pkl'))

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


if os.path.exists(DB_PATH) and os.path.exists(SPLITS_PATH):
    vectorstore = Chroma(persist_directory=DB_PATH, embedding_function=embeddings)
    chroma_retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
    
    with open(SPLITS_PATH, "rb") as f:
        splits = pickle.load(f)
    bm25_retriever = BM25Retriever.from_documents(splits)
    bm25_retriever.k = 10
    
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, chroma_retriever], weights=[0.5, 0.5]
    )
else:
    print("⚠️ If ChromaDB or splits.pkl cannot be found, please check if ingest_data.py has been executed.")
    ensemble_retriever = None

# ==========================================
# 2. A tool that encapsulates Retriever into an Agent that can be used.
# ==========================================
@tool
def query_nxp_knowledge_base(query: str, target_core: str = "BOTH") -> str:
    """
    Search the NXP i.MX93 official knowledge base, EVK manual, and Yocto guide.
    Parameters:
    - query: The search string.
    - target_core: Specify "M33" for MCU/Bare-metal/Keil issues, "A55" for MPU/Linux/Yocto/DTS issues, or "BOTH" for general hardware specs.
    """
    if not ensemble_retriever:
        return "Error: The NXP knowledge base was not loaded correctly."
    
    print(f"🔍 [Knowledge Expert searching for '{query}' in core '{target_core}'...]")
    
    # 這裡我們動態調整 Chroma Retriever 的過濾條件
    # (Here we dynamically adjust the filter conditions of the Chroma Retriever)
    if target_core in ["M33", "A55"]:
        # 設定過濾器：只允許匹配的 Core 或是通用的 BOTH 文件
        # (Set filter: only allow matching Core or universal BOTH documents)
        chroma_retriever.search_kwargs["filter"] = {"target_core": {"$in": [target_core, "BOTH"]}}
    else:
        # 移除過濾器，全域搜尋 (Remove filter, global search)
        chroma_retriever.search_kwargs.pop("filter", None)

    # 執行 Ensemble 檢索 (Execute Ensemble retrieval)
    docs = ensemble_retriever.invoke(query)
    
    context_list = []
    for i, doc in enumerate(docs, 1):
        source = os.path.basename(doc.metadata.get('source', 'Unknown'))
        core_info = doc.metadata.get('target_core', 'Unknown')
        context_list.append(f"--- Document Snippet {i} (Source: {source}, Core: {core_info}) ---\n{doc.page_content}")
        
    if not context_list:
        return "No relevant information was found. Try changing keywords or target_core."
        
    return "\n\n".join(context_list)
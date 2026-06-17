import os
import shutil
import pickle
from langchain_community.document_loaders import PDFPlumberLoader, TextLoader, WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma


DOC_PATH = "./docs/processed"
DB_PATH = "./chroma_db"

# ==========================================
# 🌐 網頁資源設定區 (Web Resources)
# ==========================================
# 將你需要 AI 閱讀的網址直接貼在這裡
WEB_URLS = [
    "https://www.keil.com/support/man/docs/uv4cl/uv4cl_commandline.htm", # Keil MDK CLI
    "https://kb.segger.com/J-Link_Commander",                            # J-Link Commander
    "https://github.com/nxp-imx/mfgtools/blob/master/README.md"          # NXP UUU (Universal Update Utility)
]

def build_vector_database():
    """讀取 PDF 與網頁內容，建立/覆蓋本地向量資料庫與 BM25 索引"""
    
    # 1. 清除舊資料庫 (Clear old DB)
    if os.path.exists(DB_PATH):
        print(f"🗑️ Clearing old vector database at {DB_PATH}...")
        shutil.rmtree(DB_PATH)

    docs = []

    # 2. 讀取本地 PDF 文件 (Load Local PDFs)
    if os.path.exists(DOC_PATH):
        print("📄 Loading local documents...")
        for filename in os.listdir(DOC_PATH):
            file_path = os.path.join(DOC_PATH, filename)
            
            # 判斷如果是 PDF，就用 PDFPlumberLoader
            if filename.lower().endswith(".pdf"):
                print(f"   📖 Reading PDF: {filename}")
                loader = PDFPlumberLoader(file_path)
                docs.extend(loader.load())
                
            # 判斷如果是 Markdown 或 TXT，就用 TextLoader
            elif filename.lower().endswith(".md") or filename.lower().endswith(".txt"):
                print(f"   📝 Reading Text/Markdown: {filename}")
                loader = TextLoader(file_path, encoding='utf-8')
                docs.extend(loader.load())
                
            # 其他不認識的檔案就跳過
            else:
                print(f"   ⏩ Skipping unsupported file: {filename}")
    else:
        print(f"⚠️ Warning: Folder {DOC_PATH} not found.")

    # 3. 讀取線上網頁文件 (Load Web Documents)
    if WEB_URLS:
        print("\n🌐 Loading Web documents via WebBaseLoader...")
        try:
            # WebBaseLoader 支援直接傳入網址 List
            web_loader = WebBaseLoader(WEB_URLS)
            web_docs = web_loader.load()
            
            # 將網頁抓下來的內容與 PDF 內容合併
            docs.extend(web_docs)
            print(f"   ✅ Successfully loaded {len(WEB_URLS)} web pages.")
        except Exception as e:
            print(f"   ❌ Error loading web pages: {e}")
            print("   💡 提示：請確認是否已執行 `pip install beautifulsoup4`")

    # 檢查是否有抓到任何資料
    if not docs:
        print("\n⚠️ No documents found from either PDFs or Web. Exiting.")
        return
        
    print(f"\n✅ Total document chunks/pages loaded: {len(docs)}")

    # 4. 文本切塊 (Text Chunking)
    # 這裡的 chunking 會同時對 PDF 與 HTML 解析後的純文字生效
    print("✂️ Splitting text...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=400)
    splits = text_splitter.split_documents(docs)

    # 5. 建立與儲存資料庫 (Embedding and Storing)
    print("🧠 Creating embeddings and saving to ChromaDB...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    Chroma.from_documents(documents=splits, embedding=embeddings, persist_directory=DB_PATH)
    
    # 6. 將 splits 存成 pickle 檔案供 BM25 讀取 (Save for Ensemble Retriever)
    print("📦 Saving documents for BM25 Keyword Search...")
    with open("splits.pkl", "wb") as f:
        pickle.dump(splits, f)
        
    print("\n🎉 Vector database & BM25 index built successfully! (PDF + Web)")

if __name__ == "__main__":
    build_vector_database()
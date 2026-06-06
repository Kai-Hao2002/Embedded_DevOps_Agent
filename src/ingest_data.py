import os
import shutil
import pickle
from langchain_community.document_loaders import PDFPlumberLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

DOC_PATH = "./docs/processed"
DB_PATH = "./chroma_db"

def build_vector_database():
    """讀取 PDF 並建立/覆蓋本地向量資料庫與 BM25 索引"""
    
    # 1. 清除舊資料庫 (Clear old DB)
    if os.path.exists(DB_PATH):
        print(f"🗑️ Clearing old vector database at {DB_PATH}...")
        shutil.rmtree(DB_PATH)

    # 2. 讀取文件 (Load Documents with Plan B)
    if not os.path.exists(DOC_PATH):
        print(f"❌ Error: Please put your split PDF chapters into {DOC_PATH}")
        return

    print("📄 Loading documents with PDFPlumber (Optimized for Tables)...")
    docs = []
    
    # 逐一讀取資料夾內的 PDF (Iterate through all PDFs in the folder)
    for filename in os.listdir(DOC_PATH):
        if filename.endswith(".pdf"):
            file_path = os.path.join(DOC_PATH, filename)
            print(f"   📖 Reading: {filename}")
            loader = PDFPlumberLoader(file_path)
            # 🚨 關鍵點：必須使用 'extend' 把新文件的內容加入列表，絕不能用 '=' 覆蓋！
            # (CRITICAL: Must use 'extend' to append new contents, NEVER use '=' to overwrite!)
            docs.extend(loader.load())
            
    if not docs:
        print("⚠️ No documents found. Please add PDFs to the folder.")
        return
        
    print(f"\n✅ Total pages loaded: {len(docs)}")

    # 3. 文本切塊 (Text Chunking)
    print("✂️ Splitting text...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=400)
    splits = text_splitter.split_documents(docs)

    # 4. 建立與儲存資料庫 (Embedding and Storing)
    print("🧠 Creating embeddings and saving to ChromaDB...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    Chroma.from_documents(documents=splits, embedding=embeddings, persist_directory=DB_PATH)
    
    # 5. 將 splits 存成 pickle 檔案供 BM25 讀取 (Save for BM25)
    print("📦 Saving documents for BM25 Keyword Search...")
    with open("splits.pkl", "wb") as f:
        pickle.dump(splits, f)
        
    print("🎉 Vector database & BM25 index built successfully!")

if __name__ == "__main__":
    build_vector_database()
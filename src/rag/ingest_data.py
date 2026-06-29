# rag/ingest_data.py
import os
import shutil
import pickle
import pdfplumber
from langchain_core.documents import Document
from langchain_community.document_loaders import PDFPlumberLoader, TextLoader, WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma


DOC_PATH = "./docs/processed"
CODE_PATH = "./target_workspace"
DB_PATH = "./chroma_db"

# ==========================================
# 🌐 網頁資源設定區 (Web Resources)
# ==========================================
WEB_URLS = {
    "Keil_MDK_CLI": "https://www.keil.com/support/man/docs/uv4cl/uv4cl_commandline.htm", # Keil MDK CLI
    "J-Link_Commander": "https://kb.segger.com/J-Link_Commander",                        # J-Link Commander
    "NXP_UUU": "https://github.com/nxp-imx/mfgtools/blob/master/README.md"               # NXP UUU (Universal Update Utility)
}

def parse_pdf_with_markdown_tables(file_path):
    """
    讀取 PDF，並將提取到的表格強制轉換為 Markdown 格式附加在頁面文字後，
    以保持暫存器與記憶體位址的 2D 對應結構。
    
    Reads a PDF and forces extracted tables into Markdown format appended to the page text,
    preserving the 2D structural relationship of registers and memory addresses.
    """
    docs = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            # 提取該頁的純文字 / Extract plain text of the page
            content = page.extract_text() or ""
            
            # 提取該頁的表格 / Extract tables from the page
            tables = page.extract_tables()
            
            for table in tables:
                if not table: continue
                
                # 將整個表格內容轉為小寫字串，用來判斷表格類型
                # Convert the entire table to a lowercase string to determine its type
                table_text_lower = str(table).lower()
                
                # 智慧注入 (Smart Injection): 
                if "start address" in table_text_lower or "start" in table_text_lower and "end" in table_text_lower:
                    # 如果表格有 Start/End Address，這才是真正的記憶體映射表！
                    # If it has Start/End Address, this is the REAL Memory Map!
                    md_table = "\n\n### [CRITICAL: Memory Map, Base Address, Start Address]\n"
                elif "offset" in table_text_lower or "register" in table_text_lower:
                    # 如果只有 offset，這只是普通的暫存器表
                    # If it only has offset, it's just a regular register table
                    md_table = "\n\n### [Hardware Register Map, Offset]\n"
                else:
                    md_table = "\n\n### [Extracted Table]\n"
                
                for row_idx, row in enumerate(table):
                    clean_row = [str(cell).replace("\n", " ").strip() if cell else "" for cell in row]
                    md_table += "| " + " | ".join(clean_row) + " |\n"
                    
                    if row_idx == 0:
                        md_table += "|" + "|".join(["---" for _ in clean_row]) + "|\n"
                
                # 將 Markdown 表格附加到該頁的內容中 / Append Markdown table to the page content
                content += md_table + "\n"
            
            # 封裝為 LangChain 認識的 Document 格式 / Wrap into LangChain Document format
            docs.append(Document(
                page_content=content,
                metadata={"source": os.path.basename(file_path), "page": i + 1, "source_type": "pdf"}
            ))
    return docs

def build_vector_database():
    """讀取多種文件並根據檔案類型進行智慧切塊 (Code-Aware Chunking)"""
    
    if os.path.exists(DB_PATH):
        print(f"🗑️ Clearing old vector database at {DB_PATH}...")
        shutil.rmtree(DB_PATH)

    # 依據檔案類型分類收集
    pdf_and_text_docs = []
    c_cpp_docs = []
    dts_docs = []
    yocto_docs = []

    # 1. 讀取本地 PDF 與文件 (Load Local PDFs & Text)
    if os.path.exists(DOC_PATH):
        print("📄 Loading local documents...")
        for filename in os.listdir(DOC_PATH):
            file_path = os.path.join(DOC_PATH, filename)
            
            if filename.lower().endswith(".pdf"):
                print(f"   📖 Reading PDF: {filename}")
                pdf_and_text_docs.extend(parse_pdf_with_markdown_tables(file_path))
                
            elif filename.lower().endswith(".md") or filename.lower().endswith(".txt"):
                print(f"   📝 Reading Text/Markdown: {filename}")
                loader = TextLoader(file_path, encoding='utf-8')
                loaded_docs = loader.load()
                # 🟢 增加 Metadata
                for doc in loaded_docs: doc.metadata["source_type"] = "markdown"
                pdf_and_text_docs.extend(loaded_docs)
                

    # 2. 掃描原始碼資料夾 (Load Source Code for RAG)
    # 讓 RAG 也能搜尋 target_workspace 裡面的 C code 和 DTS
    if os.path.exists(CODE_PATH):
        print("\n💻 Scanning source code and device trees...")
        for root, _, files in os.walk(CODE_PATH):
            for filename in files:
                file_path = os.path.join(root, filename)
                core_label = "M33" if "mcu_firmware" in file_path else "A55" if "mpu_linux_bsp" in file_path else "BOTH"
                
                if filename.endswith(".c") or filename.endswith(".h"):
                    loader = TextLoader(file_path, encoding='utf-8')
                    loaded_docs = loader.load()
                    for doc in loaded_docs: 
                        doc.metadata["source_type"] = "c_code"
                        doc.metadata["target_core"] = core_label 
                    c_cpp_docs.extend(loaded_docs)
                    
                elif filename.endswith(".dts") or filename.endswith(".dtsi"):
                    loader = TextLoader(file_path, encoding='utf-8')
                    loaded_docs = loader.load()
                    for doc in loaded_docs: 
                        doc.metadata["source_type"] = "dts"
                        doc.metadata["target_core"] = core_label
                    dts_docs.extend(loaded_docs)

                elif filename.endswith(".bb") or filename.endswith(".bbappend") or filename.endswith(".conf"):
                    loader = TextLoader(file_path, encoding='utf-8')
                    loaded_docs = loader.load()
                    for doc in loaded_docs: 
                        doc.metadata["source_type"] = "yocto_recipe"
                        doc.metadata["target_core"] = core_label
                    yocto_docs.extend(loaded_docs)

    print("\n🌐 Loading Web documents via WebBaseLoader...")
    for source_name, url in WEB_URLS.items():
        try:
            web_loader = WebBaseLoader([url])
            web_docs = web_loader.load()
            for doc in web_docs: 
                # [優化] 覆寫 Metadata 的 source 為明確名稱 / [Optimization] Override Metadata source with explicit name
                doc.metadata["source"] = source_name 
                doc.metadata["source_type"] = "web"
            pdf_and_text_docs.extend(web_docs)
            print(f"   ✅ Successfully loaded: {source_name}")
        except Exception as e:
            print(f"   ❌ Error loading web page {source_name}: {e}")

    print("\n✂️ Splitting text with content-aware strategies...")
    all_splits = []

    # 策略 A：純文本與 PDF (使用標準字元切塊)
    std_splitter = RecursiveCharacterTextSplitter(chunk_size=3500, chunk_overlap=500)
    all_splits.extend(std_splitter.split_documents(pdf_and_text_docs))
    
    # 策略 B：C/C++ 原始碼 (基於 AST 語法樹的切塊，保持 Function 完整)
    if c_cpp_docs:
        print(f"   -> Splitting {len(c_cpp_docs)} C/C++ files using AST rules...")
        c_splitter = RecursiveCharacterTextSplitter.from_language(
            language=Language.C, chunk_size=1500, chunk_overlap=200
        )
        all_splits.extend(c_splitter.split_documents(c_cpp_docs))

    # 策略 C：Device Tree (DTS) (以節點結尾 '};' 為主要分隔符，保持 Node 完整)
    if dts_docs:
        print(f"   -> Splitting {len(dts_docs)} DTS files using Node rules...")
        dts_splitter = RecursiveCharacterTextSplitter(
            separators=["\n};", "{\n", "\n\n", "\n"], # 優先在 Node 結尾切斷
            chunk_size=1200, 
            chunk_overlap=150
        )
        all_splits.extend(dts_splitter.split_documents(dts_docs))
    
    # 策略 D：Yocto Recipe / [NEW] Strategy D: Yocto Recipe
    if yocto_docs:
        print(f"   -> Splitting {len(yocto_docs)} Yocto files using recipe rules...")
        yocto_splitter = RecursiveCharacterTextSplitter(
            # 優先在 Yocto 任務函式 (如 do_compile) 的邊界切割 / Prioritize cutting at Yocto task boundaries
            separators=["\ndo_", "\n}", "\n\n", "\n"], 
            chunk_size=1000,
            chunk_overlap=150
        )
        all_splits.extend(yocto_splitter.split_documents(yocto_docs))

    print(f"\n✅ Total document chunks generated: {len(all_splits)}")

    # 5. 建立與儲存資料庫 (Embedding and Storing)
    print("🧠 Creating embeddings and saving to ChromaDB...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    Chroma.from_documents(documents=all_splits, embedding=embeddings, persist_directory=DB_PATH)
    
    # 6. 將 splits 存成 pickle 檔案供 BM25 讀取 (Save for Ensemble Retriever)
    print("📦 Saving documents for BM25 Keyword Search...")
    with open("splits.pkl", "wb") as f:
        pickle.dump(all_splits, f)
        
    print("\n🎉 Hybrid Vector database & BM25 index built successfully!")

if __name__ == "__main__":
    build_vector_database()
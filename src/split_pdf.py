import os
from pypdf import PdfReader, PdfWriter

def split_pdf_by_chapters(input_pdf, output_dir, chapter_ranges):
    """
    將大型 PDF 根據指定的頁碼範圍拆分成多個小檔案。
    """
    # 檢查輸入檔案是否存在
    if not os.path.exists(input_pdf):
        print(f"❌ 找不到輸入檔案: {input_pdf}")
        print("請確保您已將 Reference Manual 放入正確的路徑。")
        return

    # 確保輸出資料夾存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"📁 建立輸出資料夾: {output_dir}")

    print(f"📖 正在讀取 {input_pdf} ... (檔案較大，請耐心等候幾秒鐘)")
    reader = PdfReader(input_pdf)
    total_pages = len(reader.pages)
    print(f"✅ 讀取完成，總頁數: {total_pages}\n")

    for chapter_name, (start_page, end_page) in chapter_ranges.items():
        # 防呆機制：將使用者看到的 1-indexed 頁碼轉換為 pypdf 的 0-indexed 索引
        start_idx = max(0, start_page - 1)
        end_idx = min(total_pages, end_page)

        writer = PdfWriter()
        # 將指定範圍的頁面加入新的 PDF 寫入器
        for i in range(start_idx, end_idx):
            writer.add_page(reader.pages[i])

        # 儲存拆分後的小檔案
        output_filename = os.path.join(output_dir, f"{chapter_name}.pdf")
        with open(output_filename, "wb") as output_pdf:
            writer.write(output_pdf)

        print(f"✂️ 成功產出: {output_filename} (第 {start_page} 到 {end_page} 頁)")

if __name__ == "__main__":
    # ==========================================
    # ⚙️ 參數設定區 (Configuration)
    # ==========================================
    
    # 1. 設定原始 5000 頁手冊的路徑與輸出資料夾
    INPUT_FILE = "./docs/imx93_reference.pdf"  # 替換成您實際下載的檔名
    OUTPUT_FOLDER = "./docs/processed"

    # 2. 定義要萃取的章節與頁碼範圍 (請填寫您在 PDF 閱讀器上看到的實際頁碼)
    # 格式: "輸出檔名": (起始頁碼, 結束頁碼)
    # 💡 建議初期只留下 Task 1 & Task 2 絕對會用到的章節
    CHAPTERS = {
        "01_Memory_Maps": (34, 90),           # Chapter 2
        "02_System_Boot": (249, 297),         # Chapter 9
        "03_Cortex_A55": (303, 305),          # Chapter 12
        "04_Cortex_M33": (306, 373),          # Chapters 13, 14
        "05_Debug_and_JTAG": (1272, 1290),    # Chapters 24, 25
        "06_IOMUX_and_Pins": (1291, 1712),    # Chapters 26, 27
        "07_GPIO": (1713, 1737),              # Chapter 28
        "08_Clock_and_Power": (1738, 1916),   # Chapters 29, 30
        "09_LPI2C": (4753, 4822),             # Chapter 60
        "10_LPUART": (4871, 4940)             # Chapter 62
    }

    print("🚀 開始執行 PDF 拆分作業...")
    split_pdf_by_chapters(INPUT_FILE, OUTPUT_FOLDER, CHAPTERS)
    print("\n🎉 所有指定章節拆分完成！請接著執行 build_rag.py 來建立純淨的知識庫。")
import os
import difflib
from langchain_core.tools import tool

@tool
def apply_patch_tool(file_path: str, search_text: str, replace_text: str) -> str:
    """
    【程式碼修復工具】當你發現編譯錯誤，需要修改 C 語言或 Device Tree 原始碼時，呼叫此工具。
    請精確提供檔案路徑、要被替換的「完整原始程式碼片段」，以及「修正後的新程式碼片段」。
    此工具會自動產生標準的 .patch 檔案並套用修改。
    """
    print(f"\n🛠️ [Patch Tool] 正在嘗試修復檔案: {file_path}")
    
    # 1. 確認檔案是否存在 (為了 Mock 測試，如果沒有這個檔案我們就建一個假的)
    if not os.path.exists(file_path):
        # 建立一個測試用的假 main.c (供本地測試使用)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("#include <stdio.h>\n\nint main() {\n    // LPI2C2_BASE is not defined here\n    return 0;\n}\n")
    
    # 2. 讀取原始檔案內容
    with open(file_path, "r", encoding="utf-8") as f:
        original_code = f.read()

    # 3. 驗證 search_text 是否真的存在於程式碼中
    if search_text not in original_code:
        return (f"❌ 修復失敗：在 {file_path} 中找不到指定的 `search_text`。\n"
                f"請確保你提供的舊程式碼片段與檔案中完全一致（包含空白與換行）。")

    # 4. 執行程式碼替換
    new_code = original_code.replace(search_text, replace_text)

    # 5. 使用 difflib 產生標準的 Unified Diff (與 Git Patch 完全相容)
    diff = difflib.unified_diff(
        original_code.splitlines(keepends=True),
        new_code.splitlines(keepends=True),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        n=3 # 上下保留 3 行 Context
    )
    patch_content = "".join(diff)

    # 6. 儲存成 .patch 檔案 (符合 Yocto/BSP 標準流程)
    patch_dir = os.path.join(os.path.dirname(__file__), "..", "..", "patches")
    os.makedirs(patch_dir, exist_ok=True)
    
    # 使用檔案名稱作為 patch 名稱的一部分
    base_name = os.path.basename(file_path).replace(".", "_")
    patch_filename = os.path.join(patch_dir, f"fix_{base_name}_auto.patch")
    
    with open(patch_filename, "w", encoding="utf-8") as f:
        f.write(patch_content)

    # 7. 真正將修改寫入原始檔案 (套用 Patch)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_code)

    return (f"✅ 成功修復！已將修改套用至 `{file_path}`。\n"
            f"📦 已自動生成 BSP 標準補丁檔案：`{patch_filename}`。\n"
            f"請立即回報主管節點，並請求 DevOps_Expert 重新進行編譯。")
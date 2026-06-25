import os
import re
import difflib
import subprocess
import time
from langchain_core.tools import tool


@tool
def read_file_tool(file_path: str) -> str:
    """
    【檔案讀取工具】在進行程式碼修復前，請務必先呼叫此工具來讀取目標檔案的完整內容！
    這能確保您了解目前的程式碼結構，並能提供精確的 search_context 給 patch_tool。
    """
    print(f"\n👀 [Read Tool] AI 正在讀取檔案內容: {file_path}")
    if not os.path.exists(file_path):
        return f"❌ 讀取失敗：找不到檔案 `{file_path}`。"
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 幫程式碼加上行號，方便 AI 閱讀與定位
        lines = content.split('\n')
        numbered_lines = [f"{i+1:03d} | {line}" for i, line in enumerate(lines)]
        return (
            "Numbered preview for navigation:\n"
            + "\n".join(numbered_lines)
            + "\n\nRaw content for apply_patch_tool search_context. Copy from this block only:\n"
            + "```text\n"
            + content
            + "\n```"
        )
    except Exception as e:
        return f"❌ 讀取檔案時發生錯誤: {e}"
    
@tool
def apply_patch_tool(file_path: str, search_context: str, replace_content: str) -> str:
    """
    【程式碼修復工具】請精確提供檔案路徑、包含前後文的「搜尋區塊 (search_context)」，以及「替換後的完整區塊 (replace_content)」。
    [Code Repair Tool] Please provide the file path, the "search_context" including the context, and the "replaced content".
    """
    print(f"\n🛠️ [Patch Tool] is attempting to repair the file: {file_path}")    

    if not os.path.exists(file_path):
        return (f"❌ Repair failed: file `{file_path}` not found on local machine.\n")
    # 2. Read the original file content
    with open(file_path, "r", encoding="utf-8") as f:
        original_code = f.read()

    # 將連續空白正規化，提高匹配率
    def normalize_space(text):
        return re.sub(r'\s+', '', text)

    # 尋找匹配區塊
    search_norm = normalize_space(search_context)
    orig_norm = normalize_space(original_code)
    
    if search_norm not in orig_norm:
        return (f"❌ 修復失敗：無法在原始檔案中找到相符的 `search_context`。\n"
                f"🚨 [系統警告] 您提供的 search_context 必須與原始碼完全一致！\n"
                f"請先使用 `read_file_tool` 確認檔案內容，再重新嘗試。")
        
    # 執行 Python 標準庫的替換
    # 若需高精度，建議讓 LLM 輸出標準 unified diff 格式並使用 patch 命令套用
    new_code = original_code.replace(search_context, replace_content)

    # DTS 語法預檢驗 (Dry-Run)
    if file_path.endswith(".dts") or file_path.endswith(".dtsi"):
        # 暫存測試檔案
        test_file = file_path + ".test"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(new_code)
        
        # 呼叫 dtc 工具檢查語法 (若環境支援)
        try:
            result = subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", "/dev/null", test_file], 
                                    capture_output=True, text=True)
            os.remove(test_file)
            if result.returncode != 0:
                return f"❌ Repair failed: The modified Device Tree contains a syntax error!\n{result.stderr}"
        except FileNotFoundError:
            os.remove(test_file)
            
    # 儲存 patch 並寫回檔案
    diff = difflib.unified_diff(
        original_code.splitlines(keepends=True),
        new_code.splitlines(keepends=True),
        fromfile=f"a/{file_path}", tofile=f"b/{file_path}", n=3 
    )
    patch_content = "".join(diff)

    patches_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "patches"))
    os.makedirs(patches_dir, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", file_path).strip("_")
    patch_path = os.path.join(patches_dir, f"{int(time.time())}_{safe_name}.patch")
    with open(patch_path, "w", encoding="utf-8") as f:
        f.write(patch_content)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_code)

    return f"✅ Repair successful! Modifications have been applied. Unified Diff saved to {patch_path}. Please request DevOps_Expert to recompile."

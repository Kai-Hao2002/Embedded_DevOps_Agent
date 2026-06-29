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
def execute_bash_command(command: str) -> str:
    """
    【終端機工具】用於執行簡單的 Linux/Mac 指令，例如尋找檔案 (find)、移動檔案 (mv)、複製 (cp) 或查看目錄 (ls)。
    當需要還原檔案、重新命名檔案或尋找專案結構時，請使用此工具。
    [Terminal Tool] Used to execute bash commands like mv, cp, ls, find, etc.
    """
    print(f"\n💻 [Bash Tool] 執行指令: {command}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return f"✅ Command executed successfully:\n{result.stdout}"
        else:
            return f"❌ Command failed (Exit Code {result.returncode}):\n{result.stderr}"
    except Exception as e:
        return f"❌ Error executing command: {e}"
    
# src/tools/patch_tool.py

@tool
def apply_patch_tool(file_path: str, start_line: int, end_line: int, replace_content: str) -> str:
    """
    【程式碼修復工具】請精確提供檔案路徑、要替換的起始行號 (start_line)、結束行號 (end_line)，以及「替換後的完整區塊 (replace_content)」。
    如果只是要插入新程式碼而不刪除任何東西，請將 start_line 設為要插入的行號，end_line 設為 start_line - 1。
    [Code Repair Tool] Please provide the file path, start_line, end_line, and the replace_content.
    """
    print(f"\n🛠️ [Patch Tool] is attempting to repair the file: {file_path} (Lines {start_line}-{end_line})")    

    if not os.path.exists(file_path):
        return (f"❌ Repair failed: file `{file_path}` not found on local machine.\n")
        
    # 讀取原始檔案並保留換行符號
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    original_code = "".join(lines)
    total_lines = len(lines)

    # 驗證行號合法性
    if start_line < 1 or start_line > total_lines + 1 or end_line < start_line - 1 or end_line > total_lines:
        return f"❌ Repair failed: Invalid line numbers. The file has {total_lines} lines. Please check your start_line and end_line."

    # 確保替換的內容最後有換行符號
    if replace_content and not replace_content.endswith('\n'):
        replace_content += '\n'

    # 進行行號替換
    new_lines = lines[:start_line-1] + [replace_content] + lines[end_line:]
    new_code = "".join(new_lines)

    # DTS 語法預檢驗 (Dry-Run)
    if file_path.endswith(".dts") or file_path.endswith(".dtsi"):
        test_file = file_path + ".test"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(new_code)
        
        try:
            result = subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", "/dev/null", test_file], 
                                    capture_output=True, text=True)
            os.remove(test_file)
            if result.returncode != 0:
                return f"❌ Repair failed: The modified Device Tree contains a syntax error!\n{result.stderr}"
        except FileNotFoundError:
            if os.path.exists(test_file):
                os.remove(test_file)
            
    # 產生 Unified Diff 並寫入檔案
    diff = difflib.unified_diff(
        original_code.splitlines(keepends=True),
        new_code.splitlines(keepends=True),
        fromfile=f"a/{file_path}", tofile=f"b/{file_path}", n=3 
    )
    patch_content = "".join(diff)

    # 如果沒有差異，代表可能替換錯誤或無須替換
    if not patch_content:
         return "⚠️ Warning: The replaced content is identical to the original code. No changes were made."

    patches_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "patches"))
    os.makedirs(patches_dir, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", file_path).strip("_")
    patch_path = os.path.join(patches_dir, f"{int(time.time())}_{safe_name}.patch")
    
    with open(patch_path, "w", encoding="utf-8") as f:
        f.write(patch_content)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_code)

    return f"✅ Repair successful! Modifications have been applied. Unified Diff saved to {patch_path}. Please request DevOps_Expert to recompile."
import os
import sys
import json
import time
import shutil
import pandas as pd
from langchain_core.messages import HumanMessage

# 動態將 src 加入路徑，以便引入 AI Agent
# Dynamically add src to path to import AI Agent
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from agent.ai_agent import mas_app

# ==========================================
# 目錄與路徑設定 (Directory and Path Configuration)
# ==========================================
EXPERIMENTS_DIR = os.path.dirname(os.path.abspath(__file__))
BUGS_DEF_PATH = os.path.join(EXPERIMENTS_DIR, "fault_injection", "bugs_def.json")
BACKUP_DIR = os.path.join(EXPERIMENTS_DIR, "fault_injection", "backup_clean_code")
RESULTS_DIR = os.path.join(EXPERIMENTS_DIR, "results")
PROJECT_ROOT = os.path.abspath(os.path.join(EXPERIMENTS_DIR, ".."))

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# ==========================================
# 核心功能函數 (Core Functions)
# ==========================================
def backup_clean_code(target_file_rel_path: str):
    """備份乾淨的原始碼 (Backup clean source code)"""
    abs_target = os.path.join(PROJECT_ROOT, target_file_rel_path)
    if not os.path.exists(abs_target):
        print(f"⚠️ 找不到目標檔案 (Target file not found): {abs_target}")
        return False
    
    backup_path = os.path.join(BACKUP_DIR, os.path.basename(target_file_rel_path))
    shutil.copy2(abs_target, backup_path)
    return True

def restore_clean_code(target_file_rel_path: str):
    """還原乾淨的原始碼 (Restore clean source code)"""
    backup_path = os.path.join(BACKUP_DIR, os.path.basename(target_file_rel_path))
    abs_target = os.path.join(PROJECT_ROOT, target_file_rel_path)
    
    if os.path.exists(backup_path):
        shutil.copy2(backup_path, abs_target)
        return True
    return False

def inject_fault(bug_def: dict):
    """根據定義注入錯誤 (Inject fault based on definition)"""
    abs_target = os.path.join(PROJECT_ROOT, bug_def["target_file"])
    action = bug_def.get("fault_action")
    
    with open(abs_target, "r", encoding="utf-8") as f:
        code = f.read()

    if action == "replace_text":
        search = bug_def.get("fault_search")
        replace = bug_def.get("target_content")
        if search in code:
            code = code.replace(search, replace)
            with open(abs_target, "w", encoding="utf-8") as f:
                f.write(code)
            print(f"🕷️ 錯誤已注入 (Fault injected): 將 {search} 替換為 {replace}")
            return True
            
    print(f"❌ 錯誤注入失敗 (Fault injection failed for) {bug_def['bug_id']}")
    return False

def check_fix_success(bug_def: dict):
    """驗證 AI 是否成功修復原始碼 (Verify if AI successfully fixed the code)"""
    abs_target = os.path.join(PROJECT_ROOT, bug_def["target_file"])
    with open(abs_target, "r", encoding="utf-8") as f:
        current_code = f.read()
    
    if bug_def.get("fault_action") == "replace_text":
        # 修復成功代表原本正確的程式碼回來了，且錯誤的程式碼消失了
        is_fixed = bug_def["fault_search"] in current_code and bug_def["target_content"] not in current_code
        return is_fixed
        
    return False

# ==========================================
# 實驗主迴圈 (Experiment Main Loop)
# ==========================================
def run_experiments(mode="PROPOSED_MAS"):
    print(f"🚀 開始執行自動化實驗管線 (Starting Automated Experiment Pipeline) - 模式 (Mode): {mode}")
    print("=" * 60)
    
    with open(BUGS_DEF_PATH, "r", encoding="utf-8") as f:
        bugs = json.load(f)

    results = []

    for bug in bugs:
        print(f"\n🧪 測試案例 (Testing Case): {bug['bug_id']} - {bug['description']}")
        
        # 1. 備份與破壞 (Backup & Inject)
        if not backup_clean_code(bug["target_file"]):
            continue
        if not inject_fault(bug):
            restore_clean_code(bug["target_file"])
            continue

        # 2. 初始化 AI 狀態 (Initialize AI State)
        initial_state = {
            "messages": [HumanMessage(content=bug["user_prompt"])],
            "mode": mode,
            "retry_count": 0
        }


        # 3. 啟動 LangGraph 代理人並計時 (Start LangGraph Agent and time it)
        start_time = time.time()
        final_node = ""
        error_occurred = False # 記錄是否發生 API 錯誤
        
        try:
            # 限制遞迴深度避免無限死結
            for output in mas_app.stream(initial_state, {"recursion_limit": 15}):
                for node_name, state_update in output.items():
                    print(f"\n🚀 [Agent Trajectory] 進入節點 (Entering Node): {node_name}")
                    final_node = node_name
                    
                    if "messages" in state_update and state_update["messages"]:
                        last_msg = state_update["messages"][-1].content
                        # 簡化印出內容，避免畫面太亂
                        print(f"💬 {node_name} Output:\n{last_msg[:200]}...\n") 
        except Exception as e:
            print(f"   ⚠️ 系統異常中斷 (System interrupted with error): {e}")
            error_occurred = True

        mttr = round(time.time() - start_time, 2)
        
        # 4. 驗證修復結果
        is_fixed = check_fix_success(bug)
        
        # 如果是因為 API 503 斷線，我們可以將狀態標記為特殊值，以便後續分析
        if error_occurred:
            pass_at_k = "API_ERROR"
            print(f"🎯 修復狀態: 失敗 (API 伺服器無回應)")
        else:
            pass_at_k = 1 if is_fixed else 0
            print(f"🎯 修復狀態: {'成功 (Success)' if is_fixed else '失敗 (Failed)'}")
        
        # 4. 驗證修復結果 (Verify Fix Results)
        is_fixed = check_fix_success(bug)
        pass_at_k = 1 if is_fixed else 0  # 簡化版 Pass@1 判定
        
        print(f"⏱️ 修復耗時 (MTTR): {mttr} 秒 (s)")
        print(f"🎯 修復狀態 (Fix Status): {'成功 (Success)' if is_fixed else '失敗 (Failed)'}")

        # 5. 記錄數據 (Record Data)
        results.append({
            "Bug ID": bug["bug_id"],
            "Category": bug["category"],
            "LLM Mode": mode,
            "Human Baseline (s)": bug["human_baseline_time_sec"],
            "AI MTTR (s)": mttr,
            "Success (Pass@k)": pass_at_k,
            "Final Node": final_node
        })

        # 6. 還原環境準備下一輪 (Restore Environment for next round)
        restore_clean_code(bug["target_file"])
        print("-" * 60)

    # 產出 CSV 報表 (Generate CSV Report)
    df = pd.DataFrame(results)
    csv_filename = os.path.join(RESULTS_DIR, f"experiment_results_{mode}.csv")
    df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
    print(f"\n📊 實驗報表已儲存至 (Experiment report saved to): {csv_filename}")

if __name__ == "__main__":
    # 可以在此處替換為 B1, B2, B3 來執行消融實驗對照組
    # You can replace this with B1, B2, B3 to run ablation study baselines
    run_experiments(mode="PROPOSED_MAS")
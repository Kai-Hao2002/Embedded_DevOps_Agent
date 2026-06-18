import sys
import random
import time

# 準備三種常見的 Keil 編譯日誌情境
LOG_SUCCESS = """Build target 'Target 1'
compiling main.c...
linking...
Program Size: Code=1024 RO-data=256 RW-data=0 ZI-data=512  
".\\Objects\\my_project.axf" - 0 Error(s), 0 Warning(s).
"""

LOG_ERROR = """Build target 'Target 1'
compiling main.c...
main.c(45): error: #20: identifier 'LPI2C2' is undefined
main.c(46): error: #65: expected a ';'
linking...
".\\Objects\\my_project.axf" - 2 Error(s), 0 Warning(s).
"""

LOG_WARNING = """Build target 'Target 1'
compiling main.c...
main.c(12): warning: #177-D: variable 'temp' was declared but never referenced
linking...
".\\Objects\\my_project.axf" - 0 Error(s), 1 Warning(s).
"""

if __name__ == "__main__":
    print("[Mock Keil] UV4.exe emulator started...")
    time.sleep(1) # 模擬編譯時間
    
    # 解析 -o 參數來決定 Log 要存在哪裡
    out_file = "build_log.txt"
    if "-o" in sys.argv:
        out_file = sys.argv[sys.argv.index("-o") + 1]

    # 這裡可以改成固定輸出 LOG_ERROR 來測試 AI 抓蟲功能
    # 預設為隨機抽取一種情境
    outcome = random.choice([LOG_SUCCESS, LOG_ERROR, LOG_WARNING])
    #outcome = LOG_ERROR

    # 寫入假 Log 檔
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(outcome)

    print(f"[Mock Keil] Build finished. Log written to {out_file}")

    # 根據 Keil 的規則回傳 Exit Code
    if "error:" in outcome.lower():
        sys.exit(2)
    elif "warning:" in outcome.lower():
        sys.exit(1)
    else:
        sys.exit(0)
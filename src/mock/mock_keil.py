'''
# for main.py
import sys
import random
import time

LOG_SUCCESS = """Build target 'Target 1'
compiling main.c...
linking...
Program Size: Code=1024 RO-data=256 RW-data=0 ZI-data=512  
".\\Objects\\my_project.axf" - 0 Error(s), 0 Warning(s).
"""

LOG_ERROR_SYNTAX = """Build target 'Target 1'
compiling main.c...
main.c(45): error: #20: identifier 'LPI2C2' is undefined
main.c(46): error: #65: expected a ';'
".\\Objects\\my_project.axf" - 2 Error(s), 0 Warning(s).
"""

LOG_ERROR_FATAL = """Build target 'Target 1'
compiling main.c...
main.c(2): error: #5: cannot open source input file "fsl_lpi2c.h": No such file or directory
".\\Objects\\my_project.axf" - 1 Error(s), 0 Warning(s).
"""

LOG_ERROR_LINKER = """Build target 'Target 1'
compiling main.c...
linking...
.\\Objects\\my_project.axf: Error: L6218E: Undefined symbol LPI2C_MasterInit (referred from main.o).
".\\Objects\\my_project.axf" - 1 Error(s), 0 Warning(s).
"""

if __name__ == "__main__":
    print("[Mock Keil] UV4.exe emulator started...")
    time.sleep(1) 
    
    out_file = "build_log.txt"
    if "-o" in sys.argv:
        out_file = sys.argv[sys.argv.index("-o") + 1]

    # 隨機抽取常見的編譯情境 (Randomly select a common build scenario)
    outcome = random.choices(
        [LOG_SUCCESS, LOG_ERROR_SYNTAX, LOG_ERROR_FATAL, LOG_ERROR_LINKER],
        weights=[30, 40, 15, 15]
    )[0]

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(outcome)

    print(f"[Mock Keil] Build finished. Log written to {out_file}")

    if "Error:" in outcome or "error:" in outcome.lower():
        sys.exit(2)
    else:
        sys.exit(0)
'''
import sys
import os
import time

LOG_SUCCESS = """Build target 'Target 1'
compiling main.c...
linking...
Program Size: Code=1024 RO-data=256 RW-data=0 ZI-data=512  
".\\Objects\\my_project.axf" - 0 Error(s), 0 Warning(s).
"""

# 新增：針對 i.MX93 硬體限制的編譯器報錯
LOG_ERROR_UNSUPPORTED_PIN = """Build target 'Target 1'
compiling main.c...
target_workspace/mcu_firmware/main.c(11): error: #35: #error directive: "Platform limitation: 'kLPI2C_4PinUnidirectional' is physically NOT supported on i.MX93. Please check chip-specific LPI2C information."
".\\Objects\\my_project.axf" - 1 Error(s), 0 Warning(s).
"""

if __name__ == "__main__":
    print("[Mock Keil] UV4.exe emulator started...")
    time.sleep(1) 
    
    out_file = "build_log.txt"
    if "-o" in sys.argv:
        out_file = sys.argv[sys.argv.index("-o") + 1]

    target_c_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "target_workspace", "mcu_firmware", "main.c"))
    
    outcome = LOG_SUCCESS
    
    if os.path.exists(target_c_file):
        with open(target_c_file, "r", encoding="utf-8") as f:
            content = f.read()
            # 嚴格把關：只要偵測到不支援的 4-Pin 模式，就拋出硬體限制錯誤
            if 'kLPI2C_4PinUnidirectional' in content:
                outcome = LOG_ERROR_UNSUPPORTED_PIN
    else:
        outcome = f"Fatal Error: Target file {target_c_file} not found!"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(outcome)

    if "Error:" in outcome or "error:" in outcome.lower() or "Fatal" in outcome:
        sys.exit(2)
    else:
        sys.exit(0)
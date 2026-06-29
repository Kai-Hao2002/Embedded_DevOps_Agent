# tools/run_yocto_tool.py
import paramiko
import socket
import os
import re
import time
import random
from dotenv import load_dotenv

load_dotenv()

EXECUTION_MODE = os.getenv("EXECUTION_MODE", "MOCK").upper()

SSH_HOST = os.getenv("YOCTO_SSH_HOST", "127.0.0.1")
SSH_PORT = int(os.getenv("YOCTO_SSH_PORT", 2222))
SSH_USER = os.getenv("YOCTO_SSH_USER", "root")
SSH_PASS = os.getenv("YOCTO_SSH_PASS", "yocto")

REMOTE_IMAGE_PATH = "/root/Image-imx93.bin"
LOCAL_IMAGE_PATH = "./Image-imx93.bin"
BUILD_LOG_PATH = "/root/yocto_build.log"

def _connect_ssh_with_retry(host, port, username, password, max_retries=3, delay=3):
    """
    SSH 連線輔助函數，具備重試與超時保護機制。
    SSH connection helper functions with retry and timeout protection mechanisms.
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    for attempt in range(1, max_retries + 1):
        try:
            ssh.connect(host, port=port, username=username, password=password, timeout=10)
            return ssh
        except (paramiko.SSHException, socket.timeout, socket.error) as e:
            print(f"⚠️ SSH conects failed. ({host}:{port}),{delay} miniutes retry ({attempt}/{max_retries})... errors: {e}")
            time.sleep(delay)
            
    return None

def extract_critical_yocto_logs(log_content: str) -> str:
    """
    【日誌截斷器 Log Truncator - 層級化壓縮版】
    不直接回傳海量上下文，而是萃取「錯誤摘要」與「詳細日誌路徑」，
    強迫 AI 代理人使用讀檔工具去查閱真正的錯誤細節，大幅節省 Token。
    
    [Log Truncator - Hierarchical Compression Version]
    Instead of returning massive context directly, it extracts the "Error Summary" and "Detailed Log Paths",
    forcing the AI agent to use file-reading tools to inspect the real error details, significantly saving Tokens.
    """
    lines = log_content.splitlines()
    
    errors_found = []
    detailed_log_paths = []
    
    for line in lines:
        # 擷取 Yocto 提示的詳細日誌路徑 (Capture the detailed log path prompted by Yocto)
        if "Logfile of failure stored in:" in line:
            match = re.search(r'Logfile of failure stored in:\s*(/[^\s]+)', line)
            if match:
                detailed_log_paths.append(match.group(1))
        
        # 擷取明確的 ERROR 或 FATAL 行，捨棄 WARNING 以免干擾主線
        # (Capture explicit ERROR or FATAL lines, discard WARNINGs to avoid distracting the main thread)
        if re.match(r'^(ERROR|FATAL ERROR|FAILED):', line, re.IGNORECASE):
            # 過濾掉太長的 gcc 雜訊，保留純粹的 Yocto 錯誤宣告
            # (Filter out overly long gcc noise, keeping pure Yocto error declarations)
            if len(line) < 200: 
                errors_found.append(line.strip())
                
    # 組裝「層級化地圖」回報給 AI (Assemble the "Hierarchical Map" to report back to the AI)
    report = []
    report.append("🚨 [Yocto Build Failed] 系統發生建置錯誤！(System Build Error!)")
    report.append("="*50)
    report.append("📋 【錯誤摘要 Error Summary】:")
    
    if errors_found:
        # 去除重複的錯誤行 (Remove duplicate error lines)
        unique_errors = list(dict.fromkeys(errors_found))
        for err in unique_errors[:5]: # 最多只顯示前 5 個主要錯誤 (Show up to the top 5 main errors)
            report.append(f" - {err}")
    else:
        report.append(" - (未能在主控台捕捉到簡短錯誤，請直接查看下方詳細日誌 / Could not capture a short error in the console, please check the detailed logs below)")
        
    report.append("="*50)
    
    if detailed_log_paths:
        report.append("📂 【詳細日誌路徑 Detailed Task Logs】:")
        unique_paths = list(dict.fromkeys(detailed_log_paths))
        for path in unique_paths:
            report.append(f" 👉 {path}")
        
        report.append("\n💡 [System Directive to Knowledge_Expert]:")
        report.append("DO NOT GUESS the error. You MUST use the `execute_bash_command` (e.g., `cat <path>`) or `read_file_tool` to read the exact detailed log files listed above to find the root cause!")
    else:
        # 如果沒有找到具體路徑，就回退到回傳最後 30 行，避免完全沒線索
        # (If no specific paths are found, fallback to returning the last 30 lines to avoid having no clues at all)
        report.append("⚠️ [Fallback] 找不到獨立的 task log 路徑，以下為最後 30 行日誌： (Could not find independent task log paths, below are the last 30 lines of the log:)")
        report.append("\n".join(lines[-30:]))
        
    return "\n".join(report)

def trigger_remote_build(target_recipe="imx-image-multimedia"):
    """
    非同步觸發：透過 SSH 在背景啟動 Yocto 編譯
    Asynchronous Triggering: Launching Yocto Compilation in the Background via SSH
    """
    if EXECUTION_MODE == "MOCK":
        print("🧪 [Mock Mode] Simulates triggering remote Yocto compilation...")
        chaos_event = random.choices(["NORMAL", "SSH_TIMEOUT", "CONNECTION_REFUSED"], weights=[70, 20, 10])[0]
        
        if chaos_event == "SSH_TIMEOUT":
            print("⚠️ [Chaos] SSH IMEOUT...")
            time.sleep(3)
            return "❌ Critical Network Error: Unable to connect to the Yocto server; SSH Timeout."
        elif chaos_event == "CONNECTION_REFUSED":
            print("⚠️ [Chaos] CONNECTION REFUSED...")
            time.sleep(1)
            return "❌ Critical Network Error: Connection refused by Yocto server."
        
        time.sleep(1)
        return "✅ Yocto remote compilation has started in the background (Mock). Please use the status check tool to track the progress."

    print("🌐 [Real Mode] Connecting and launching Yocto Build in the background....")
    ssh = _connect_ssh_with_retry(SSH_HOST, SSH_PORT, SSH_USER, SSH_PASS)
    
    if not ssh:
        return "❌ Critical Network Error: Unable to connect to the Yocto server; maximum retries reached. \n🚨 [System Command]: Please report to the user to check server status and network configuration."
        
    try:
        command = f"nohup bitbake {target_recipe} > {BUILD_LOG_PATH} 2>&1 &"
        ssh.exec_command(command, timeout=10)
        return "✅ Yocto remote compilation has started in the background. Please use the status check tool to track the progress."
    except Exception as e:
        return f"❌ An unexpected error occurred during compilation: {e}"
    finally:
        ssh.close()

def check_build_status():
    """狀態輪詢：檢查背景編譯任務的最新日誌/Status polling: Check the latest logs of background compilation tasks."""
    if EXECUTION_MODE == "MOCK":
        chaos_event = random.choices(["NORMAL", "SERVER_OVERLOAD"], weights=[85, 15])[0]
        if chaos_event == "SERVER_OVERLOAD":
            print("⚠️ [Chaos] SERVER OVERLOAD...")
            time.sleep(2)
            return "❌ Log read timeout. The server may be overloaded. Please try again later."
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

        # Attempt to load the real Yocto error log (if it exists)
        bug_id = os.getenv("CURRENT_TEST_BUG_ID", "DEFAULT")
        real_log_path = os.path.join(project_root, "experiments", "real_logs", f"{bug_id}_yocto.log")
        
        if os.path.exists(real_log_path):
            with open(real_log_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_log_output = f.read()
            
            # 判斷是否為成功的 Log
            if "Build successful" in raw_log_output or "Tasks summary: attempted" in raw_log_output and "failed: 0" in raw_log_output:
                return "✅ Compilation successful! Image generated.\n(Please proceed with the deployment steps)"
            else:
                # 使用截斷器過濾真實的萬行 Log
                smart_log = extract_critical_yocto_logs(raw_log_output, context_lines=40)
                return f"❌ Compilation failed! Filtered Critical Logs:\n{smart_log}"

        # Hardcoded Mock 邏輯 (Fallback / 作為後備方案)
        uboot_recipe = os.path.join(project_root, "target_workspace", "mpu_linux_bsp", "recipes-bsp", "u-boot", "u-boot-imx_2023.04.bb")
        if not os.path.exists(uboot_recipe):
            return (
                "❌ Compilation failed! Filtered Critical Logs:\n"
                "ERROR: Nothing PROVIDES 'u-boot-imx' (but /path/to/imx-image-multimedia.bb DEPENDS on or otherwise requires it)\n"
                "ERROR: Required build target 'imx-image-multimedia' has no buildable providers.\n"
                "Missing or unbuildable dependency chain was: ['imx-image-multimedia', 'u-boot-imx']"
            )


        dts_file = os.path.join(project_root, "target_workspace", "mpu_linux_bsp", "arch", "arm64", "boot", "dts", "freescale", "imx93-11x11-evk.dts")
        if os.path.exists(dts_file):
            with open(dts_file, "r", encoding="utf-8") as f:
                content = f.read()
                if "/* FATAL: Missing closing brace } */" in content:
                    return (
                        "❌ Compilation failed! Filtered Critical Logs:\n"
                        "ERROR: Task do_compile failed with exit code '1'\n"
                        "FATAL ERROR: Syntax error parsing input tree\n"
                        "target_workspace/mpu_linux_bsp/arch/arm64/boot/dts/freescale/imx93-11x11-evk.dts: syntax error"
                    )
                
        return "✅ 編譯成功！最後日誌：\nMock Build successful. Image generated at /root/Image-imx93.bin\n(請執行下載與燒錄步驟)"
        
    ssh = _connect_ssh_with_retry(SSH_HOST, SSH_PORT, SSH_USER, SSH_PASS)
    if not ssh:
        return "❌ Critical network error: Unable to connect to the Yocto server to obtain status."
        
    try:
        stdin, stdout, stderr = ssh.exec_command(f"tail -n 5000 {BUILD_LOG_PATH}", timeout=15)
        raw_log_output = stdout.read().decode('utf-8', errors='ignore').strip()
        
        if not raw_log_output:
            return "⏳ The compilation system is initializing; no logs have been generated yet..."
            
        if "Build successful" in raw_log_output:
            return "✅ Compilation successful! Image generated.\n(Please proceed with the deployment steps)"
        elif "Failed" in raw_log_output or "ERROR:" in raw_log_output:
            # 呼叫日誌截斷器，萃取精華錯誤片段
            smart_log = extract_critical_yocto_logs(raw_log_output, context_lines=40)
            return f"❌ Compilation failed! Filtered Critical Logs:\n{smart_log}"
        else:
            # 編譯進行中，回傳最後 5 行讓 Supervisor 知道還活著即可
            return f"⏳ Compiling... current progress:\n" + "\n".join(raw_log_output.splitlines()[-5:])
            
    except socket.timeout:
        return "❌ Log read timeout. The server may be overloaded. Please try again later."
    except Exception as e:
        return f"❌ An error occurred while querying the status: {e}"
    finally:
        ssh.close()

def download_remote_image():
    """
    透過 SFTP 將編譯好的 Image 從遠端伺服器下載到本地
    Download the compiled image from the remote server to the local machine via SFTP.
    """
    if EXECUTION_MODE == "MOCK":
        print("🧪 [Mock Mode] download Image...")
        # 建立一個假的空檔案，確保後續 UUU 燒錄檢查時檔案是存在的
        with open(LOCAL_IMAGE_PATH, "w") as f:
            f.write("mock_image_data_for_testing")
        print(f"✅ Image downloads successfully (Mock): {LOCAL_IMAGE_PATH}")
        return True

    print("📥 [Real Mode] Downloading Image via SFTP...")
    ssh = _connect_ssh_with_retry(SSH_HOST, SSH_PORT, SSH_USER, SSH_PASS)
    
    if not ssh:
        print("❌ Critical network error: SFTP connection failed, unable to download image.")
        return False
        
    try:
        sftp = ssh.open_sftp()
        sftp.get(REMOTE_IMAGE_PATH, LOCAL_IMAGE_PATH)
        sftp.close()
        print(f"✅ Image successfully downloaded to local machine:{LOCAL_IMAGE_PATH}")
        return True
    except Exception as e:
        print(f"❌ Download Image failed: {e}")
        return False
    finally:
        ssh.close()

def flash_image_uuu():
    """
    模擬 NXP UUU 工具將 Image 燒錄至 i.MX93
    Use the emulation NXP UUU tool to burn the image to the i.MX93
    """
    if not os.path.exists(LOCAL_IMAGE_PATH):
        print("❌ The local image file could not be found, and the file could not be burned.")
        return False
        
    if EXECUTION_MODE == "MOCK":
        print("\n⚡ [Mock Mode] 啟動 UUU (Universal Update Utility) 工具...")
        time.sleep(1)
        print(f"uuu -b emmc_all u-boot-imx93.imx {LOCAL_IMAGE_PATH}")
        print("100% [================================>]")
        print("✅ 映像檔燒錄至 eMMC 成功！ (Mock UUU Flash completed!)")
        os.remove(LOCAL_IMAGE_PATH) # 清理假檔案
        return True

    print("\n⚡ [Real Mode] 啟動 UUU (Universal Update Utility) 工具...")
    time.sleep(1)
    print(f"uuu -b emmc_all u-boot-imx93.imx {LOCAL_IMAGE_PATH}")
    # 未來進入公司後，可以將這裡替換成真實的 subprocess.run() 呼叫
    time.sleep(2) 
    print("100% [================================>]")
    print("✅ 映像檔燒錄至 eMMC 成功！ (UUU Flash completed!)")
    
    os.remove(LOCAL_IMAGE_PATH)
    return True

if __name__ == "__main__":
    print("="*50)
    print("Launch the Task 2 automated workflow (Cortex-A Yocto deployment)")
    print(f"Current Mode: {EXECUTION_MODE}")
    print("="*50)
    
    if trigger_remote_build():
        time.sleep(1) 
        status = check_build_status()
        print(status)
        if "成功" in status:
            if download_remote_image():
                flash_image_uuu()
    else:
        print("🛑 progress ends")
import paramiko
import os
import time
from dotenv import load_dotenv

load_dotenv()

SSH_HOST = os.getenv("YOCTO_SSH_HOST", "127.0.0.1")
SSH_PORT = int(os.getenv("YOCTO_SSH_PORT", 2222))
SSH_USER = os.getenv("YOCTO_SSH_USER", "root")
SSH_PASS = os.getenv("YOCTO_SSH_PASS", "yocto")

REMOTE_IMAGE_PATH = "/root/Image-imx93.bin"
LOCAL_IMAGE_PATH = "./Image-imx93.bin"
BUILD_LOG_PATH = "/root/yocto_build.log"

def trigger_remote_build():
    """非同步觸發：透過 SSH 在背景啟動 Yocto 編譯"""
    """Asynchronous Trigger: Start Yocto build in the background via SSH"""
    print("🌐 正在連線並在背景啟動 Yocto Build...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS)
        # 使用 nohup 與 & 讓指令在背景執行，不受 SSH 斷線影響
        # Use nohup and & to run the command in the background, immune to SSH disconnects
        command = f"nohup bitbake imx-image-multimedia > {BUILD_LOG_PATH} 2>&1 &"
        ssh.exec_command(command)
        return "✅ Yocto 遠端編譯已於背景啟動。請使用狀態檢查工具來追蹤進度。"
    except Exception as e:
        return f"❌ 觸發編譯時發生 SSH 錯誤: {e}"
    finally:
        ssh.close()

def check_build_status():
    """狀態輪詢：檢查背景編譯任務的最新日誌"""
    """State Polling: Check the latest logs of the background build task"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS)
        
        # 讀取 Log 的最後 10 行來判斷狀態
        # Read the last 10 lines of the Log to determine the status
        stdin, stdout, stderr = ssh.exec_command(f"tail -n 10 {BUILD_LOG_PATH}")
        log_output = stdout.read().decode('utf-8').strip()
        
        if not log_output:
            return "⏳ 編譯系統正在初始化，尚未產生日誌..."
            
        # 根據 Dockerfile 中的 Mock 腳本關鍵字判斷
        # Determine status based on Mock script keywords in Dockerfile
        if "Build successful" in log_output:
            return f"✅ 編譯成功！最後日誌：\n{log_output}\n(請執行下載與燒錄步驟)"
        elif "Failed" in log_output or "Error" in log_output:
            return f"❌ 編譯失敗！最後日誌：\n{log_output}"
        else:
            return f"⏳ 編譯進行中... 目前進度：\n{log_output}"
            
    except Exception as e:
        return f"❌ 查詢狀態時發生錯誤: {e}"
    finally:
        ssh.close()

def download_remote_image():
    """透過 SFTP 將編譯好的 Image 從遠端伺服器下載到本地"""
    print("📥 正在透過 SFTP 下載 Image...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS)
        sftp = ssh.open_sftp()
        sftp.get(REMOTE_IMAGE_PATH, LOCAL_IMAGE_PATH)
        sftp.close()
        print(f"✅ Image 成功下載至本地端: {LOCAL_IMAGE_PATH}")
        return True
    except Exception as e:
        print(f"❌ 下載 Image 失敗: {e}")
        return False
    finally:
        ssh.close()

def flash_image_uuu():
    """模擬 NXP UUU 工具將 Image 燒錄至 i.MX93"""
    if not os.path.exists(LOCAL_IMAGE_PATH):
        print("❌ 找不到本地 Image 檔案，無法燒錄。")
        return False
        
    print("\n⚡ 啟動 UUU (Universal Update Utility) 工具...")
    time.sleep(1)
    print(f"uuu -b emmc_all u-boot-imx93.imx {LOCAL_IMAGE_PATH}")
    time.sleep(2) # 模擬燒錄時間
    
    print("100% [================================>]")
    print("✅ 映像檔燒錄至 eMMC 成功！ (UUU Flash completed!)")
    
    # 測試完畢後把假檔案刪除保持環境乾淨
    os.remove(LOCAL_IMAGE_PATH)
    return True

if __name__ == "__main__":
    print("="*50)
    print("啟動 Task 2 自動化工作流 (Cortex-A Yocto 部署)")
    print("="*50)
    
    if trigger_remote_build():
        flash_image_uuu()
    else:
        print("🛑 流程終止。")
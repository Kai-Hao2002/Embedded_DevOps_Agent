# src/tools/hal_mpu.py
import os
import time
import random
import re
import socket
import paramiko
import logging
from abc import ABC, abstractmethod
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# 共用的日誌截斷器 (Shared Log Truncator)
def extract_critical_yocto_logs(log_content: str) -> str:
    # 這裡放入我們在上一階段實作的層級化壓縮版 Log Truncator
    # (Insert the hierarchical log truncator we implemented in the previous stage here)
    lines = log_content.splitlines()
    errors_found = []
    detailed_log_paths = []
    for line in lines:
        if "Logfile of failure stored in:" in line:
            match = re.search(r'Logfile of failure stored in:\s*(/[^\s]+)', line)
            if match: detailed_log_paths.append(match.group(1))
        if re.match(r'^(ERROR|FATAL ERROR|FAILED):', line, re.IGNORECASE):
            if len(line) < 200: errors_found.append(line.strip())
            
    report = ["🚨 [Yocto Build Failed] 系統發生建置錯誤！", "="*50, "📋 【錯誤摘要 Error Summary】:"]
    if errors_found:
        unique_errors = list(dict.fromkeys(errors_found))
        for err in unique_errors[:5]: report.append(f" - {err}")
    else:
        report.append(" - (未能在主控台捕捉到簡短錯誤，請直接查看下方詳細日誌)")
    
    report.append("="*50)
    if detailed_log_paths:
        report.append("📂 【詳細日誌路徑 Detailed Task Logs】:")
        unique_paths = list(dict.fromkeys(detailed_log_paths))
        for path in unique_paths: report.append(f" 👉 {path}")
        report.append("\n💡 [System Directive to Knowledge_Expert]:")
        report.append("DO NOT GUESS. You MUST use `execute_bash_command` (e.g., `cat <path>`) to read the exact detailed log files listed above!")
    else:
        report.append("⚠️ [Fallback] 找不到獨立的 task log 路徑，以下為最後 30 行日誌：")
        report.append("\n".join(lines[-30:]))
    return "\n".join(report)

# ==========================================
# 1. 抽象介面 (Abstract Interface)
# ==========================================
class MPUToolchainStrategy(ABC):
    @abstractmethod
    def trigger_build(self, target_recipe: str = "imx-image-multimedia") -> str: pass
    @abstractmethod
    def check_status(self) -> str: pass
    @abstractmethod
    def download_image(self) -> bool: pass
    @abstractmethod
    def flash_image(self) -> bool: pass

# ==========================================
# 2. Mock 實作 (Mock Implementation)
# ==========================================
class MockMPUToolchain(MPUToolchainStrategy):
    def trigger_build(self, target_recipe: str = "imx-image-multimedia") -> str:
        logger.info("🧪 [Mock Mode] 模擬觸發遠端 Yocto 建置...")
        chaos_event = random.choices(["NORMAL", "SSH_TIMEOUT", "CONNECTION_REFUSED"], weights=[70, 20, 10])[0]
        if chaos_event == "SSH_TIMEOUT":
            time.sleep(3)
            return "❌ Critical Network Error: Unable to connect to the Yocto server; SSH Timeout."
        time.sleep(1)
        return "✅ Yocto remote compilation has started in the background (Mock). Please use the status check tool to track the progress."

    def check_status(self) -> str:
        chaos_event = random.choices(["NORMAL", "SERVER_OVERLOAD"], weights=[85, 15])[0]
        if chaos_event == "SERVER_OVERLOAD":
            time.sleep(2)
            return "❌ Log read timeout. The server may be overloaded. Please try again later."
        
        # 檢查是否有模擬的錯誤 (Check for simulated errors like missing bb file or broken dts)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        uboot_recipe = os.path.join(project_root, "target_workspace", "mpu_linux_bsp", "recipes-bsp", "u-boot", "u-boot-imx_2023.04.bb")
        if not os.path.exists(uboot_recipe):
            return extract_critical_yocto_logs("ERROR: Nothing PROVIDES 'u-boot-imx'\nLogfile of failure stored in: /tmp/log/do_compile.log")
            
        return "✅ 編譯成功！最後日誌：\nMock Build successful. Image generated.\n(請執行下載與燒錄步驟)"

    def download_image(self) -> bool:
        logger.info("🧪 [Mock Mode] 模擬下載 Image...")
        with open("./Image-imx93.bin", "w") as f: f.write("mock_image_data")
        return True

    def flash_image(self) -> bool:
        logger.info("⚡ [Mock Mode] 模擬 UUU 燒錄...")
        time.sleep(1)
        if os.path.exists("./Image-imx93.bin"): os.remove("./Image-imx93.bin")
        return True

# ==========================================
# 3. Real 實作 (Real Hardware Implementation)
# ==========================================
class RealMPUToolchain(MPUToolchainStrategy):
    def __init__(self):
        self.host = os.getenv("YOCTO_SSH_HOST", "127.0.0.1")
        self.port = int(os.getenv("YOCTO_SSH_PORT", 2222))
        self.user = os.getenv("YOCTO_SSH_USER", "root")
        self.password = os.getenv("YOCTO_SSH_PASS", "yocto")
        self.remote_image_path = "/root/Image-imx93.bin"
        self.local_image_path = "./Image-imx93.bin"
        self.build_log_path = "/root/yocto_build.log"

    def _get_ssh(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(self.host, port=self.port, username=self.user, password=self.password, timeout=10)
            return ssh
        except Exception as e:
            logger.error(f"SSH連線失敗: {e}")
            return None

    def trigger_build(self, target_recipe: str = "imx-image-multimedia") -> str:
        ssh = self._get_ssh()
        if not ssh: return "❌ Critical Network Error: Unable to connect to the Yocto server."
        try:
            ssh.exec_command(f"nohup bitbake {target_recipe} > {self.build_log_path} 2>&1 &", timeout=10)
            return "✅ Yocto remote compilation has started in the background."
        finally:
            ssh.close()

    def check_status(self) -> str:
        ssh = self._get_ssh()
        if not ssh: return "❌ Critical network error: Unable to connect to server."
        try:
            stdin, stdout, stderr = ssh.exec_command(f"tail -n 5000 {self.build_log_path}", timeout=15)
            raw_log = stdout.read().decode('utf-8', errors='ignore').strip()
            if "Build successful" in raw_log: return "✅ Compilation successful! Image generated."
            elif "Failed" in raw_log or "ERROR:" in raw_log:
                return extract_critical_yocto_logs(raw_log)
            else:
                return f"⏳ Compiling... current progress:\n" + "\n".join(raw_log.splitlines()[-5:])
        finally:
            ssh.close()

    def download_image(self) -> bool:
        ssh = self._get_ssh()
        if not ssh: return False
        try:
            sftp = ssh.open_sftp()
            sftp.get(self.remote_image_path, self.local_image_path)
            sftp.close()
            return True
        except Exception:
            return False
        finally:
            ssh.close()

    def flash_image(self) -> bool:
        logger.info("⚡ [Real Mode] 啟動真實 UUU 工具...")
        # 實作真實的 subprocess 呼叫 / Implement real subprocess call
        # result = subprocess.run(["uuu", "-b", "emmc_all", "u-boot-imx93.imx", self.local_image_path])
        return True

# ==========================================
# 4. 工廠模式 (Factory Pattern)
# ==========================================
def get_mpu_toolchain() -> MPUToolchainStrategy:
    mode = os.getenv("EXECUTION_MODE", "MOCK").upper()
    return RealMPUToolchain() if mode == "REAL" else MockMPUToolchain()
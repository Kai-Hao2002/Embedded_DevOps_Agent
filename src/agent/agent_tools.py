# src/agent/agent_tools.py
import os
import re
import time
from langchain_core.tools import tool
from tools.run_keil_tool import build_project, flash_target
from tools.run_yocto_tool import trigger_remote_build, check_build_status, flash_image_uuu, download_remote_image
from tools.serial_monitor_tool import monitor_uart_log

def static_safety_check(platform: str) -> tuple[bool, str]:
    """
    【靜態規則檢查器 Static Rule Checker】
    在燒錄前掃描原始碼或設定檔，攔截可能導致硬體損壞的危險參數。
    【Static Rule Checker】
    Scan source code or configuration files before burning to intercept dangerous parameters that may cause hardware damage.
    """
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    if platform == "MCU":
        target_file = os.path.join(PROJECT_ROOT, "target_workspace", "mcu_firmware", "main.c")
        if not os.path.exists(target_file):
            return True, "" 
            
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()
            
        # 規則 1: 檢查 MCU 時脈是否設定過高 (例如大於 250MHz)
        clock_match = re.search(r'CLOCK_SetCoreSysClkFreq\(\s*(\d+)\s*\)', content)
        if clock_match:
            freq = int(clock_match.group(1))
            if freq > 250000000:
                return False, f"🛑 [Security Interception] MCU core frequency setting error ({freq} Hz). The upper limit of the i.MX93 M33 core is 250MHz. Continuing to program may brick the chip or make it unstable!"
                
    elif platform == "MPU":
        dts_file = os.path.join(PROJECT_ROOT, "target_workspace", "mpu_linux_bsp", "arch", "arm64", "boot", "dts", "freescale", "imx93-11x11-evk.dts")
        if not os.path.exists(dts_file):
            return True, ""
            
        with open(dts_file, "r", encoding="utf-8") as f:
            content = f.read()
            
        # 規則 2: 檢查 PMIC 核心電壓是否過高 (例如 regulator-max-microvolt 大於 1.1V)
        volt_match = re.search(r'regulator-max-microvolt\s*=\s*<\s*(\d+)\s*>;', content)
        if volt_match:
            uv = int(volt_match.group(1))
            if uv > 1100000:
                return False, f"🛑 [Security Interception] PMIC voltage setting abnormal ({uv} uV). VDD_SOC exceeds the 1.1V absolute limit, posing a risk of SoC burnout. eMMC deployment is rejected!"
                
    return True, "✅ 靜態安全掃描通過 (Static Safety Check Passed)。"

@tool
def compile_and_flash_mcu(dummy_arg: str = "") -> str:
    """
    用於編譯並燒錄 Cortex-M33 (MCU) 的 Keil 專案。
    Keil project for compiling and programming Cortex-M33 (MCU).
    """
    is_success, build_report = build_project()
    if is_success:
        is_safe, safety_msg = static_safety_check("MCU")
        if not is_safe:
            return f"❌ MCU compiles successfully, but FLASHING ABORTED due to safety violation:\n{safety_msg}\nPlease modify the code and try again."
            
        flash_target()
        return f"MCU compiles and programs sucessfully! \nlog:\n{build_report}"
    else:
        return f"MCU compiles failed. Errors:\n{build_report}"

@tool
def start_mpu_build(dummy_arg: str = "") -> str:
    """
    用於觸發遠端 Yocto 伺服器進行 Cortex-A55 (MPU) 的映像檔編譯。
    Used to trigger the compilation of the Cortex-A55 (MPU) image file on a remote Yocto server.
    """
    return trigger_remote_build()

@tool
def check_mpu_build_status(dummy_arg: str = "") -> str:
    """
    用於檢查 Yocto 編譯進度。如果回報「進行中」，請等待並重新呼叫。
    Used to check the Yocto compilation progress. If it returns "In Progress", please wait and call again.
    """
    time.sleep(2)
    return check_build_status()

@tool
def deploy_mpu_image(dummy_arg: str = "") -> str:
    """
    當 Yocto 編譯成功後，呼叫此工具下載 Image 並透過 UUU 燒錄。
    Once Yocto has compiled successfully, call this tool to download the image and flash it via UUU.
    """
    dl_success = download_remote_image()
    if not dl_success:
        return "❌ download the image failed!"
    flash_success = flash_image_uuu()
    return "✅ UUU flashes successfully!" if flash_success else "❌ UUU flashes failed!"

@tool
def monitor_device_logs(port_name: str = "") -> str:
    """
    用於監聽實體或虛擬開發板的 UART 序列埠開機日誌。
    Used to monitor the boot logs of the UART serial port on a physical or virtual development board.
    """
    selected_port = port_name or os.getenv("TARGET_SERIAL_PORT", "/dev/ttys000")
    success, report = monitor_uart_log(selected_port, duration=8)
    return report
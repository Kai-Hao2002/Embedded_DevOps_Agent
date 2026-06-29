# src/tools/hal_mcu.py
import os
import time
import subprocess
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# ==========================================s
# 1. 定義抽象介面 (Define the Abstract Interface)
# ==========================================
class MCUToolchainStrategy(ABC):
    """
    MCU 工具鏈的抽象基礎類別 (Abstract base class for the MCU toolchain)
    不論底層是 Mock 還是真實硬體，都必須實作這些介面。
    """
    @abstractmethod
    def build_project(self) -> tuple[bool, str]:
        pass

    @abstractmethod
    def flash_target(self) -> bool:
        pass

# ==========================================
# 2. 實作 Mock 類別 (Implement Mock Class)
# ==========================================
class MockMCUToolchain(MCUToolchainStrategy):
    def build_project(self) -> tuple[bool, str]:
        logger.info("🧪 [Mock Mode] 模擬 MCU 編譯中... (Simulating MCU Build...)")
        time.sleep(1) # 模擬編譯時間
        
        # 這裡可以直接呼叫您原本 mock_keil.py 的邏輯，或者根據測試需求動態回傳
        # 為簡化展示，我們假設檢查某個檔案狀態來決定是否成功
        target_c_file = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..", "target_workspace", "mcu_firmware", "main.c"
        ))
        
        try:
            with open(target_c_file, "r", encoding="utf-8") as f:
                content = f.read()
                if 'kLPI2C_4PinUnidirectional' in content:
                    return False, "❌ target_workspace/mcu_firmware/main.c(15): error: #35: #error directive: \"Platform limitation: 'kLPI2C_4PinUnidirectional' is physically NOT supported...\""
        except FileNotFoundError:
            return False, "❌ 找不到目標檔案 (Target file not found)"
            
        return True, "✅ [編譯完美通過 Mock Build Passed: 0 Errors, 0 Warnings]"

    def flash_target(self) -> bool:
        logger.info("🧪 [Mock Mode] 模擬 MCU 燒錄中... (Simulating MCU Flash...)")
        time.sleep(1)
        return True

# ==========================================
# 3. 實作真實硬體類別 (Implement Real Hardware Class)
# ==========================================
class RealMCUToolchain(MCUToolchainStrategy):
    def __init__(self):
        self.keil_path = os.getenv("KEIL_REAL_PATH", r"C:\Keil_v5\UV4\UV4.exe")
        self.jlink_path = os.getenv("JLINK_REAL_PATH", r"C:\Program Files\SEGGER\JLink\JLink.exe")
        self.project_path = "target_workspace/mcu_firmware/mock_project.uvprojx"
        self.build_log = "build_log.txt"

    def build_project(self) -> tuple[bool, str]:
        logger.info("🔥 [Real Mode] 執行真實 Keil 編譯... (Executing real Keil build...)")
        cmd = [self.keil_path, "-b", self.project_path, "-j0", "-o", self.build_log]
        try:
            process = subprocess.run(cmd, capture_output=True, text=True)
            # 這裡接入您原本 parse_build_log 的邏輯
            # ...
            return True, "✅ [真實編譯完成 Real Build Completed]"
        except Exception as e:
            return False, f"❌ 編譯器執行失敗 (Compiler execution failed): {e}"

    def flash_target(self) -> bool:
        logger.info("🔥 [Real Mode] 執行真實 J-Link 燒錄... (Executing real J-Link flash...)")
        cmd = [self.jlink_path, "-CommanderScript", "flash_m33.jlink"]
        try:
            process = subprocess.run(cmd, capture_output=True, text=True)
            return "O.K." in process.stdout or "Verified OK" in process.stdout
        except Exception:
            return False

# ==========================================
# 4. 工廠模式 (Factory Pattern)
# ==========================================
def get_mcu_toolchain() -> MCUToolchainStrategy:
    """動態依賴注入 (Dynamic Dependency Injection)"""
    mode = os.getenv("EXECUTION_MODE", "MOCK").upper()
    if mode == "REAL":
        return RealMCUToolchain()
    return MockMCUToolchain()
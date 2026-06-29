import os
import pty
import time
import sys
import random

def get_random_scenario():
    """決定這次開機要發生什麼狀況 (解除強制成功，引入混沌工程)"""
    scenarios = [
        "NORMAL",          # 完美的成功開機
        "NORMAL_PANIC",    # 傳統的 Kernel Panic
        "BAUDRATE_ERROR",  # 亂碼 (Baud rate 設錯)
        "TIMEOUT",         # 開機沒反應 (卡死)
        "HARD_FAULT"       # Cortex-M33 崩潰
    ]
    # 設定不同情境的發生機率 (可依照測試需求自由調整 weights)
    # 目前設定 NORMAL 有 40% 機率，其餘異常狀況各佔 15%
    return random.choices(scenarios, weights=[40, 15, 15, 15, 15])[0]

def start_virtual_board():
    master, slave = pty.openpty()
    slave_name = os.ttyname(slave)
    
    scenario = get_random_scenario()
    
    print("="*50)
    print("🔥 [Mock Board] i.MX93 虛擬開發板已準備就緒！")
    print(f"🔌 請將 AI Agent (pyserial) 連接到這個虛擬序列埠: {slave_name}")
    print(f"🎲 本次模擬情境 (Current Scenario): {scenario}")
    print("="*50)
    
    input("\n👉 請在第二個終端機啟動監聽腳本後，回到這裡按 [Enter] 鍵模擬開發板上電開機...")
    print("\n[開發板開機中... 持續輸出 UART Log...]")

    try:
        if scenario == "NORMAL":
            # 🟢 新增：完美的成功開機日誌 (包含 QA Expert 需要的關鍵字)
            logs = [
                "Cortex-M33 Booting...\n",
                "LPI2C2 Initialized\n",
                "MCU Booting...\n",
                "[0.000000] Booting Linux on physical CPU 0x0000000000\n",
                "[2.145321] Freeing unused kernel memory: 2048K\n",
                "System is operating normally. ✅\n"
            ]
            for line in logs:
                os.write(master, line.encode('utf-8'))
                time.sleep(0.2)

        elif scenario == "TIMEOUT":
            # 模擬硬體死機，什麼都不吐 (Simulate hardware freeze, outputting nothing)
            time.sleep(10)
            
        elif scenario == "BAUDRATE_ERROR":
            # 模擬 Baud rate 不匹配時的亂碼 (Simulate gibberish when baud rate mismatches)
            gibberish = "$%&*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
            for _ in range(20):
                random_chars = "".join(random.choices(gibberish, k=50)) + "\n"
                os.write(master, random_chars.encode('utf-8'))
                time.sleep(0.1)

        elif scenario == "HARD_FAULT":
            # 模擬 MCU M33 核心的 HardFault (Simulate HardFault on the MCU M33 core)
            logs = [
                "Cortex-M33 Booting...\n",
                "Initializing LPI2C2...\n",
                "*** HARD FAULT ***\n",
                "CFSR: 0x00000082 (PRECISERR)\n",
                "BFAR: 0x44350000 (Invalid Memory Access)\n",
                "System Halted.\n"
            ]
            for line in logs:
                os.write(master, line.encode('utf-8'))
                time.sleep(0.2)

        elif scenario == "NORMAL_PANIC":
            # 傳統的 Kernel Panic
            logs = [
                "U-Boot 2023.04-imx_v2023.04_2.1.0+g0000000000 for NXP i.MX93 EVK\n",
                "Starting kernel ...\n",
                "Linux version 6.1.22-nxp (oe-user@oe-host) (aarch64-poky-linux-gcc)\n",
                "[    3.012000] Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)\n",
                "[    3.035000] ---[ end Kernel panic - not syncing: VFS: Unable to mount root fs ]---\n"
            ]
            for line in logs:
                os.write(master, line.encode('utf-8'))
                time.sleep(0.2)
            
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n[Mock Board] 電源關閉。")

if __name__ == "__main__":
    start_virtual_board()
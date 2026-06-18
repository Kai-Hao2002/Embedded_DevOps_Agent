import serial
import time
import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_BAUDRATE = int(os.getenv("TARGET_BAUDRATE", 115200))

def monitor_uart_log(port_name: str, duration: int = 5):
    """
    連接到指定的序列埠，持續監聽指定秒數的日誌。
    如果發現 'panic', 'HardFault' 或 'Error' 等關鍵字，立刻回報。
    """
    print(f"📡 正在連接序列埠: {port_name}，準備監聽 {duration} 秒...")
    
    captured_logs = []
    error_detected = False
    
    try:
        # 使用環境變數定義的 baudrate / Use baudrate defined by env variables
        ser = serial.Serial(port_name, DEFAULT_BAUDRATE, timeout=1)
        
        end_time = time.time() + duration
        while time.time() < end_time:
            if ser.in_waiting > 0:
                # 讀取一行並解碼
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    captured_logs.append(line)
                    # 偵測危險關鍵字
                    if "panic" in line.lower() or "hardfault" in line.lower():
                        error_detected = True
                        
        ser.close()
        
    except serial.SerialException as e:
        return False, f"❌ 無法開啟序列埠 {port_name}：{e}"

    if not captured_logs:
        return True, "✅ 監聽結束，未收到任何 UART 輸出 (可能開發板尚未開機)。"

    log_summary = "\n".join(captured_logs)
    
    if error_detected:
        return False, f"❌ 警告！在 UART 日誌中偵測到系統崩潰 (Crash)：\n{log_summary}"
    else:
        return True, f"✅ 系統運作正常，擷取到的日誌如下：\n{log_summary}"

if __name__ == "__main__":
    # 這裡的 port_name 需要替換成 mock_board_uart.py 印出來的路徑
    test_port = input("請輸入虛擬序列埠路徑 (例如 /dev/ttys001): ")
    success, report = monitor_uart_log(test_port, duration=8)
    print("\n" + "="*40)
    print(report)
    print("="*40)
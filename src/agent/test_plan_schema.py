# src/agent/test_plan_schema.py
from pydantic import BaseModel, Field
from typing import List

class TestCaseSchema(BaseModel):
    """定義單一硬體測試案例的結構 / Defines the structure of a single hardware test case"""
    test_id: int = Field(description="測試案例的唯一識別碼 / Unique identifier for the test case")
    test_name: str = Field(description="測試項目的名稱 (例如: LPI2C2 初始化測試) / Name of the test item")
    target_register: str = Field(description="目標暫存器名稱與說明 (例如: LPI2C2_MCCR0) / Target register name and description")
    register_address: str = Field(description="該暫存器的絕對記憶體位址 (例如: 0x44350048) / Absolute memory address of the register")
    expected_hex_value: str = Field(description="預期的十六進位值 (例如: 0x00000048) / Expected hexadecimal value")
    test_python_script: str = Field(
        description="一段完整的 Python 腳本，使用 J-Link 或工具讀取此位址並與預期值比對 / A complete Python script that reads this address via J-Link or tools and compares it with the expected value"
    )

class TestPlanSchema(BaseModel):
    """定義完整測試計畫的結構 / Defines the structure of a complete test plan"""
    plan_title: str = Field(description="測試計畫的總體標題 / Overall title of the test plan")
    target_architecture: str = Field(description="目標硬體架構 (例如: NXP i.MX93 Cortex-M33) / Target hardware architecture")
    test_cases: List[TestCaseSchema] = Field(description="包含的所有結構化測試案例清單 / List of all structured test cases contained")
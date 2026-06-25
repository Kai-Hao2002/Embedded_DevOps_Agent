# src/agent/utils.py
import os
import base64
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic

load_dotenv()

def get_llm(provider="gemini"):
    """
    動態獲取 LLM 實例
    Dynamically obtain LLM instances
    """
    if provider == "gemini":
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            raise ValueError("❌ Missing GEMINI_API_KEY in .env file!")
        return ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=gemini_key, temperature=0)
    
    elif provider == "claude":
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_api_key:
            raise ValueError("❌ Missing ANTHROPIC_API_KEY in .env file!")
        return ChatAnthropic(model="claude-3-5-sonnet-20240620", api_key=anthropic_api_key, temperature=0)    
    
    raise ValueError(f"Unknown provider: {provider}")

def get_image_base64(image_path: str) -> str:
    """
    將本地圖片轉換為 Base64 格式供 LLM 視覺模型讀取
    Convert local images to Base64 format for LLM visual models to read.
    """
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")
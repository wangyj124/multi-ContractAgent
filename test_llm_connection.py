import os
import sys
import time
import traceback
from src.core.llm import get_llm

# Ensure we can import src
sys.path.append(os.getcwd())

def test_connection():
    model_name = "qwen3-30B-A3B-Instruct"
    print(f"[测试] 正在测试模型连接: {model_name}...", flush=True)
    
    try:
        # Use a short timeout for the test
        llm = get_llm(model_name, timeout=10)
        
        # Print actual configuration
        print(f"[配置] Model Base URL: {llm.openai_api_base}", flush=True)
        key_preview = llm.openai_api_key.get_secret_value()[:5] if hasattr(llm.openai_api_key, 'get_secret_value') else str(llm.openai_api_key)[:5]
        print(f"[配置] Model API Key: {key_preview}...", flush=True)
        
        start_time = time.time()
        print("[动作] 发送请求: 'Hello'...", flush=True)
        
        response = llm.invoke([("human", "Hello")])
        
        duration = time.time() - start_time
        print(f"[成功] 收到回复 ({duration:.2f}s):", flush=True)
        print(f"       {response.content}", flush=True)
        
    except Exception as e:
        print(f"\n[失败] 连接测试失败: {e}", flush=True)
        traceback.print_exc()

if __name__ == "__main__":
    test_connection()

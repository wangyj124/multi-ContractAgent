
import os
import sys
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from src.core.archivist import Archivist
from src.core.retriever import Retriever
from src.tools.lookup import LookupToolSet, Colors
from src.agents.nodes import worker_node
from src.core.state import FieldState
from langchain_core.messages import ToolMessage

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("TestWorkerTools")

def setup_test_environment():
    """
    Setup a clean environment with a mock document.
    """
    print(f"{Colors.CYAN}[测试] 初始化环境...{Colors.RESET}")
    
    # Initialize Retriever
    collection_name = "test_worker_tools"
    retriever = Retriever(location=":memory:", collection_name=collection_name)
    
    # Create mock chunks
    chunks = [
        {
            "content": "第一章 合同总价\n1.1 本合同总价为人民币100万元整。",
            "path": "第一章/1.1",
            "chunk_id": 0
        },
        {
            "content": "第二章 付款方式\n2.1 甲方应在合同签订后支付30%预付款。",
            "path": "第二章/2.1",
            "chunk_id": 1
        }
    ]
    
    # Index chunks
    print(f"{Colors.CYAN}[测试] 索引测试文档...{Colors.RESET}")
    retriever.index_chunks(chunks)
    
    return retriever

def test_structural_lookup(retriever: Retriever):
    """
    Test structural_lookup tool execution and logging.
    """
    print(f"\n{Colors.CYAN}=== 测试 structural_lookup ==={Colors.RESET}")
    
    lookup_tools = LookupToolSet(retriever)
    
    # Test Case 1: Existing path
    path = "第一章/1.1"
    print(f"[测试] 调用 structural_lookup(path='{path}')")
    result = lookup_tools.structural_lookup(path)
    print(f"[测试] 结果预览: {result[:50]}...")
    
    if "100万元" in result:
        print(f"{Colors.BLUE}[PASS] 成功检索到内容{Colors.RESET}")
    else:
        print(f"{Colors.RED}[FAIL] 未检索到预期内容{Colors.RESET}")

    # Test Case 2: Non-existing path
    path = "第三章/3.1"
    print(f"[测试] 调用 structural_lookup(path='{path}')")
    result = lookup_tools.structural_lookup(path)
    print(f"[测试] 结果预览: {result[:50]}...")
    
    if "未找到" in result:
        print(f"{Colors.BLUE}[PASS] 正确处理不存在的路径{Colors.RESET}")
    else:
        print(f"{Colors.RED}[FAIL] 异常的返回内容{Colors.RESET}")

def test_semantic_fallback(retriever: Retriever):
    """
    Test semantic_fallback tool execution and logging.
    """
    print(f"\n{Colors.CYAN}=== 测试 semantic_fallback ==={Colors.RESET}")
    
    lookup_tools = LookupToolSet(retriever)
    
    # Test Case: Keyword search
    query = "付款方式"
    print(f"[测试] 调用 semantic_fallback(query='{query}')")
    result = lookup_tools.semantic_fallback(query)
    print(f"[测试] 结果预览: {result[:50]}...")
    
    if "预付款" in result:
        print(f"{Colors.BLUE}[PASS] 成功检索到语义相关内容{Colors.RESET}")
    else:
        print(f"{Colors.RED}[FAIL] 未检索到预期内容{Colors.RESET}")

from src.core.llm import get_llm

def test_llm_connection():
    """
    Test basic LLM connectivity.
    """
    print(f"\n{Colors.CYAN}=== 测试 LLM 连接 ==={Colors.RESET}")
    llm = get_llm(os.environ.get("MODEL_WORKER", "qwen3-30B-A3B-Instruct"), temperature=0)
    print(f"[测试] 请求模型: {llm.model_name}")
    try:
        response = llm.invoke("你好，请回复'连接成功'。")
        print(f"[测试] 模型回复: {response.content}")
        print(f"{Colors.BLUE}[PASS] 模型连接正常{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}[FAIL] 模型连接失败: {e}{Colors.RESET}")

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.core.schema import ExtractionResult

def test_manual_json_extraction():
    """
    Test manual JSON extraction to debug structured output issues.
    """
    print(f"\n{Colors.CYAN}=== 测试手动 JSON 提取 ==={Colors.RESET}")
    llm = get_llm(os.environ.get("MODEL_WORKER", "qwen3-30B-A3B-Instruct"), temperature=0)
    
    parser = JsonOutputParser(pydantic_object=ExtractionResult)
    
    prompt = ChatPromptTemplate.from_template(
        "你是一个信息提取助手。\n"
        "请从以下文本中提取 '{task}'。\n"
        "请严格按照 JSON 格式输出，不要包含任何其他内容。\n"
        "{format_instructions}\n\n"
        "文本：\n{text}\n"
    )
    
    chain = prompt | llm | parser
    
    task = "合同总价"
    text = "[Chunk ID: 0]\n第一章 合同总价\n1.1 本合同总价为人民币100万元整。"
    
    print(f"[测试] 开始手动提取...")
    try:
        result = chain.invoke({
            "task": task, 
            "text": text,
            "format_instructions": parser.get_format_instructions()
        })
        print(f"[测试] 提取结果: {result}")
        print(f"{Colors.BLUE}[PASS] 手动 JSON 提取成功{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}[FAIL] 手动 JSON 提取失败: {e}{Colors.RESET}")

def test_worker_node(retriever: Retriever):
    """
    Test worker_node execution, model connection, and logging.
    """
    print(f"\n{Colors.CYAN}=== 测试 worker_node ==={Colors.RESET}")
    
    # Prepare state
    task = "合同总价"
    tool_output = "[Chunk ID: 0]\n第一章 合同总价\n1.1 本合同总价为人民币100万元整。"
    
    state: FieldState = {
        "field_current_task": task,
        "field_messages": [
            ToolMessage(content=tool_output, tool_call_id="mock_id", name="structural_lookup")
        ],
        "extraction_results": {},
        "navigation_history": [],
        "document_structure": "",
        "field_next_step": "worker"
    }
    
    print(f"[测试] 调用 worker_node，任务: {task}")
    try:
        result_state = worker_node(state)
        
        extraction = result_state.get("extraction_results", {}).get(task, {})
        value = extraction.get("value")
        
        print(f"[测试] 提取值: {value}")
        
        if value and "100" in str(value):
            print(f"{Colors.BLUE}[PASS] Worker 提取成功{Colors.RESET}")
        else:
            print(f"{Colors.RED}[FAIL] Worker 提取失败或值不匹配{Colors.RESET}")
            
    except Exception as e:
        print(f"{Colors.RED}[FAIL] Worker 执行出错: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()

def main():
    load_dotenv()
    try:
        retriever = setup_test_environment()
        test_structural_lookup(retriever)
        test_semantic_fallback(retriever)
        test_llm_connection()
        # test_manual_json_extraction()
        test_worker_node(retriever)
    except KeyboardInterrupt:
        print("\n[测试] 用户中断")
    except Exception as e:
        print(f"\n[测试] 发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

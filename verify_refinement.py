import os
import sys
import time
from src.core.archivist import Archivist

# Ensure stdout is flushed
sys.stdout.reconfigure(line_buffering=True)

def verify_document_processing():
    # Use the specific file mentioned by the user
    file_path = "data/input/甘露机岛合同-20181211版最终-签字版（无价格版）.docx"
    
    # Check if file exists, if not, try finding it or use a fallback
    if not os.path.exists(file_path):
        print(f"[警告] 文件不存在: {file_path}", flush=True)
        # Try to find any docx in data/input
        input_dir = "data/input"
        if os.path.exists(input_dir):
            files = [f for f in os.listdir(input_dir) if f.endswith(".docx")]
            if files:
                file_path = os.path.join(input_dir, files[0])
                print(f"[提示] 使用替代文件: {file_path}", flush=True)
            else:
                print("[错误] data/input 目录下没有 .docx 文件", flush=True)
                return
        else:
            print(f"[错误] 目录不存在: {input_dir}", flush=True)
            return

    archivist = Archivist()
    
    print("="*50, flush=True)
    print("开始验证文档处理逻辑", flush=True)
    print("="*50, flush=True)
    
    try:
        start_time = time.time()
        chunks = archivist.extract_chunks(file_path)
        end_time = time.time()
        print(f"\n[完成] 提取完成，耗时: {end_time - start_time:.2f}s", flush=True)
        
        print("\n" + "="*50, flush=True)
        print("生成文档结构树", flush=True)
        print("="*50, flush=True)
        
        tree = archivist.generate_document_structure(chunks)
        print(tree, flush=True)
        
        print("\n" + "="*50, flush=True)
        print("验证检查点", flush=True)
        print("="*50, flush=True)
        
        # 1. Check max depth
        lines = tree.split('\n')
        max_indent = 0
        for line in lines:
            indent = (len(line) - len(line.lstrip())) // 2
            if indent > max_indent:
                max_indent = indent
        
        print(f"最大缩进层级: {max_indent} (预期最大为 2, 即 Level 3)", flush=True)
        if max_indent > 2:
            print("[失败] 存在 Level 4+ 节点", flush=True)
        else:
            print("[通过] 层级限制验证", flush=True)

        # 2. Check short titles
        long_titles = [line.split('(')[0].strip().replace('- ', '') for line in lines if len(line.split('(')[0].strip().replace('- ', '')) > 20]
        if long_titles:
            print(f"[警告] 发现较长标题 (可能未精简): {long_titles[:3]}...", flush=True)
        else:
            print("[通过] 标题长度验证 (未发现超长标题)", flush=True)
            
        # 3. Check summaries
        summaries = [line for line in lines if "(摘要:" in line]
        if summaries:
            print(f"[通过] 摘要已生成 (共 {len(summaries)} 条)", flush=True)
        else:
            print("[警告] 未发现摘要", flush=True)

    except Exception as e:
        print(f"[错误] 处理过程中发生异常: {e}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Ensure we can import src
    sys.path.append(os.getcwd())
    verify_document_processing()

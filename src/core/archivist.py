import os
import re
import time
import httpx
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from docx import Document
from docx.document import Document as _Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

from src.core.llm import get_llm
from pathlib import Path

def _load_prompt(prompt_name: str) -> str:
    base_path = Path(__file__).parent.parent / "prompts"
    prompt_path = base_path / f"{prompt_name}.txt"
    if not prompt_path.exists():
         raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

HIERARCHY_PATTERNS = [
    (r"^\s*(合同封面|合同协议书|目录|此页为合同签字页)$", 1),  # Level 1: Special Pages
    (r"^\s*(第[一二三四五六七八九十\d]+[卷册])", 1),  # Level 1: Volume
    
    (r"^\s*(第[一二三四五六七八九十\d]+章)", 2),  # Level 2: Chapter
    (r"^\s*(Chapter\s+\d+)", 2),  # Level 2: Chapter (English)
    (r"^\s*(定义|合同标的|价格|支付与支付条件|交货和运输)$", 2),  # Level 2: Specific Chapter Titles

    # Level 4+ (Explicitly ignore/merge) - Checked BEFORE Level 3 to avoid partial matches
    (r"^\s*\d+\.\d+\.\d+", -1),  # e.g. 2.1.1
    (r"^\s*\d+[（(][A-Z][）)]\.\d+", -1),  # e.g. 10(A).1
    
    # Level 3
    (r"^\s*\d+\.\s", 3),          # "1. "
    (r"^\s*\d+\.\d+(?!\.)", 3),   # "2.1" (negative lookahead ensures no .1)
    (r"^\s*\d+[（(][A-Z][）)](?!\.)", 3), # "10(A)" (negative lookahead ensures no .1)
    (r"^\s*(第\d+[（(][A-Z][）)]条)(?!\.)", 3),  # "第10(A)条"
    (r"^\s*([商务技术]*附件\s*\d+)", 3),  # Attachment
]

class Archivist:
    def __init__(self, embedding_model_name: str = "qwen3-embedding-8B"):
        self.embedding_model_name = embedding_model_name
        # Placeholder for embedding model
        self.embedding_model = self._mock_embedding_model
    
    def _mock_embedding_model(self, text: str):
        # Placeholder embedding generation
        return [0.0] * 1024

    def _int_to_chinese(self, n: int) -> str:
        """
        Convert integer to Chinese numeral (simple implementation for 1-99).
        """
        chars = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
        
        if n < 10:
            return chars[n]
        elif n < 20:
            return "十" + (chars[n % 10] if n % 10 != 0 else "")
        elif n == 20:
             return "二十"
        elif n < 100:
            digit = n // 10
            unit = n % 10
            return chars[digit] + "十" + (chars[unit] if unit != 0 else "")
        else:
            return str(n) # Fallback

    def extract_chunks(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load a .docx file and extract chunks with metadata.
        """
        print(f"[开始处理] 文件路径: {file_path}", flush=True)
        start_time = time.time()
        
        doc = Document(file_path)
        chunks = []
        
        # Initial hierarchy is "Contract Cover" (Level 1)
        current_hierarchy = ["合同封面"]
        current_text_buffer = []
        
        # State for aggregating Level 3 summaries
        active_level_3_index = None
        active_level_3_text = []
        
        # Chapter numbering counter (Level 2)
        self.chapter_counter = 0

        def finalize_level_3():
            nonlocal active_level_3_index, active_level_3_text
            if active_level_3_index is not None and active_level_3_index < len(chunks):
                full_text = "\n".join(active_level_3_text)
                if not full_text.strip():
                    return
                
                chunk = chunks[active_level_3_index]
                title = chunk['metadata']['path'].split('/')[-1]
                
                print(f"[数据聚合] 条款 {title} 包含子条款字数: {len(full_text)}", flush=True)
                
                # Update chunk content to include full aggregated text
                chunk['content'] = full_text
                # Summary will be generated in batch processing later
            
            # Reset
            active_level_3_index = None
            active_level_3_text = []

        # Iterate over all elements in the document body
        for element in doc.element.body:
            if isinstance(element, CT_P):
                paragraph = Paragraph(element, doc)
                text = paragraph.text.strip()
                if not text:
                    continue
                
                # Check for hierarchy changes
                style_name = paragraph.style.name if paragraph.style else None
                
                # Check for numbering property in pPr
                pPr = element.pPr
                has_num = False
                if pPr is not None and getattr(pPr, "numPr", None) is not None:
                    has_num = True
                
                new_hierarchy = self._detect_hierarchy(text, current_hierarchy, style_name, has_num)
                
                if new_hierarchy != current_hierarchy:
                    # Check if we entered a new Level 2 Chapter
                    # Logic: if new_hierarchy has length 2 and the last element is the current text
                    if len(new_hierarchy) == 2 and new_hierarchy[-1] == text:
                        # Ensure we don't double count if we revisit same header (unlikely in sequential read)
                        # Also check if it already has "第X章"
                        if not re.match(r"^\s*第[一二三四五六七八九十\d]+章", text) and not re.match(r"^\s*Chapter", text, re.IGNORECASE):
                             self.chapter_counter += 1
                             chapter_num = self._int_to_chinese(self.chapter_counter)
                             # Update text and hierarchy
                             new_title = f"第{chapter_num}章 {text}"
                             new_hierarchy[-1] = new_title
                             text = new_title # Update text for buffer
                             print(f"[自动编号] 添加章节号: {new_title}", flush=True)

                    # Flush the current buffer as a chunk
                    if current_text_buffer:
                        # Add chunks and get the index of the first added chunk
                        added_indices = self._add_text_chunks(chunks, current_text_buffer, current_hierarchy)
                        
                        # Accumulate text if we are in Level 3
                        text_content = "\n".join(current_text_buffer)
                        if len(current_hierarchy) == 3:
                            # If we were in a Level 3 block, append text
                            active_level_3_text.append(text_content)
                            # If this was the start of the Level 3 block (or we missed the start), set index
                            if active_level_3_index is None and added_indices:
                                active_level_3_index = added_indices[0]
                        
                        current_text_buffer = []
                    
                    # If we are transitioning to a NEW Level 1, 2, or 3, we finalize the previous Level 3
                    if len(new_hierarchy) <= 3:
                        finalize_level_3()
                        
                        # Handle long titles for Level 3
                        # We defer this to batch processing
                        if len(new_hierarchy) == 3 and len(text) > 10:
                            # Just set the text as is for now, will process later
                            new_hierarchy[-1] = text

                    # Start new buffer
                    # Only start a new buffer if it's Level 3 or deeper content.
                    # Level 1 and 2 headers are purely structural and should NOT generate a text chunk themselves unless they have body content.
                    # But wait, if we just set current_text_buffer = [text], this text will be flushed as a chunk next time hierarchy changes or buffer fills.
                    # If the text is just a header like "第一章 定义", we don't want to summarize it as a standalone chunk.
                    
                    if len(new_hierarchy) < 3:
                        # For Level 1 & 2, we don't start a text buffer with the header itself.
                        # We just update the hierarchy.
                        # The header text is already in the hierarchy path.
                        current_text_buffer = []
                    else:
                        # For Level 3, the header text IS the start of the content (e.g. "2.1 本合同标的...").
                        current_text_buffer = [text]
                    
                    current_hierarchy = new_hierarchy
                else:
                    # It's normal text, add to buffer
                    current_text_buffer.append(text)
                    # Also append to Level 3 accumulator if active
                    # But wait, if hierarchy hasn't changed, we are still in the same block.
                    # We will accumulate when we FLUSH.
            
            elif isinstance(element, CT_Tbl):
                # Flush text buffer before processing table
                if current_text_buffer:
                    added_indices = self._add_text_chunks(chunks, current_text_buffer, current_hierarchy)
                    # Accumulate for Level 3
                    text_content = "\n".join(current_text_buffer)
                    if len(current_hierarchy) == 3:
                        active_level_3_text.append(text_content)
                        if active_level_3_index is None and added_indices:
                            active_level_3_index = added_indices[0]
                    
                    current_text_buffer = []
                
                table = Table(element, doc)
                table_content = self._extract_table_content(table)
                title = current_hierarchy[-1] if current_hierarchy else "Table"
                
                chunks.append({
                    "content": table_content,
                    "metadata": {
                        "path": "/".join(filter(None, current_hierarchy)),
                        "type": "table",
                        "summary": self._generate_smart_summary(table_content, title)
                    }
                })
                
                # Append table content to Level 3 accumulator as well
                if len(current_hierarchy) == 3:
                    active_level_3_text.append(table_content)
        
        # Flush remaining text buffer
        if current_text_buffer:
            added_indices = self._add_text_chunks(chunks, current_text_buffer, current_hierarchy)
            text_content = "\n".join(current_text_buffer)
            if len(current_hierarchy) == 3:
                active_level_3_text.append(text_content)
                if active_level_3_index is None and added_indices:
                    active_level_3_index = added_indices[0]
            
        finalize_level_3()
        
        # Batch processing for summaries and short titles
        print("[处理进度] 开始批量生成摘要和精简标题...", flush=True)
        self._batch_process_chunks(chunks)
        
        end_time = time.time()
        print(f"[统计信息] 总块数: {len(chunks)}, 耗时: {end_time - start_time:.2f}秒", flush=True)
        return chunks

    def _batch_process_chunks(self, chunks: List[Dict[str, Any]]):
        """
        Process summaries and short titles in parallel.
        """
        tasks = []
        
        # 1. Summary Tasks
        for i, chunk in enumerate(chunks):
            content = chunk.get("content", "")
            path = chunk.get("metadata", {}).get("path", "")
            title = path.split("/")[-1]
            
            # Summary Check
            if not chunk.get("metadata", {}).get("summary"):
                is_special = any(k in title for k in ["合同封面", "合同协议书", "签字页"])
                if len(content) > 50 or is_special:
                    tasks.append(("summary", i, content, title))
                else:
                    chunk["metadata"]["summary"] = content
            
            # Short Title Check (Level 3 titles > 10 chars)
            # We check the last part of the path
            # Note: We need to update the path in metadata AND potentially all subsequent chunks that share this path?
            # Actually, Archivist logic assigns paths sequentially. 
            # If we update the path here, it only affects this chunk.
            # But the path is used for structure generation.
            # So we should update it.
            # However, multiple chunks might share the same path (if chunked by size).
            # We need to find unique paths that need shortening.
            
        # We handle short titles separately to avoid complexity with shared paths
        # Collect unique long Level 3 titles
        long_titles = {} # path -> index list
        for i, chunk in enumerate(chunks):
            path = chunk.get("metadata", {}).get("path", "")
            parts = path.split("/")
            if len(parts) >= 3: # Level 3 or deeper
                level3_title = parts[2] # 0=Vol, 1=Chap, 2=Clause
                if len(level3_title) > 10 and "Short" not in level3_title: # Avoid re-processing if already short
                     if level3_title not in long_titles:
                         long_titles[level3_title] = []
                     long_titles[level3_title].append(i)
        
        for title, indices in long_titles.items():
            tasks.append(("short_title", indices, title, None))

        if not tasks:
            return

        print(f"[并行处理] 待处理任务数: {len(tasks)} (并发数: 5)", flush=True)
        
        max_workers = int(os.environ.get("MAX_CONCURRENT_REQUESTS", 5))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {}
            
            for task in tasks:
                task_type = task[0]
                if task_type == "summary":
                    _, index, content, title = task
                    future = executor.submit(self._generate_smart_summary, content, title)
                    future_to_task[future] = task
                elif task_type == "short_title":
                    _, indices, text, _ = task
                    future = executor.submit(self._generate_short_title, text)
                    future_to_task[future] = task
            
            for future in tqdm(as_completed(future_to_task), total=len(tasks), desc="AI 处理中", unit="task"):
                task = future_to_task[future]
                task_type = task[0]
                
                try:
                    result = future.result()
                    
                    if task_type == "summary":
                        _, index, _, _ = task
                        chunks[index]["metadata"]["summary"] = result
                        
                    elif task_type == "short_title":
                        _, indices, old_title, _ = task
                        new_title = result
                        # Update all chunks with this title in their path
                        for idx in indices:
                            path = chunks[idx]["metadata"]["path"]
                            # Replace the specific part of the path
                            # Be careful with replace, ensure we target the right segment
                            # We know it's Level 3 (index 2)
                            parts = path.split("/")
                            if len(parts) > 2 and parts[2] == old_title:
                                parts[2] = new_title
                                chunks[idx]["metadata"]["path"] = "/".join(parts)
                                
                except Exception as e:
                    print(f"[错误] 任务 {task_type} 失败: {e}", flush=True)
                    if task_type == "summary":
                        _, index, content, _ = task
                        chunks[index]["metadata"]["summary"] = content[:50] + "..."

    def _detect_hierarchy(self, text: str, current_hierarchy: List[str], style_name: Optional[str] = None, has_num: bool = False) -> List[str]:
        """
        Detect if the text is a header and update the hierarchy.
        Returns the new hierarchy list.
        """
        # Priority 1: Regex
        for pattern, depth in HIERARCHY_PATTERNS:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                if depth == -1:
                    # Level 4+ -> treated as body text, so return current hierarchy
                    # This ensures it gets appended to the current Level 3 block
                    print(f"[提取层级] Level 4+ 视为正文: {text[:30]}...", flush=True)
                    return current_hierarchy
                
                print(f"[提取层级] 检测到标题(Regex): {text[:30]}... -> 映射深度: {depth}", flush=True)
                
                # Ensure hierarchy is long enough (fill gaps with empty strings)
                new_hierarchy = current_hierarchy[:]
                while len(new_hierarchy) < depth - 1:
                    new_hierarchy.append("")
                
                # Truncate and append
                new_hierarchy = new_hierarchy[:depth-1]
                new_hierarchy.append(text)
                return new_hierarchy

        # Priority 2: Style Name (Heading X)
        if style_name:
            depth = None
            if style_name.startswith("Heading 2") or style_name.startswith("标题 2"):
                depth = 2
            elif style_name.startswith("Heading 3") or style_name.startswith("标题 3"):
                depth = 3
            
            if depth:
                print(f"[提取层级] 检测到标题(Style): {text[:30]}... -> 映射深度: {depth}", flush=True)
                new_hierarchy = current_hierarchy[:]
                while len(new_hierarchy) < depth - 1:
                    new_hierarchy.append("")
                new_hierarchy = new_hierarchy[:depth-1]
                new_hierarchy.append(text)
                return new_hierarchy

        # Priority 3: Word Numbering (Special case for definitions)
        if has_num and len(current_hierarchy) >= 2 and "定义" in current_hierarchy[1]:
            depth = 3
            print(f"[提取层级] 检测到标题(自动编号): {text[:30]}... -> 映射深度: {depth}", flush=True)
            new_hierarchy = current_hierarchy[:]
            while len(new_hierarchy) < depth - 1:
                new_hierarchy.append("")
            new_hierarchy = new_hierarchy[:depth-1]
            new_hierarchy.append(text)
            return new_hierarchy

        return current_hierarchy

    def _add_text_chunks(self, chunks: List[Dict[str, Any]], text_buffer: List[str], hierarchy: List[str]) -> List[int]:
        """
        Chunk the text buffer and add to chunks list.
        Returns the indices of the added chunks.
        """
        full_text = "\n".join(text_buffer)
        if not full_text.strip():
            return []
        
        CHUNK_SIZE = 4000
        OVERLAP = 2000
        
        path_str = "/".join(filter(None, hierarchy))
        
        # Determine title for summary context (last part of hierarchy)
        title = hierarchy[-1] if hierarchy else "Unknown"
        
        start_index = len(chunks)
        added_indices = []
        
        if len(full_text) <= CHUNK_SIZE:
            chunks.append({
                "content": full_text,
                "metadata": {
                    "path": path_str,
                    "type": "text",
                    # Summary will be generated later
                    "summary": ""
                }
            })
            added_indices.append(start_index)
        else:
            # Sliding window
            start = 0
            while start < len(full_text):
                end = start + CHUNK_SIZE
                chunk_text = full_text[start:end]
                chunks.append({
                    "content": chunk_text,
                    "metadata": {
                        "path": path_str,
                        "type": "text",
                        "summary": ""
                    }
                })
                added_indices.append(len(chunks) - 1)
                if end >= len(full_text):
                    break
                start += (CHUNK_SIZE - OVERLAP)
        
        return added_indices

    def _generate_short_title(self, text: str) -> str:
        """
        Generate a short title using LLM.
        """
        summary_model = os.environ.get("MODEL_SUMMARY", "qwen3-30B-A3B-Instruct")
        print(f"[模型调用] 正在为 '{text[:20]}...' 生成精简标题... (Model: {summary_model})", flush=True)
        
        try:
            llm = get_llm(summary_model, temperature=0) 
            
            # Use short_title prompt from file
            prompt_template = _load_prompt("short_title")
            prompt = prompt_template.format(text=text)
            
            print(f"[DEBUG] Requesting Model: {summary_model}", flush=True)
            print(f"[DEBUG] Prompt Length: {len(prompt)} chars", flush=True)
            print(f"[DEBUG] Prompt Preview: {prompt[:100].replace(chr(10), ' ')}...", flush=True)
            
            start_ts = time.time()
            messages = [("human", prompt)]
            response = llm.invoke(messages)
            content = response.content.strip()
            
            duration = time.time() - start_ts
            print(f"[模型调用] 精简标题完成，耗时: {duration:.2f}s", flush=True)
            return content
        except Exception as e:
            # We don't have start_ts if exception happens before assignment? 
            # Actually start_ts is assigned inside try block now.
            # Let's fix that.
            print(f"[错误] 生成精简标题失败: {e}", flush=True)
            return text

    def _generate_smart_summary(self, text: str, title: str) -> str:
        """
        Intelligently generate a summary for the chunk.
        - If text is short (<50 chars), return text itself.
        - If text is long, use LLM to summarize with dynamic length.
        """
        text = text.strip()
        if not text:
            return ""
            
        # Check for special pages that ALWAYS need summary
        is_special_page = any(k in title for k in ["合同封面", "合同协议书", "签字页"])
        
        # Threshold check: < 50 chars
        if len(text) < 50 and not is_special_page:
            return text
            
        summary_model = os.environ.get("MODEL_SUMMARY", "qwen3-30B-A3B-Instruct")
        
        # Determine target length
        text_len = len(text)
        if text_len < 500:
            target_len = 50
        elif text_len < 1000:
            target_len = 100
        else:
            target_len = 200
            
        # print(f"[模型调用] 正在为 '{title}' 生成摘要 (长度: {text_len} -> 目标: {target_len})...", flush=True)
        
        # LLM Summary
        try:
            llm = get_llm(summary_model, temperature=0, timeout=120) 
            
            prompt_template = _load_prompt("summary")
            # Ensure text is not too long for prompt context
            # Pass length parameter to template
            prompt = prompt_template.format(title=title, text=text[:3000], length=target_len)
            
            # Debug logs removed for cleaner parallel output
            # print(f"[DEBUG] Prompt Length: {len(prompt)} chars", flush=True)
            
            messages = [
                ("human", prompt)
            ]
            response = llm.invoke(messages)
            content = response.content.strip()
            
            # Post-processing: Remove title repetition if model ignored instructions
            if content.startswith(title):
                content = content[len(title):].strip()
                # Remove potential separator characters like ": " or " - "
                if content.startswith(":") or content.startswith("-"):
                    content = content[1:].strip()
            
            # Remove "摘要：" prefix if present
            if content.startswith("摘要：") or content.startswith("摘要:"):
                content = content[3:].strip()
                
            return content
        except httpx.ReadTimeout:
            print(f"[错误] 生成摘要超时 (Timeout 120s) - Text Length: {len(text)}", flush=True)
            return text[:target_len] + "..." 
        except Exception as e:
            print(f"[错误] 生成摘要失败: {e}", flush=True)
            # Fallback to truncated text if LLM fails
            return text[:target_len] + "..."

    def _generate_summary(self, text: str) -> str:
        """
        Deprecated. Use _generate_smart_summary instead.
        """
        return self._generate_smart_summary(text, "Unknown")

    def generate_document_structure(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Generate a readable tree structure from the paths in the chunks.
        Format: Title (Summary)
        """
        structure = []
        node_count = 0
        
        def find_child(nodes, name):
            for node in nodes:
                if node['name'] == name:
                    return node
            return None

        for chunk in chunks:
            path = chunk.get('metadata', {}).get('path', [])
            summary = chunk.get('metadata', {}).get('summary', "")
            
            if not path:
                continue
            
            # If path is a string, split it
            if isinstance(path, str):
                path = path.split('/')
                
            current_level = structure
            for i, part in enumerate(path):
                node = find_child(current_level, part)
                if not node:
                    node = {'name': part, 'children': [], 'summary': ""}
                    current_level.append(node)
                    node_count += 1
                
                # If this is the leaf node (corresponding to the chunk), add summary
                if i == len(path) - 1 and summary:
                     # Always update summary if available, to catch aggregated summaries
                     node['summary'] = summary

                current_level = node['children']
        
        # Convert to string
        lines = []
        def build_string(nodes, indent=0):
            if indent > 2: # Limit visual depth to Level 3 (0, 1, 2)
                return

            for node in nodes:
                prefix = "  " * indent + "- "
                line = prefix + node['name']
                
                # Show summary
                if node.get('summary'):
                    # Full summary without truncation
                    line += f" (摘要: {node['summary']})"
                
                lines.append(line)
                build_string(node['children'], indent + 1)
        
        build_string(structure)
        
        print(f"[统计信息] 文档树生成完毕，总节点数: {node_count}", flush=True)
        return "\n".join(lines)

    def _extract_table_content(self, table: Table) -> str:
        """
        Convert table to string representation (e.g. CSV or Markdown-like).
        """
        rows = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            rows.append(" | ".join(cells))
        return "\n".join(rows)

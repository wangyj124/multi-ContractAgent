import re
from typing import List, Dict, Any, Optional
from docx import Document
from docx.document import Document as _Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

class Archivist:
    def __init__(self, embedding_model_name: str = "qwen3-embedding-8B"):
        self.embedding_model_name = embedding_model_name
        # Placeholder for embedding model
        self.embedding_model = self._mock_embedding_model
    
    def _mock_embedding_model(self, text: str):
        # Placeholder embedding generation
        return [0.0] * 1024

    def extract_chunks(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load a .docx file and extract chunks with metadata.
        """
        doc = Document(file_path)
        chunks = []
        current_hierarchy = []
        current_text_buffer = []
        
        # Iterate over all elements in the document body
        for element in doc.element.body:
            if isinstance(element, CT_P):
                paragraph = Paragraph(element, doc)
                text = paragraph.text.strip()
                if not text:
                    continue
                
                # Check for hierarchy changes
                new_hierarchy = self._detect_hierarchy(text, current_hierarchy)
                
                if new_hierarchy != current_hierarchy:
                    # If hierarchy changed, flush the current buffer as a chunk
                    if current_text_buffer:
                        self._add_text_chunks(chunks, current_text_buffer, current_hierarchy)
                        current_text_buffer = []
                    current_hierarchy = new_hierarchy
                    # If the paragraph itself was a header, we don't add it to the body text usually,
                    # but it depends on preference. Let's include it in the hierarchy path but not the body?
                    # Or maybe the header is just metadata. 
                    # Let's assume the header text is part of the path, not the content chunk.
                else:
                    # It's normal text, add to buffer
                    current_text_buffer.append(text)
            
            elif isinstance(element, CT_Tbl):
                # Flush text buffer before processing table
                if current_text_buffer:
                    self._add_text_chunks(chunks, current_text_buffer, current_hierarchy)
                    current_text_buffer = []
                
                table = Table(element, doc)
                table_content = self._extract_table_content(table)
                chunks.append({
                    "content": table_content,
                    "metadata": {
                        "path": list(current_hierarchy),
                        "type": "table",
                        "summary": "Placeholder summary for table"
                    }
                })
        
        # Flush remaining text buffer
        if current_text_buffer:
            self._add_text_chunks(chunks, current_text_buffer, current_hierarchy)
            
        return chunks

    def _detect_hierarchy(self, text: str, current_hierarchy: List[str]) -> List[str]:
        """
        Detect if the text is a header and update the hierarchy.
        Returns the new hierarchy list.
        """
        # Regex for Chapter X
        chapter_match = re.match(r'^(Chapter\s+\d+|第\d+章)', text, re.IGNORECASE)
        if chapter_match:
            return [text]
        
        # Regex for 1.1, 1.1.1
        section_match = re.match(r'^(\d+(\.\d+)+)', text)
        if section_match:
            # Determine level based on dots
            level_str = section_match.group(1)
            level_depth = level_str.count('.') + 1
            
            # Determine depth:
            # 1.1 -> 1 dot -> depth 2 (child of Chapter)
            # 1.1.1 -> 2 dots -> depth 3
            depth = level_str.count('.') + 1
            
            new_hierarchy = list(current_hierarchy)
            
            # Adjust hierarchy
            if len(new_hierarchy) >= depth:
                new_hierarchy = new_hierarchy[:depth-1]
            
            new_hierarchy.append(text)
            return new_hierarchy

        return current_hierarchy

    def _add_text_chunks(self, chunks: List[Dict[str, Any]], text_buffer: List[str], hierarchy: List[str]):
        """
        Chunk the text buffer and add to chunks list.
        """
        full_text = "\n".join(text_buffer)
        
        # Simple token count estimation (e.g. 1 word = 1.3 tokens or just char count for now)
        # Prompt says "500 token overlap". Let's assume 1 token ~ 4 chars for English, 
        # but for Chinese/General it's complex.
        # Let's use a simple character limit for "chunking" as a proxy if we don't have a tokenizer.
        # 500 tokens ~ 2000 chars?
        # Let's assume a chunk size of 1000 tokens (~4000 chars) with 500 token (~2000 chars) overlap.
        
        CHUNK_SIZE = 4000
        OVERLAP = 2000
        
        if len(full_text) <= CHUNK_SIZE:
            chunks.append({
                "content": full_text,
                "metadata": {
                    "path": list(hierarchy),
                    "type": "text",
                    "summary": "Placeholder summary"
                }
            })
        else:
            # Sliding window
            start = 0
            while start < len(full_text):
                end = start + CHUNK_SIZE
                chunk_text = full_text[start:end]
                chunks.append({
                    "content": chunk_text,
                    "metadata": {
                        "path": list(hierarchy),
                        "type": "text",
                        "summary": "Placeholder summary"
                    }
                })
                if end >= len(full_text):
                    break
                start += (CHUNK_SIZE - OVERLAP)

    def _extract_table_content(self, table: Table) -> str:
        """
        Convert table to string representation (e.g. CSV or Markdown-like).
        """
        rows = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            rows.append(" | ".join(cells))
        return "\n".join(rows)

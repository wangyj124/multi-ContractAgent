import re
from typing import List, Dict, Any, Optional
from docx import Document
from docx.document import Document as _Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

from src.core.llm import get_llm

HIERARCHY_PATTERNS = [
    (r"^(第[一二三四五六七八九十\d]+[卷册篇])", 1),  # Volume
    (r"^(此页为合同签字页)$", 1),  # Special Page
    (r"^(第[一二三四五六七八九十\d]+章)", 2),  # Chapter
    (r"^([商务技术]*附件\s*\d+)", 3),  # Attachment
    (r"^(\d+\.\d+\.\d+)(?!\.\d)", 4),  # Clause (X.X.X)
    (r"^(\d+\.\d+)(?!\.\d)", 3),  # Section (X.X)
    (r"^(第\d+[（(][A-Z][）)]条)", 3),  # Special Clause
    (r"^(\d+(\.\d+)+)", -1),  # Dynamic fallback
]

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
                        # Flush current buffer with OLD hierarchy
                        self._add_text_chunks(chunks, current_text_buffer, current_hierarchy)
                        current_text_buffer = []
                    
                    # Start new buffer with the header text! (Header Alignment)
                    current_text_buffer = [text]
                    current_hierarchy = new_hierarchy
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
                        "path": "/".join(filter(None, current_hierarchy)),
                        "type": "table",
                        "summary": self._generate_summary(table_content)
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
        for pattern, depth in HIERARCHY_PATTERNS:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                if depth == -1:
                    # Dynamic depth based on dots
                    # 1.1 -> 1 dot -> depth 2
                    level_str = match.group(1)
                    depth = level_str.count('.') + 1
                
                # Ensure hierarchy is long enough (fill gaps with empty strings)
                new_hierarchy = current_hierarchy[:]
                while len(new_hierarchy) < depth - 1:
                    new_hierarchy.append("")
                
                # Truncate and append
                new_hierarchy = new_hierarchy[:depth-1]
                new_hierarchy.append(text)
                return new_hierarchy

        return current_hierarchy

    def _add_text_chunks(self, chunks: List[Dict[str, Any]], text_buffer: List[str], hierarchy: List[str]):
        """
        Chunk the text buffer and add to chunks list.
        """
        full_text = "\n".join(text_buffer)
        
        CHUNK_SIZE = 4000
        OVERLAP = 2000
        
        path_str = "/".join(filter(None, hierarchy))
        
        if len(full_text) <= CHUNK_SIZE:
            chunks.append({
                "content": full_text,
                "metadata": {
                    "path": path_str,
                    "type": "text",
                    "summary": self._generate_summary(full_text)
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
                        "path": path_str,
                        "type": "text",
                        "summary": self._generate_summary(chunk_text)
                    }
                })
                if end >= len(full_text):
                    break
                start += (CHUNK_SIZE - OVERLAP)

    def _generate_summary(self, text: str) -> str:
        """
        Generate a summary of the text using LLM.
        """
        try:
            llm = get_llm("gpt-4o-mini") # Using a lightweight model for summary
            messages = [
                ("system", "You are a helpful assistant that summarizes legal document chunks."),
                ("human", f"Summarize the following text concisely within 50 words:\n\n{text[:2000]}")
            ]
            response = llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"Error generating summary: {str(e)}"

    def generate_document_structure(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Generate a readable tree structure from the paths in the chunks.
        """
        structure = []
        
        def find_child(nodes, name):
            for node in nodes:
                if node['name'] == name:
                    return node
            return None

        for chunk in chunks:
            path = chunk.get('metadata', {}).get('path', [])
            if not path:
                continue
            
            # If path is a string, split it
            if isinstance(path, str):
                path = path.split('/')
                
            current_level = structure
            for part in path:
                node = find_child(current_level, part)
                if not node:
                    node = {'name': part, 'children': []}
                    current_level.append(node)
                current_level = node['children']
        
        # Convert to string
        lines = []
        def build_string(nodes, indent=0):
            for node in nodes:
                lines.append("  " * indent + node['name'])
                build_string(node['children'], indent + 1)
        
        build_string(structure)
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

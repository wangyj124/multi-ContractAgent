import os
import sys
import logging
from dotenv import load_dotenv

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Load .env
load_dotenv()

# Setup minimal logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("DocStructDebug")

from src.core.archivist import Archivist

def debug_document_structure():
    docx_path = os.path.join(project_root, "data/input/甘露机岛合同-20181211版最终-签字版（无价格版）.docx")
    
    if not os.path.exists(docx_path):
        logger.error(f"File not found: {docx_path}")
        return

    logger.info(f"Loading document: {docx_path}")
    
    # Mock LLM methods to speed up structure verification
    original_generate_short_title = Archivist._generate_short_title
    original_generate_smart_summary = Archivist._generate_smart_summary
    
    def mock_short_title(self, text):
        return f"[SHORT] {text[:10]}"
        
    def mock_smart_summary(self, text, title):
        return f"[SUMMARY] {text[:20]}..."

    Archivist._generate_short_title = mock_short_title
    Archivist._generate_smart_summary = mock_smart_summary
    
    archivist = Archivist()
    
    # 1. Extract chunks
    logger.info("Extracting chunks (LLM Mocked)...")
    chunks = archivist.extract_chunks(docx_path)
    logger.info(f"Extracted {len(chunks)} chunks.")
    
    # Restore original methods
    Archivist._generate_short_title = original_generate_short_title
    Archivist._generate_smart_summary = original_generate_smart_summary
    
    # 2. Generate structure
    logger.info("Generating structure tree...")
    structure = archivist.generate_document_structure(chunks)
    
    print("\n" + "="*40 + " DOCUMENT STRUCTURE " + "="*40)
    print(structure)
    print("="*100 + "\n")
    
    # 3. Verification Checks
    logger.info("Running verification checks...")
    
    # Check 1: Chapter presence
    if "第四章" in structure:
        logger.info("✅ Chapter 4 found.")
    else:
        logger.warning("❌ Chapter 4 NOT found in structure.")

    # Check 2: Depth limit (no X.X.X)
    # We look for lines with 3 levels of indentation (usually "      - ") and pattern like "4.1.1"
    lines = structure.split('\n')
    deep_nodes = [l for l in lines if l.strip().startswith("- ") and l.count(".") >= 2 and any(char.isdigit() for char in l)]
    
    # Filter only lines that look like "4.1.1" (ignoring summaries that might contain dots)
    import re
    deep_node_pattern = re.compile(r"^\s*-\s*\d+\.\d+\.\d+")
    found_deep_nodes = [l for l in lines if deep_node_pattern.match(l)]
    
    if not found_deep_nodes:
        logger.info("✅ No nodes deeper than X.X found.")
    else:
        logger.warning(f"❌ Found {len(found_deep_nodes)} nodes deeper than X.X:")
        for n in found_deep_nodes[:3]:
            logger.warning(f"   {n}")

    # Check 3: Summary length
    long_summaries = []
    for chunk in chunks:
        summary = chunk.get("metadata", {}).get("summary", "")
        if len(summary) > 200: # 100 words approx 150-200 chars? Prompt said 100 words. Let's say 300 chars max.
             long_summaries.append(summary[:50] + "...")
    
    if not long_summaries:
        logger.info("✅ All summaries are within reasonable length.")
    else:
        logger.warning(f"❌ Found {len(long_summaries)} long summaries.")

if __name__ == "__main__":
    debug_document_structure()

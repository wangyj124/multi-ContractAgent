
import os
import sys
from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.text.paragraph import Paragraph

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
docx_path = os.path.join(project_root, "data/input/甘露机岛合同-20181211版最终-签字版（无价格版）.docx")

doc = Document(docx_path)

print("--- INSPECTING NUMBERING XML (AGAIN) ---")
for element in doc.element.body:
    if isinstance(element, CT_P):
        paragraph = Paragraph(element, doc)
        text = paragraph.text.strip()
        
        if text in ["定义", "合同标的", "价格"]:
            print(f"\nText: '{text}'")
            # Check for numPr in the paragraph properties
            pPr = element.pPr
            if pPr is not None:
                numPr = getattr(pPr, 'numPr', None)
                if numPr is not None:
                    print("  [HAS NUMBERING] Found <w:numPr>")
                    print(f"  XML snippet: {numPr.xml}")
                else:
                    print("  [NO NUMBERING] No <w:numPr> found")
            else:
                 print("  [NO NUMBERING] No pPr found")

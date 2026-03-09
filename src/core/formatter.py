import csv
from typing import Dict, List, Any, Optional
from src.core.schema import ExtractionResult

class CSVExporter:
    """
    Exporter for extraction results to CSV format.
    """
    
    @staticmethod
    def export(results: Dict[str, ExtractionResult], tasks: List[Dict], output_path: str):
        """
        Exports extraction results to a CSV file.
        
        Args:
            results: Dictionary of extraction results keyed by field name (e.g., 'field_0').
            tasks: List of tasks (from XTParser) containing metadata like index and focus.
            output_path: Path to save the CSV file.
        """
        # Define headers
        headers = ["序号", "关注点", "内容", "合同描述", "备注"]
        
        rows = []
        for i, task in enumerate(tasks):
            # Determine the key for this task in the results
            # Assuming SchemaGenerator logic: field_{i}
            key = f"field_{i}"
            
            result = results.get(key)
            
            # Default values
            index = task.get("index", "")
            focus = task.get("focus", "")
            content = ""
            contract_desc = ""
            remarks = task.get("description", "")
            
            if result:
                # Handle both object and dict
                if isinstance(result, dict):
                    val = result.get("value")
                    clause = result.get("clause_no")
                    evidence = result.get("evidence") or result.get("source_snippet")
                    validation_notes = result.get("validation_notes")
                else:
                    val = getattr(result, "value", None)
                    clause = getattr(result, "clause_no", None)
                    evidence = getattr(result, "evidence", None) or getattr(result, "source_snippet", None)
                    validation_notes = getattr(result, "validation_notes", None)

                # Content
                if val is not None:
                    content = str(val)
                
                # Contract Description: {clause_no}: {evidence}
                parts = []
                if clause:
                    parts.append(str(clause))
                if evidence:
                    parts.append(str(evidence))
                
                if len(parts) == 2:
                    contract_desc = f"{parts[0]}: {parts[1]}"
                elif len(parts) == 1:
                    contract_desc = parts[0]
                
                # Remarks: Merge original remarks + validation notes
                if validation_notes:
                    if remarks:
                        remarks = f"{remarks}; {validation_notes}"
                    else:
                        remarks = validation_notes
            
            rows.append([index, focus, content, contract_desc, remarks])
        
        # Write to CSV
        # Use utf-8-sig for Excel compatibility
        try:
            with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
        except Exception as e:
            raise IOError(f"Failed to write to {output_path}: {e}")

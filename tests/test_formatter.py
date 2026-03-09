import pytest
import os
import csv
from src.core.formatter import CSVExporter
from src.core.schema import ExtractionResult

def test_csv_exporter():
    # Setup dummy data
    tasks = [
        {"index": 1, "focus": "Field 1", "description": "Desc 1"},
        {"index": 2, "focus": "Field 2", "description": "Desc 2"},
    ]
    
    # Use ExtractionResult objects
    results = {
        "field_0": ExtractionResult(
            field_name="Field 1",
            value="Value 1",
            clause_no="1.1",
            evidence="Evidence 1",
            validation_notes="Note 1"
        ),
        "field_1": ExtractionResult(
            field_name="Field 2",
            value="Value 2",
            # Missing clause/evidence/notes to test defaults
            clause_no=None,
            evidence=None,
            validation_notes=None
        )
    }
    
    output_path = "test_output.csv"
    
    # Run export
    CSVExporter.export(results, tasks, output_path)
    
    # Verify file exists
    assert os.path.exists(output_path)
    
    # Verify content
    with open(output_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)
        
        # Header
        assert rows[0] == ["序号", "关注点", "内容", "合同描述", "备注"]
        
        # Row 1
        assert rows[1][0] == "1"
        assert rows[1][1] == "Field 1"
        assert rows[1][2] == "Value 1"
        assert rows[1][3] == "1.1: Evidence 1"
        assert "Desc 1" in rows[1][4]
        assert "Note 1" in rows[1][4]
        
        # Row 2
        assert rows[2][0] == "2"
        assert rows[2][1] == "Field 2"
        assert rows[2][2] == "Value 2"
        assert rows[2][3] == "" # No clause/evidence
        assert rows[2][4] == "Desc 2" # Original desc only

    # Cleanup
    if os.path.exists(output_path):
        os.remove(output_path)

def test_csv_exporter_dict_input():
    # Test with dict input (like from workflow state dump)
    tasks = [
        {"index": 1, "focus": "Field 1", "description": "Desc 1"},
    ]
    
    results = {
        "field_0": {
            "value": "Value Dict",
            "clause_no": "2.2",
            "evidence": "Evidence Dict",
            "validation_notes": "Note Dict"
        }
    }
    
    output_path = "test_output_dict.csv"
    CSVExporter.export(results, tasks, output_path)
    
    with open(output_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)
        assert rows[1][2] == "Value Dict"
        assert rows[1][3] == "2.2: Evidence Dict"
        assert "Note Dict" in rows[1][4]

    if os.path.exists(output_path):
        os.remove(output_path)

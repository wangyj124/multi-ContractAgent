
import pytest
import os
from src.core.task_init import XTParser, SchemaGenerator, ExtractionResult
from pydantic import BaseModel

# Assuming data/input/XT.xlsx is already created by previous step
EXCEL_PATH = "data/input/XT.xlsx"

def test_xt_parser_load_tasks():
    assert os.path.exists(EXCEL_PATH), "Excel file not found. Please create it first."
    
    parser = XTParser(EXCEL_PATH)
    tasks = parser.load_tasks()
    
    assert isinstance(tasks, list)
    assert len(tasks) > 0
    
    first_task = tasks[0]
    assert "index" in first_task
    assert "focus" in first_task
    assert "description" in first_task
    
    # Verify specific content based on dummy data
    # Row 1: 1, 合同金额, , , 提取合同的总金额，注意区分含税/不含税
    assert first_task["focus"] == "合同金额"
    assert "提取合同的总金额" in first_task["description"]

def test_schema_generator_generate_model():
    tasks = [
        {"index": 1, "focus": "合同金额", "description": "Total amount"},
        {"index": 2, "focus": "签署日期", "description": "Sign date"}
    ]
    
    Model = SchemaGenerator.generate_model(tasks)
    
    assert issubclass(Model, BaseModel)
    assert Model.__name__ == "ContractInterpretation"
    
    # Check fields
    fields = Model.model_fields
    assert "field_0" in fields
    assert "field_1" in fields
    
    # Check metadata
    assert fields["field_0"].title == "合同金额"
    assert fields["field_0"].description == "Total amount"
    
    # Test instantiation
    data = {
        "field_0": {"field_name": "合同金额", "value": "1000", "evidence": "page 1", "clause_no": "1.1"},
        "field_1": {"field_name": "签署日期", "value": "2023-01-01", "evidence": "page 2", "clause_no": "2.2"}
    }
    
    instance = Model(**data)
    assert instance.field_0.value == "1000"
    assert instance.field_1.value == "2023-01-01"
    
    # Test partial instantiation (fields are Optional)
    instance_partial = Model(field_0={"field_name": "合同金额", "value": "500"})
    assert instance_partial.field_0.value == "500"
    assert instance_partial.field_1 is None

def test_integration():
    parser = XTParser(EXCEL_PATH)
    tasks = parser.load_tasks()
    Model = SchemaGenerator.generate_model(tasks)
    
    assert len(Model.model_fields) == len(tasks)
    
    # Print schema for manual verification (visible in pytest -s)
    print(Model.model_json_schema())

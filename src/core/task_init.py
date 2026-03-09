from typing import List, Dict, Any, Type, Optional
import pandas as pd
from pydantic import BaseModel, Field, create_model
from src.core.schema import ExtractionResult

class XTParser:
    """Parses the Excel file containing extraction tasks."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load_tasks(self) -> List[Dict[str, Any]]:
        """Loads tasks from the Excel file."""
        try:
            df = pd.read_excel(self.file_path)
            # Ensure required columns exist
            required_columns = ["序号", "关注点", "备注"]
            for col in required_columns:
                if col not in df.columns:
                    raise ValueError(f"Missing required column: {col}")

            tasks = []
            for _, row in df.iterrows():
                # Handle NaN values
                description = row.get("备注")
                if pd.isna(description):
                    description = ""
                
                focus = row.get("关注点")
                if pd.isna(focus):
                    continue

                task = {
                    "index": row.get("序号"),
                    "focus": str(focus).strip(),
                    "description": str(description).strip()
                }
                tasks.append(task)
            return tasks
        except Exception as e:
            raise RuntimeError(f"Failed to load tasks from {self.file_path}: {e}")

class SchemaGenerator:
    """Generates Pydantic models dynamically based on tasks."""

    @staticmethod
    def generate_model(tasks: List[Dict[str, Any]]) -> Type[BaseModel]:
        """
        Dynamically create a Pydantic model `ContractInterpretation`.
        Each task becomes a field in the model.
        """
        fields = {}
        for i, task in enumerate(tasks):
            # Use a generic field name to avoid identifier issues
            # The semantic meaning is carried by title and description
            field_name = f"field_{i}"
            
            title = task.get("focus", f"Field {i}")
            description = task.get("description", "")
            
            # Define the field: type, default value, and metadata
            fields[field_name] = (
                Optional[ExtractionResult],
                Field(
                    default=None,
                    title=title,
                    description=description
                )
            )
        
        # Create the model
        model = create_model("ContractInterpretation", **fields)
        return model

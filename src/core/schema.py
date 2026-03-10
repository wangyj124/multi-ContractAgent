from typing import Optional, List, Any
from pydantic import BaseModel, Field

class ExtractionResult(BaseModel):
    """
    Result of an extraction task.
    """
    field_name: str = Field(description="The name of the field being extracted")
    value: Optional[Any] = Field(description="The extracted value")
    confidence: float = Field(description="Confidence score between 0 and 1", default=1.0)
    source_chunk_id: Optional[int] = Field(description="The ID of the chunk where the value was found", default=None)
    validation_notes: Optional[str] = Field(description="Notes from the validation process", default=None)
    source_snippet: Optional[str] = Field(description="The source text snippet where the value was found", default=None)
    evidence: Optional[str] = Field(description="The quote or evidence from the document", default=None)
    clause_no: Optional[str] = Field(description="The clause number where the value was found", default=None)
    page_number: Optional[int] = Field(description="Page number where the value was found", default=None)
    navigation_history: Optional[List[str]] = Field(description="History of navigation steps taken to find the value", default=None)
    error: Optional[str] = Field(description="Error message if extraction failed", default=None)
    failure_reason: Optional[str] = Field(description="Reason for validation failure", default=None)

class SupervisorDecision(BaseModel):
    """
    Decision made by the supervisor agent.
    """
    next_step: str = Field(description="Next step to take: 'finish' or a task name")
    tool_call: Optional[str] = Field(description="Name of the tool to call if any", default=None)
    tool_args: Optional[dict] = Field(description="Arguments for the tool call", default=None)

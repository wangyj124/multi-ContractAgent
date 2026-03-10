
import unittest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage
from src.agents.nodes import validator_node
from src.core.state import AgentState

class TestValidatorFeedback(unittest.TestCase):
    
    @patch("src.agents.nodes._retriever")
    def test_validator_date_mismatch_feedback(self, mock_retriever):
        # Setup mock retriever to avoid errors
        mock_retriever.get_context.return_value = "Mock context"
        
        # Setup initial state
        # We simulate a state where "Sign Date" is already extracted
        # And "Effective Date" has just been extracted by worker (but is invalid)
        state = {
            "current_task": "Effective Date",
            "extraction_results": {
                "Sign Date": {
                    "value": "2023-01-01",
                    "source_chunk_id": "chunk_1"
                },
                "Effective Date": {
                    "value": "2022-01-01", # Before Sign Date -> Error
                    "source_chunk_id": "chunk_2"
                }
            },
            "messages": []
        }
        
        # Run validator node
        result = validator_node(state)
        
        # Verify next step
        self.assertEqual(result["next_step"], "supervisor")
        
        # Verify messages
        self.assertIn("messages", result)
        messages = result["messages"]
        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], HumanMessage)
        self.assertIn("Validation Failed", messages[0].content)
        self.assertIn("Effective Date (2022-01-01) is before Sign Date (2023-01-01)", messages[0].content)
        
        # Verify extraction_results
        # "Effective Date" should be removed to force retry
        self.assertNotIn("Effective Date", result["extraction_results"])
        # "Sign Date" should remain
        self.assertIn("Sign Date", result["extraction_results"])
        
    @patch("src.agents.nodes._retriever")
    def test_validator_success(self, mock_retriever):
        # Setup mock
        mock_retriever.get_context.return_value = "Mock context"
        
        # Setup state with valid dates
        state = {
            "current_task": "Effective Date",
            "extraction_results": {
                "Sign Date": {
                    "value": "2023-01-01",
                    "source_chunk_id": "chunk_1"
                },
                "Effective Date": {
                    "value": "2023-02-01", # After Sign Date -> OK
                    "source_chunk_id": "chunk_2"
                }
            },
            "messages": []
        }
        
        # Run validator node
        result = validator_node(state)
        
        # Verify next step
        self.assertEqual(result["next_step"], "supervisor")
        
        # Verify messages (should be empty or not present)
        if "messages" in result:
            self.assertEqual(len(result["messages"]), 0)
            
        # Verify extraction_results
        # "Effective Date" should remain
        self.assertIn("Effective Date", result["extraction_results"])
        self.assertEqual(result["extraction_results"]["Effective Date"]["value"], "2023-02-01")

if __name__ == "__main__":
    unittest.main()

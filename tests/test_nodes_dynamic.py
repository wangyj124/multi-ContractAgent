import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.nodes import supervisor_node
from src.core.state import AgentState

class TestNodesDynamic(unittest.TestCase):
    
    @patch("src.agents.nodes.get_llm")
    def test_supervisor_node_dynamic_tasks(self, mock_get_llm):
        # Setup mock LLM
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_llm_with_tools = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        
        # Setup mock chain response
        mock_response = MagicMock()
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response
        
        # We need to mock the pipe operator behavior for chain = prompt | llm_with_tools
        # Since prompt is created inside, it's hard to mock the pipe directly unless we mock ChatPromptTemplate
        
        # However, we can inspect what supervisor_node does.
        # It calls chain.invoke({"task": next_task})
        # The prompt construction uses f-string for system_prompt now.
        
        # Let's mock ChatPromptTemplate to verify the system prompt content
        with patch("src.agents.nodes.ChatPromptTemplate") as mock_prompt_cls:
            mock_prompt_template = MagicMock()
            mock_prompt_cls.from_messages.return_value = mock_prompt_template
            
            # Chain behavior: prompt | llm -> chain
            # When we do prompt | llm, it calls prompt.__or__(llm)
            mock_prompt_template.__or__.return_value = mock_chain
            
            # Define state
            state: AgentState = {
                "messages": [],
                "next_step": "",
                "current_task": "",
                "extraction_results": {"Task A": "Done"},
                "document_structure": "Section 1: Header\nSection 2: Body",
                "task_list": ["Task A", "Task B", "Task C"]
            }
            
            # Execute
            result = supervisor_node(state)
            
            # Verify next task selection
            # Task A is done, so next should be Task B
            self.assertEqual(result["current_task"], "Task B")
            self.assertEqual(result["next_step"], "tools")
            
            # Verify prompt construction
            # Check the system prompt passed to from_messages
            args, _ = mock_prompt_cls.from_messages.call_args
            messages = args[0]
            system_msg_tuple = messages[0]
            self.assertEqual(system_msg_tuple[0], "system")
            system_prompt_content = system_msg_tuple[1]
            
            # Verify document structure is in prompt
            self.assertIn("Document Structure:", system_prompt_content)
            self.assertIn("Section 1: Header", system_prompt_content)
            self.assertIn("Section 2: Body", system_prompt_content)
            
            # Verify chain invocation
            mock_chain.invoke.assert_called_with({"task": "Task B"})

    def test_supervisor_node_all_tasks_done(self):
        state: AgentState = {
            "messages": [],
            "next_step": "",
            "current_task": "",
            "extraction_results": {"Task A": "Done"},
            "document_structure": "",
            "task_list": ["Task A"]
        }
        
        result = supervisor_node(state)
        self.assertEqual(result["next_step"], "finish")

if __name__ == "__main__":
    unittest.main()

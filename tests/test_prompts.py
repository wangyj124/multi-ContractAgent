import sys
from pathlib import Path
import unittest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.agents.nodes import _load_prompt

class TestPrompts(unittest.TestCase):
    def test_supervisor_prompt(self):
        prompt = _load_prompt("supervisor")
        self.assertIn("{task}", prompt)
        self.assertIn("{document_structure}", prompt)
        print("\nSupervisor prompt loaded and verified.")

    def test_worker_prompt(self):
        prompt = _load_prompt("worker")
        self.assertIn("{task}", prompt)
        self.assertIn("{text}", prompt)
        print("\nWorker prompt loaded and verified.")

if __name__ == "__main__":
    unittest.main()

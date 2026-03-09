import unittest
from src.core.archivist import Archivist

class TestArchivistStructure(unittest.TestCase):
    def setUp(self):
        self.archivist = Archivist()
    
    def test_generate_structure_simple(self):
        chunks = [
            {'metadata': {'path': ['Chapter 1']}},
            {'metadata': {'path': ['Chapter 1', '1.1']}},
            {'metadata': {'path': ['Chapter 2']}}
        ]
        
        expected_output = (
            "Chapter 1\n"
            "  1.1\n"
            "Chapter 2"
        )
        
        result = self.archivist.generate_document_structure(chunks)
        self.assertEqual(result.strip(), expected_output.strip())

    def test_generate_structure_nested(self):
        chunks = [
            {'metadata': {'path': ['Chapter 1']}},
            {'metadata': {'path': ['Chapter 1', '1.1']}},
            {'metadata': {'path': ['Chapter 1', '1.1', '1.1.1']}},
            {'metadata': {'path': ['Chapter 1', '1.2']}}
        ]
        
        expected_output = (
            "Chapter 1\n"
            "  1.1\n"
            "    1.1.1\n"
            "  1.2"
        )
        
        result = self.archivist.generate_document_structure(chunks)
        self.assertEqual(result.strip(), expected_output.strip())

    def test_generate_structure_empty(self):
        chunks = []
        expected_output = ""
        result = self.archivist.generate_document_structure(chunks)
        self.assertEqual(result, expected_output)

    def test_generate_structure_order(self):
        chunks = [
            {'metadata': {'path': ['Preface']}},
            {'metadata': {'path': ['Chapter 1']}},
            {'metadata': {'path': ['Chapter 2']}}
        ]
        
        expected_output = (
            "Preface\n"
            "Chapter 1\n"
            "Chapter 2"
        )
        
        result = self.archivist.generate_document_structure(chunks)
        self.assertEqual(result.strip(), expected_output.strip())

if __name__ == '__main__':
    unittest.main()

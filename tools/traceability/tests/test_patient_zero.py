import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.document_indexing import DocumentService, IndexingQueue


class PatientZeroTests(unittest.TestCase):
    def test_accept_queues_work_without_processing_it(self):
        queue = IndexingQueue()
        service = DocumentService(queue)

        result = service.accept("doc-001")

        self.assertEqual({"document_id": "doc-001", "status": "accepted"}, result)
        self.assertEqual(1, len(queue))
        self.assertEqual("doc-001", queue.dequeue().document_id)


if __name__ == "__main__":
    unittest.main()

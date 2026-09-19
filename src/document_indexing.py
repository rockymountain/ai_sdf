"""Patient Zero implementation: an explicit asynchronous indexing handoff boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from collections import deque
from typing import Deque


@dataclass(frozen=True)
class DocumentIndexRequested:
    document_id: str
    requested_at: datetime


class IndexingQueue:
    """Phase-0 in-memory adapter behind the indexing queue boundary."""

    def __init__(self) -> None:
        self._jobs: Deque[DocumentIndexRequested] = deque()

    def enqueue(self, document_id: str) -> DocumentIndexRequested:
        event = DocumentIndexRequested(
            document_id=document_id,
            requested_at=datetime.now(timezone.utc),
        )
        self._jobs.append(event)
        return event

    def dequeue(self) -> DocumentIndexRequested | None:
        return self._jobs.popleft() if self._jobs else None

    def __len__(self) -> int:
        return len(self._jobs)


class DocumentService:
    def __init__(self, queue: IndexingQueue) -> None:
        self.queue = queue

    def accept(self, document_id: str) -> dict[str, str]:
        self.queue.enqueue(document_id)
        return {"document_id": document_id, "status": "accepted"}

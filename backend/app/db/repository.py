"""Provide repository operations for task API persistence."""

from collections.abc import Sequence
from dataclasses import replace
from threading import RLock
from uuid import uuid4

from backend.app.db.models import (
    OwnerRecord,
    ProcessingState,
    TaskOrigin,
    TaskRecord,
    TaskStatus,
    TaskType,
    utc_now,
)


class TaskRepository:
    """Persist owner, task, and owner-scoped idempotency records."""

    def create_owner(self) -> OwnerRecord:
        """Create an anonymous owner and installation credential.

        Returns:
            The created owner record.
        """
        raise NotImplementedError

    def get_owner_by_token(self, token: str) -> OwnerRecord | None:
        """Find an owner by anonymous installation token.

        Args:
            token: The bearer token supplied by the extension.

        Returns:
            The owner record when the token is valid, otherwise None.
        """
        raise NotImplementedError

    def list_tasks(self, owner_id: str) -> Sequence[TaskRecord]:
        """List tasks visible to an owner.

        Args:
            owner_id: The owner boundary to query.

        Returns:
            The owner's tasks ordered by most recently updated first.
        """
        raise NotImplementedError

    def create_manual_task(
        self,
        *,
        owner_id: str,
        client_request_id: str,
        title: str,
    ) -> TaskRecord:
        """Create or replay an idempotent manual task request.

        Args:
            owner_id: The owner boundary for the new task.
            client_request_id: The owner-scoped idempotency key.
            title: The manual task title.

        Returns:
            The created task, or the existing task for a repeated key.
        """
        raise NotImplementedError

    def get_task(self, *, owner_id: str, task_id: str) -> TaskRecord | None:
        """Fetch one owner-scoped task.

        Args:
            owner_id: The owner boundary to enforce.
            task_id: The task identifier.

        Returns:
            The task when it exists for this owner, otherwise None.
        """
        raise NotImplementedError

    def update_manual_task(
        self,
        *,
        owner_id: str,
        task_id: str,
        title: str | None,
        status: TaskStatus | None,
        status_reason: str | None,
        status_reason_provided: bool,
    ) -> TaskRecord | None:
        """Update a manual task owned by the requester.

        Args:
            owner_id: The owner boundary to enforce.
            task_id: The task identifier.
            title: The replacement title, if supplied.
            status: The replacement task status, if supplied.
            status_reason: The replacement task status reason, if supplied.
            status_reason_provided: Whether the patch supplied status_reason.

        Returns:
            The updated task when it exists and is manual, otherwise None.
        """
        raise NotImplementedError

    def delete_task(self, *, owner_id: str, task_id: str) -> bool:
        """Delete one owner-scoped task.

        Args:
            owner_id: The owner boundary to enforce.
            task_id: The task identifier.

        Returns:
            True when a task was deleted, otherwise False.
        """
        raise NotImplementedError

    def clear_owner_data(self, owner_id: str) -> int:
        """Delete all retained task data for one owner.

        Args:
            owner_id: The owner boundary to clear.

        Returns:
            The number of tasks deleted.
        """
        raise NotImplementedError


class InMemoryTaskRepository(TaskRepository):
    """Store task API data in process memory for local development and tests."""

    def __init__(self) -> None:
        """Initialize empty owner and task collections."""
        self._lock = RLock()
        self._owners_by_token: dict[str, OwnerRecord] = {}
        self._tasks_by_id: dict[str, TaskRecord] = {}
        self._manual_requests: dict[tuple[str, str], str] = {}

    def create_owner(self) -> OwnerRecord:
        """Create an anonymous owner and installation credential.

        Returns:
            The created owner record.
        """
        with self._lock:
            owner = OwnerRecord(
                owner_id=str(uuid4()),
                installation_id=str(uuid4()),
                installation_token=f"inst_{uuid4().hex}{uuid4().hex}",
                created_at=utc_now(),
            )
            self._owners_by_token[owner.installation_token] = owner
            return owner

    def get_owner_by_token(self, token: str) -> OwnerRecord | None:
        """Find an owner by anonymous installation token.

        Args:
            token: The bearer token supplied by the extension.

        Returns:
            The owner record when the token is valid, otherwise None.
        """
        with self._lock:
            return self._owners_by_token.get(token)

    def list_tasks(self, owner_id: str) -> Sequence[TaskRecord]:
        """List tasks visible to an owner.

        Args:
            owner_id: The owner boundary to query.

        Returns:
            The owner's tasks ordered by most recently updated first.
        """
        with self._lock:
            return sorted(
                (
                    task
                    for task in self._tasks_by_id.values()
                    if task.owner_id == owner_id
                ),
                key=lambda task: task.updated_at,
                reverse=True,
            )

    def create_manual_task(
        self,
        *,
        owner_id: str,
        client_request_id: str,
        title: str,
    ) -> TaskRecord:
        """Create or replay an idempotent manual task request.

        Args:
            owner_id: The owner boundary for the new task.
            client_request_id: The owner-scoped idempotency key.
            title: The manual task title.

        Returns:
            The created task, or the existing task for a repeated key.
        """
        with self._lock:
            request_key = (owner_id, client_request_id)
            existing_task_id = self._manual_requests.get(request_key)
            if existing_task_id is not None:
                return self._tasks_by_id[existing_task_id]

            now = utc_now()
            task = TaskRecord(
                task_id=str(uuid4()),
                owner_id=owner_id,
                origin=TaskOrigin.MANUAL,
                source_key=None,
                source_url=None,
                task_type=TaskType.MANUAL,
                title=title,
                status=TaskStatus.IN_PROGRESS,
                status_reason=None,
                summary=title,
                processing_state=ProcessingState.READY,
                processing_error_code=None,
                observed_at=None,
                updated_at=now,
                client_request_id=client_request_id,
            )
            self._tasks_by_id[task.task_id] = task
            self._manual_requests[request_key] = task.task_id
            return task

    def get_task(self, *, owner_id: str, task_id: str) -> TaskRecord | None:
        """Fetch one owner-scoped task.

        Args:
            owner_id: The owner boundary to enforce.
            task_id: The task identifier.

        Returns:
            The task when it exists for this owner, otherwise None.
        """
        with self._lock:
            task = self._tasks_by_id.get(task_id)
            if task is None or task.owner_id != owner_id:
                return None
            return task

    def update_manual_task(
        self,
        *,
        owner_id: str,
        task_id: str,
        title: str | None,
        status: TaskStatus | None,
        status_reason: str | None,
        status_reason_provided: bool,
    ) -> TaskRecord | None:
        """Update a manual task owned by the requester.

        Args:
            owner_id: The owner boundary to enforce.
            task_id: The task identifier.
            title: The replacement title, if supplied.
            status: The replacement task status, if supplied.
            status_reason: The replacement task status reason, if supplied.
            status_reason_provided: Whether the patch supplied status_reason.

        Returns:
            The updated task when it exists and is manual, otherwise None.
        """
        with self._lock:
            task = self._tasks_by_id.get(task_id)
            if (
                task is None
                or task.owner_id != owner_id
                or task.origin != TaskOrigin.MANUAL
            ):
                return None

            updated = replace(
                task,
                title=title if title is not None else task.title,
                status=status if status is not None else task.status,
                status_reason=(
                    status_reason if status_reason_provided else task.status_reason
                ),
                summary=title if title is not None else task.summary,
                updated_at=utc_now(),
            )
            self._tasks_by_id[task_id] = updated
            return updated

    def delete_task(self, *, owner_id: str, task_id: str) -> bool:
        """Delete one owner-scoped task.

        Args:
            owner_id: The owner boundary to enforce.
            task_id: The task identifier.

        Returns:
            True when a task was deleted, otherwise False.
        """
        with self._lock:
            task = self._tasks_by_id.get(task_id)
            if task is None or task.owner_id != owner_id:
                return False

            del self._tasks_by_id[task_id]
            if task.client_request_id is not None:
                self._manual_requests.pop((owner_id, task.client_request_id), None)
            return True

    def clear_owner_data(self, owner_id: str) -> int:
        """Delete all retained task data for one owner.

        Args:
            owner_id: The owner boundary to clear.

        Returns:
            The number of tasks deleted.
        """
        with self._lock:
            task_ids = [
                task.task_id
                for task in self._tasks_by_id.values()
                if task.owner_id == owner_id
            ]
            for task_id in task_ids:
                task = self._tasks_by_id.pop(task_id)
                if task.client_request_id is not None:
                    self._manual_requests.pop((owner_id, task.client_request_id), None)
            return len(task_ids)


_repository = InMemoryTaskRepository()


def get_repository() -> TaskRepository:
    """Return the process-wide task repository.

    Returns:
        The repository used by FastAPI dependencies.
    """
    return _repository

"""Batch processing service for running prompts in parallel."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from threading import Lock
from typing import Callable, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.api.v1.schemas.requests import BatchRequest
from app.api.v1.schemas.responses import BatchStatus, SendPromptResponse
from app.config import settings
from app.repositories.interaction_repository import InteractionRepository
from app.services.interaction_service import InteractionService
from app.services.provider_service import ProviderService
from app.services.providers.provider_factory import ProviderFactory

logger = logging.getLogger(__name__)


@dataclass
class _BatchTask:
  """Internal representation of a single prompt/model run."""

  prompt: str
  model: str
  provider: str


@dataclass
class _BatchJob:
  """Track batch job metadata and results."""

  batch_id: str
  tasks: List[_BatchTask]
  status: str = "pending"
  started_at: Optional[datetime] = None
  completed_at: Optional[datetime] = None
  cancel_requested: bool = False
  cancel_reason: Optional[str] = None
  results: List[SendPromptResponse] = field(default_factory=list)
  errors: List[Dict[str, str]] = field(default_factory=list)
  completed_tasks: int = 0
  failed_tasks: int = 0
  lock: Lock = field(default_factory=Lock)

  @property
  def total_tasks(self) -> int:
    """Return total number of prompt/model tasks in the job."""
    return len(self.tasks)

  def mark_started(self) -> None:
    """Mark job as started and record timestamp."""
    with self.lock:
      if self.cancel_requested:
        self.status = "cancelled"
        self.completed_at = datetime.utcnow()
        return
      self.status = "processing"
      self.started_at = datetime.utcnow()

  def mark_cancelled(self, reason: Optional[str] = None) -> None:
    """Mark the job as cancelled and stop further accounting."""
    with self.lock:
      self.cancel_requested = True
      self.cancel_reason = reason or "Cancelled by user"
      self.status = "cancelled"
      self.completed_at = datetime.utcnow()

  def add_result(self, response: SendPromptResponse) -> None:
    """Record a successful result."""
    with self.lock:
      if self.cancel_requested:
        return
      self.results.append(response)
      self.completed_tasks += 1
      self._update_status_locked()

  def add_error(self, task: _BatchTask, error_message: str) -> None:
    """Record an error for the given task."""
    with self.lock:
      if self.cancel_requested:
        return
      self.errors.append({
        "prompt": task.prompt,
        "model": task.model,
        "provider": task.provider,
        "error": error_message,
      })
      self.completed_tasks += 1
      self.failed_tasks += 1
      self._update_status_locked()

  def _update_status_locked(self) -> None:
    if self.cancel_requested:
      self.status = "cancelled"
      return
    if self.completed_tasks >= self.total_tasks:
      self.completed_at = datetime.utcnow()
      self.status = "failed" if self.failed_tasks else "completed"

  def snapshot(self) -> BatchStatus:
    """Convert job state to API schema."""
    with self.lock:
      return BatchStatus(
        batch_id=self.batch_id,
        total_tasks=self.total_tasks,
        completed_tasks=self.completed_tasks,
        failed_tasks=self.failed_tasks,
        status=self.status,
        cancel_reason=self.cancel_reason,
        results=self.results.copy(),
        errors=self.errors.copy(),
        started_at=self.started_at,
        completed_at=self.completed_at,
        estimated_completion=None,
      )


class BatchService:
  """Service orchestrating backend-managed batch requests."""

  def __init__(self, session_factory: Callable[[], Session]):
    """Initialize batch service with session factory and worker pool."""
    self._session_factory = session_factory
    self._jobs: Dict[str, _BatchJob] = {}
    self._jobs_lock = Lock()
    max_workers = max(1, settings.BATCH_MAX_CONCURRENCY)
    self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="batch-worker")
    self._default_provider_limit = max(1, settings.BATCH_PER_PROVIDER_CONCURRENCY)
    self._provider_limits = settings.get_batch_provider_limits()

  def _create_job(self, tasks: List[_BatchTask]) -> _BatchJob:
    batch_id = str(uuid4())
    job = _BatchJob(batch_id=batch_id, tasks=tasks)
    with self._jobs_lock:
      self._jobs[batch_id] = job
    return job

  async def start_batch(self, request: BatchRequest) -> BatchStatus:
    """Create a batch job and schedule asynchronous execution."""
    tasks = self._build_tasks(request)
    job = self._create_job(tasks)
    loop = asyncio.get_running_loop()
    loop.create_task(self._run_job(job))
    return job.snapshot()

  async def _run_job(self, job: _BatchJob) -> None:
    job.mark_started()
    if job.cancel_requested:
      return
    provider_semaphores = {
      provider: asyncio.Semaphore(max(1, limit or self._default_provider_limit))
      for provider, limit in self._provider_limits.items()
    }

    async def _process_task(task: _BatchTask) -> None:
      if job.cancel_requested:
        return
      semaphore = provider_semaphores.setdefault(
        task.provider,
        asyncio.Semaphore(self._default_provider_limit)
      )
      async with semaphore:
        if job.cancel_requested:
          return
        try:
          response = await self._run_provider_call(task.prompt, task.model)
          if job.cancel_requested:
            return
          job.add_result(response)
        except Exception as exc:  # noqa: BLE001
          logger.exception("Batch task failed: prompt=%s model=%s", task.prompt, task.model)
          job.add_error(task, str(exc))

    await asyncio.gather(*(_process_task(task) for task in job.tasks))

  async def _run_provider_call(self, prompt: str, model: str) -> SendPromptResponse:
    loop = asyncio.get_running_loop()
    func = partial(self._execute_send_prompt, prompt, model)
    return await loop.run_in_executor(self._executor, func)

  def _execute_send_prompt(self, prompt: str, model: str) -> SendPromptResponse:
    session = self._session_factory()
    try:
      repository = InteractionRepository(session)
      interaction_service = InteractionService(repository)
      provider_service = ProviderService(interaction_service)
      return provider_service.send_prompt(prompt=prompt, model=model, save_to_db=True)
    finally:
      session.close()

  def _build_tasks(self, request: BatchRequest) -> List[_BatchTask]:
    tasks: List[_BatchTask] = []
    for prompt in request.prompts:
      for model in request.models:
        provider = ProviderFactory.get_provider_for_model(model)
        if not provider:
          raise ValueError(f"Model '{model}' is not supported for batch processing")
        tasks.append(_BatchTask(prompt=prompt, model=model, provider=provider))
    if not tasks:
      raise ValueError("No tasks to process")
    return tasks

  def get_status(self, batch_id: str) -> BatchStatus:
    """Return the BatchStatus snapshot for a given job id."""
    job = self._jobs.get(batch_id)
    if not job:
      raise ValueError(f"Batch '{batch_id}' not found")
    return job.snapshot()

  def cancel_batch(self, batch_id: str, reason: Optional[str] = None) -> BatchStatus:
    """Request cancellation of a running job."""
    job = self._jobs.get(batch_id)
    if not job:
      raise ValueError(f"Batch '{batch_id}' not found")
    job.mark_cancelled(reason)
    return job.snapshot()

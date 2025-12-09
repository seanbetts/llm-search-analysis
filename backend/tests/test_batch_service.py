"""Tests for backend batch processing service."""

import asyncio

from app.api.v1.schemas.requests import BatchRequest
from app.services.batch_service import BatchService
from app.api.v1.schemas.responses import SendPromptResponse


class DummySession:
  """No-op session used for BatchService tests."""

  def close(self):
    return None


def session_factory():
  return DummySession()


def test_batch_service_processes_jobs(monkeypatch):
  """Batch jobs should execute tasks and record successes."""
  service = BatchService(session_factory)

  async def fake_run_provider_call(self, prompt, model):
    return SendPromptResponse(
      prompt=prompt,
      response_text="ok",
      search_queries=[],
      citations=[],
      all_sources=[],
      provider="openai",
      model=model,
      model_display_name=model,
      response_time_ms=1000,
      data_source="api",
      sources_found=0,
      sources_used=0,
      avg_rank=None,
      extra_links_count=0,
      interaction_id=1,
    )

  monkeypatch.setattr(BatchService, "_run_provider_call", fake_run_provider_call)

  request = BatchRequest(
    prompts=["Prompt A", "Prompt B"],
    provider="openai",
    models=["gpt-5.1"],
  )

  async def run_job():
    status = await service.start_batch(request)
    await asyncio.sleep(0.1)
    return service.get_status(status.batch_id)

  final_status = asyncio.run(run_job())
  assert final_status.status == "completed"
  assert final_status.completed_tasks == 2
  assert len(final_status.results) == 2

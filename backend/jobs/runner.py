"""Execution worker and job runner with atomic claim and cancellation."""
import asyncio
import json
import time
from typing import Dict, List, Optional
from backend.adapters.base import MetricCallback
from backend.adapters.registry import get_adapter
from backend.domain.models import ArtifactKind, Framework, MetricPoint, RunConfiguration, RunStatus
from backend.observability.logging import logger, set_correlation_id
from backend.persistence.database import AsyncSessionLocal
from backend.persistence.repositories import (
    ArtifactRepository,
    MetricRepository,
    RunRepository,
)

# Active cancellation registry
active_cancellations: Dict[str, bool] = {}


def request_cancellation(run_id: str) -> None:
    active_cancellations[run_id] = True


def is_run_cancelled(run_id: str) -> bool:
    return active_cancellations.get(run_id, False)


def clear_cancellation(run_id: str) -> None:
    active_cancellations.pop(run_id, None)


async def execute_run_job(run_id: str, correlation_id: Optional[str] = None) -> None:
    """Executes a single queued run with atomic state transitions and error recovery."""
    if correlation_id:
        set_correlation_id(correlation_id)

    async with AsyncSessionLocal() as session:
        run_repo = RunRepository(session)
        metric_repo = MetricRepository(session)
        artifact_repo = ArtifactRepository(session)

        # 1. Atomic claim: compare-and-set queued -> running
        claimed = await run_repo.atomic_claim(run_id)
        if not claimed:
            logger.warning(f"Could not claim run {run_id} (already claimed or cancelled)")
            return

        await run_repo.add_event(run_id, "run_started", {"timestamp": time.time()})
        await session.commit()

        run = await run_repo.get_by_id(run_id, load_details=True)
        if not run or not run.config:
            await run_repo.set_terminal_status(run_id, RunStatus.FAILED, error="Run configuration missing")
            return

        config_dict = json.loads(run.config.config_json)
        run_config = RunConfiguration(**config_dict)

        dataset_storage_key = None
        if run.config.dataset_id:
            from backend.persistence.repositories import DatasetRepository
            dataset_repo = DatasetRepository(session)
            ds = await dataset_repo.get_by_id(run.config.dataset_id)
            if ds:
                dataset_storage_key = ds.storage_key

    # 2. Metric batching and streaming
    main_loop = asyncio.get_running_loop()
    collected_metrics: List[MetricPoint] = []
    metric_lock = asyncio.Lock()
    streaming_futures = []

    def sync_metric_callback(points: List[MetricPoint]) -> None:
        collected_metrics.extend(points)

        async def push_metrics(pts: List[MetricPoint]):
            async with metric_lock:
                async with AsyncSessionLocal() as metric_session:
                    m_repo = MetricRepository(metric_session)
                    await m_repo.batch_insert(run_id, pts)
                    await metric_session.commit()

        try:
            if main_loop.is_running():
                streaming_futures.append(
                    asyncio.run_coroutine_threadsafe(push_metrics(list(points)), main_loop)
                )
        except Exception as e:
            logger.error(f"Error streaming metrics for run {run_id}: {e}")

    # 3. Execution in executor to keep event loop responsive
    def run_training_sync():
        adapter = get_adapter(run_config.framework)
        return adapter.train(
            config=run_config,
            on_metrics=sync_metric_callback,
            is_cancelled=lambda: is_run_cancelled(run_id),
            run_id=run_id,
            dataset_storage_key=dataset_storage_key,
        )

    start_exec = time.time()
    try:
        result = await main_loop.run_in_executor(None, run_training_sync)

        duration_ms = int((time.time() - start_exec) * 1000)

        # Wait until callback-driven writes scheduled on the event loop have finished.
        # The final result insert below remains the authoritative fallback and upserts
        # the same metric keys, preventing a session-close or callback race.
        for streaming_future in streaming_futures:
            try:
                await asyncio.wrap_future(streaming_future)
            except Exception as exc:
                logger.error(f"Error finalizing streamed metrics for run {run_id}: {exc}")

        async with AsyncSessionLocal() as session:
            run_repo = RunRepository(session)
            artifact_repo = ArtifactRepository(session)
            metric_repo = MetricRepository(session)

            # Ensure all metric points are flushed to the database
            metrics_to_save = result.metric_points if (result and result.metric_points) else collected_metrics
            if metrics_to_save:
                await metric_repo.batch_insert(run_id, metrics_to_save)

            if is_run_cancelled(run_id):
                await run_repo.set_terminal_status(
                    run_id,
                    RunStatus.CANCELLED,
                    error="Training cancelled by user request",
                    error_code="USER_CANCELLED",
                    duration_ms=duration_ms,
                )
                await run_repo.add_event(run_id, "run_cancelled")
            elif not result.success:
                await run_repo.set_terminal_status(
                    run_id,
                    RunStatus.FAILED,
                    error=result.error or "Training failed",
                    error_code="TRAINING_ERROR",
                    duration_ms=duration_ms,
                )
                await run_repo.add_event(run_id, "run_failed", {"error": result.error})
            else:
                # Save artifacts to DB
                for art in result.artifacts:
                    await artifact_repo.create(
                        run_id=run_id,
                        kind=art["kind"],
                        filename=art["filename"],
                        checksum=art["checksum"],
                        size_bytes=art["size_bytes"],
                        storage_key=art["storage_key"],
                    )

                await run_repo.set_terminal_status(
                    run_id,
                    RunStatus.SUCCEEDED,
                    duration_ms=duration_ms,
                )
                await run_repo.add_event(run_id, "run_succeeded", {"final_metrics": result.final_metrics})

            await session.commit()

    except Exception as exc:
        duration_ms = int((time.time() - start_exec) * 1000)
        logger.exception(f"Unhandled exception during run {run_id}: {exc}")
        async with AsyncSessionLocal() as session:
            run_repo = RunRepository(session)
            await run_repo.set_terminal_status(
                run_id,
                RunStatus.FAILED,
                error=str(exc),
                error_code="INTERNAL_ERROR",
                duration_ms=duration_ms,
            )
            await run_repo.add_event(run_id, "run_failed", {"error": str(exc)})
            await session.commit()
    finally:
        clear_cancellation(run_id)

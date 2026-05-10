"""API route handlers — upload, pipeline management, SSE streaming, downloads."""

from __future__ import annotations

import asyncio
import gc
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, UploadFile, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse
from starlette.concurrency import run_in_threadpool

from core.config import get_settings
from core.file_loader import validate_file, load_dataframe, get_preview
from core.state_manager import state_manager
from core.cache import profile_cache
from core.logging import get_logger
from tools.profiler import compute_profile
from tools.reporter import generate_report
from agents.orchestrator import run_ai_pipeline

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.schemas import (
    PipelineStage, CleaningCriteria, UploadResponse,
    PipelineStartRequest, PipelineStartResponse, ErrorResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api")


# ─── Upload ──────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload a file for processing."""
    settings = get_settings()

    # Read file bytes
    file_bytes = await file.read()
    size = len(file_bytes)

    # Validate
    error = validate_file(
        filename=file.filename or "unknown",
        content_type=file.content_type,
        size_bytes=size,
        max_size_bytes=settings.max_file_size_bytes,
    )
    if error:
        raise HTTPException(status_code=400, detail=error)

    # Save to uploads dir
    ext = Path(file.filename or "file.csv").suffix.lower()
    file_id = str(uuid.uuid4())
    upload_path = Path(settings.upload_dir) / f"{file_id}{ext}"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(file_bytes)

    # Load and get preview
    try:
        df, metadata = await run_in_threadpool(load_dataframe, upload_path, file_bytes)
        preview = get_preview(df)
    except Exception as e:
        upload_path.unlink(missing_ok=True)
        logger.error("upload_load_failed", error=str(e))
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    # Cache the file hash for profile caching
    file_hash = profile_cache.compute_hash(file_bytes)

    logger.info("file_uploaded", file_id=file_id, filename=file.filename, size=size)

    return UploadResponse(
        file_id=file_id,
        filename=file.filename or "unknown",
        size_bytes=size,
        row_count=metadata["row_count"],
        col_count=metadata["col_count"],
        columns=metadata["columns"],
        preview=preview,
    )


# ─── Pipeline Start ─────────────────────────────────────────

@router.post("/pipeline/start", response_model=PipelineStartResponse)
async def start_pipeline(request: PipelineStartRequest):
    """Start a new data cleaning pipeline."""
    settings = get_settings()
    file_id = request.file_id

    # Find uploaded file
    upload_dir = Path(settings.upload_dir)
    matching = list(upload_dir.glob(f"{file_id}.*"))
    if not matching:
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

    file_path = matching[0]
    session_id = str(uuid.uuid4())

    # Create session
    await state_manager.create_session(
        session_id=session_id,
        file_id=file_id,
        filename=file_path.name,
        criteria=request.criteria,
    )

    # Start background pipeline
    asyncio.create_task(_run_pipeline_task(session_id, file_path, request.criteria))

    logger.info("pipeline_started", session_id=session_id, file_id=file_id)
    return PipelineStartResponse(session_id=session_id)


async def _run_pipeline_task(session_id: str, file_path: Path, criteria: CleaningCriteria):
    """Background task that runs the full pipeline and emits SSE events."""
    settings = get_settings()
    start_time = time.time()

    async def emit(event_type: str, data: dict[str, Any]):
        await state_manager.push_event(session_id, {"event": event_type, "data": data})

    async def on_log(stage: str, message: str):
        await emit("log", {"stage": stage, "message": message, "timestamp": datetime.utcnow().isoformat()})

    try:
        # ── Stage 1: Parse ──
        await state_manager.update_stage(session_id, PipelineStage.PARSING, 0.0)
        await emit("progress", {"stage": "parse", "progress": 0.0})

        file_bytes = file_path.read_bytes()
        df, metadata = await run_in_threadpool(load_dataframe, file_path, file_bytes)
        await state_manager.set_dataframe(session_id, df)

        await state_manager.update_stage(session_id, PipelineStage.PARSING, 1.0)
        await emit("progress", {"stage": "parse", "progress": 1.0})
        await on_log("parse", f"✅ Parsed {metadata['row_count']} rows × {metadata['col_count']} columns")

        # ── Stage 2: Profile ──
        await state_manager.update_stage(session_id, PipelineStage.PROFILING, 0.0)
        await emit("progress", {"stage": "profile", "progress": 0.0})

        # Check cache
        file_hash = profile_cache.compute_hash(file_bytes)
        cached_profile = profile_cache.get(file_hash)

        if cached_profile:
            profile = cached_profile
            await on_log("profile", "⚡ Using cached profile")
        else:
            profile = await run_in_threadpool(compute_profile, df)
            profile_cache.set(file_hash, profile)

        await state_manager.update_stage(session_id, PipelineStage.PROFILING, 1.0, profile=profile)
        await emit("progress", {"stage": "profile", "progress": 1.0})
        await on_log("profile", f"✅ Profile complete: {profile.duplicate_count} duplicates, {len(profile.outlier_counts)} cols with outliers")

        # ── Stage 3: Clean ──
        await state_manager.update_stage(session_id, PipelineStage.CLEANING, 0.0)
        await emit("progress", {"stage": "clean", "progress": 0.0})

        cleaned_df, cleaning_log, plots, insights, used_fallback = await run_ai_pipeline(
            df, profile, criteria, on_log
        )

        await state_manager.update_stage(
            session_id, PipelineStage.CLEANING, 1.0,
            cleaning_log=cleaning_log, fallback_mode=used_fallback,
        )
        await emit("progress", {"stage": "clean", "progress": 1.0})
        await state_manager.set_dataframe(session_id, cleaned_df)

        # ── Stage 4: Analyze ──
        await state_manager.update_stage(session_id, PipelineStage.ANALYZING, 0.0, plots=plots, insights=insights)
        await emit("progress", {"stage": "analyze", "progress": 1.0})

        # ── Stage 5: Report ──
        await state_manager.update_stage(session_id, PipelineStage.REPORTING, 0.0)
        await emit("progress", {"stage": "report", "progress": 0.0})

        output_dir = Path(settings.output_dir) / session_id
        state = await state_manager.get_state(session_id)
        outputs = await run_in_threadpool(generate_report, state, cleaned_df, output_dir)

        # Convert to download URLs
        download_urls = {
            ftype: f"/api/download/{session_id}/{ftype}"
            for ftype in outputs.keys()
        }

        duration = round(time.time() - start_time, 2)
        await state_manager.update_stage(
            session_id, PipelineStage.COMPLETED, 1.0,
            outputs=download_urls,
            completed_at=datetime.utcnow().isoformat(),
            duration_sec=duration,
        )

        await emit("progress", {"stage": "report", "progress": 1.0})
        await emit("complete", {
            "session_id": session_id,
            "duration_sec": duration,
            "outputs": download_urls,
            "fallback_mode": used_fallback,
        })

        logger.info("pipeline_completed", session_id=session_id, duration=duration, fallback=used_fallback)

        # Cleanup memory
        del df
        gc.collect()

    except Exception as e:
        logger.error("pipeline_failed", session_id=session_id, error=str(e))
        await state_manager.update_stage(
            session_id, PipelineStage.FAILED, 0.0,
            error=str(e),
        )
        await emit("error", {"code": "PIPELINE_FAILED", "message": str(e), "recoverable": False})


# ─── SSE Stream ──────────────────────────────────────────────

@router.get("/pipeline/stream/{session_id}")
async def stream_pipeline(session_id: str):
    """Server-Sent Events stream for pipeline progress."""
    state = await state_manager.get_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        queue = await state_manager.get_event_queue(session_id)
        if not queue:
            return

        heartbeat_interval = 15
        last_heartbeat = time.time()

        while True:
            try:
                # Try to get event with timeout
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    event_type = event.get("event", "progress")
                    data = json.dumps(event.get("data", {}))
                    yield f"event: {event_type}\ndata: {data}\n\n"

                    # Stop streaming on terminal events
                    if event_type in ("complete", "error"):
                        break

                except asyncio.TimeoutError:
                    pass

                # Heartbeat
                if time.time() - last_heartbeat > heartbeat_interval:
                    yield ": heartbeat\n\n"
                    last_heartbeat = time.time()

                # Check if session still exists
                current_state = await state_manager.get_state(session_id)
                if not current_state or current_state.stage in (PipelineStage.COMPLETED, PipelineStage.FAILED):
                    if queue.empty():
                        break

            except Exception as e:
                logger.error("sse_error", session_id=session_id, error=str(e))
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ─── Results ─────────────────────────────────────────────────

@router.get("/pipeline/results/{session_id}")
async def get_results(session_id: str):
    """Get pipeline results."""
    state = await state_manager.get_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    return state.model_dump()


# ─── Download ────────────────────────────────────────────────

@router.get("/download/{session_id}/{file_type}")
async def download_file(session_id: str, file_type: str):
    """Download an output file."""
    settings = get_settings()
    output_dir = Path(settings.output_dir) / session_id

    file_map = {
        "csv": ("cleaned.csv", "text/csv"),
        "xlsx": ("cleaned.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "report": ("report.html", "text/html"),
        "charts": ("charts.json", "application/json"),
    }

    if file_type not in file_map:
        raise HTTPException(status_code=400, detail=f"Invalid file type: {file_type}")

    filename, media_type = file_map[file_type]
    file_path = output_dir / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type,
    )

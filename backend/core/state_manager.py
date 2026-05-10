"""Thread-safe pipeline state manager with session TTL."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import get_settings
from core.logging import get_logger

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.schemas import PipelineState, PipelineStage, CleaningCriteria, DataProfile

logger = get_logger(__name__)


class StateManager:
    """In-memory state manager for pipeline sessions."""

    def __init__(self):
        self._states: dict[str, PipelineState] = {}
        self._dataframes: dict[str, pd.DataFrame] = {}  # session_id -> DataFrame
        self._lock = asyncio.Lock()
        self._event_queues: dict[str, asyncio.Queue] = {}

    async def create_session(
        self,
        session_id: str,
        file_id: str,
        filename: str,
        criteria: CleaningCriteria,
    ) -> PipelineState:
        """Create a new pipeline session."""
        async with self._lock:
            state = PipelineState(
                session_id=session_id,
                file_id=file_id,
                filename=filename,
                criteria=criteria,
            )
            self._states[session_id] = state
            self._event_queues[session_id] = asyncio.Queue()
            logger.info("session_created", session_id=session_id, filename=filename)
            return state

    async def get_state(self, session_id: str) -> PipelineState | None:
        """Get current state for a session."""
        return self._states.get(session_id)

    async def update_stage(
        self,
        session_id: str,
        stage: PipelineStage,
        progress: float = 0.0,
        **kwargs: Any,
    ) -> None:
        """Update pipeline stage and optional fields."""
        async with self._lock:
            state = self._states.get(session_id)
            if not state:
                logger.warning("session_not_found", session_id=session_id)
                return

            state.stage = stage
            state.progress = progress

            for key, value in kwargs.items():
                if hasattr(state, key):
                    setattr(state, key, value)

            logger.info(
                "stage_updated",
                session_id=session_id,
                stage=stage.value,
                progress=progress,
            )

    async def set_dataframe(self, session_id: str, df: pd.DataFrame) -> None:
        """Store a DataFrame for a session."""
        self._dataframes[session_id] = df

    async def get_dataframe(self, session_id: str) -> pd.DataFrame | None:
        """Retrieve the DataFrame for a session."""
        return self._dataframes.get(session_id)

    async def get_event_queue(self, session_id: str) -> asyncio.Queue | None:
        """Get the SSE event queue for a session."""
        return self._event_queues.get(session_id)

    async def push_event(self, session_id: str, event: dict[str, Any]) -> None:
        """Push an SSE event to the session's queue."""
        queue = self._event_queues.get(session_id)
        if queue:
            await queue.put(event)

    async def cleanup_expired(self) -> int:
        """Remove expired sessions and their files. Returns count of cleaned sessions."""
        settings = get_settings()
        now = time.time()
        expired = []

        for sid, state in self._states.items():
            from datetime import datetime
            try:
                created = datetime.fromisoformat(state.created_at).timestamp()
            except (ValueError, TypeError):
                created = now  # Skip if timestamp is invalid
            
            if now - created > settings.session_ttl_seconds:
                expired.append(sid)

        count = 0
        for sid in expired:
            await self._cleanup_session(sid)
            count += 1

        if count > 0:
            logger.info("sessions_cleaned", count=count)

        return count

    async def _cleanup_session(self, session_id: str) -> None:
        """Clean up a single session's resources."""
        settings = get_settings()

        # Remove state
        self._states.pop(session_id, None)
        self._event_queues.pop(session_id, None)

        # Remove DataFrame from memory
        df = self._dataframes.pop(session_id, None)
        if df is not None:
            del df

        # Remove output files
        output_dir = Path(settings.output_dir) / session_id
        if output_dir.exists():
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)

        logger.info("session_cleaned", session_id=session_id)

    @property
    def active_sessions(self) -> int:
        """Count of active sessions."""
        return len(self._states)


# Global state manager instance
state_manager = StateManager()

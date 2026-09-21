"""Audio deletion + audit logging for DPDP compliance."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from db.models import AudioDeletionLog

logger = logging.getLogger(__name__)


def log_deletion(
    db: Session,
    encounter_id: str,
    chunk_ids: list[int],
    reason: str = "transcribe_complete",
) -> None:
    entry = AudioDeletionLog(
        encounter_id=encounter_id,
        chunk_ids=chunk_ids,
        deleted_at=datetime.utcnow(),
        deletion_reason=reason,
    )
    db.add(entry)
    db.commit()
    logger.info(
        "Deletion logged: encounter=%s chunks=%d reason=%s",
        encounter_id,
        len(chunk_ids),
        reason,
    )

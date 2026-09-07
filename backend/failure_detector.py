"""Failure Detection and Quality Auditing for Fact Knowledge Layer.

Logs extraction, parsing, and relationship reasoning failures, evaluates completeness,
and generates structured failure reports for demo and audit verification.
"""

from __future__ import annotations
import re
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Central in-memory failure log buffer for fast access and testing
_FAILURE_LOGS: List[Dict[str, Any]] = []


def log_failure(
    error_type: str,
    details: str,
    page_number: Optional[int] = None,
    fact_id: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Central failure logger called whenever extraction, JSON parsing, classification,
    or validation encounters an issue.
    """
    entry = {
        "id": len(_FAILURE_LOGS) + 1,
        "timestamp": datetime.utcnow().isoformat(),
        "error_type": error_type,
        "details": details,
        "page_number": page_number,
        "fact_id": fact_id,
        "context": context or {},
    }
    _FAILURE_LOGS.append(entry)
    logger.warning(f"[FailureLog] {error_type} (page={page_number}, fact={fact_id}): {details}")

    # Optionally persist to database if Session provided
    if db is not None:
        try:
            from backend.db import FailureLog
            db_entry = FailureLog(
                error_type=error_type,
                details=details,
                page_number=page_number,
                fact_id=fact_id,
                context_data=json.dumps(context or {}),
            )
            db.add(db_entry)
            db.commit()
        except Exception as e:
            logger.debug(f"Failed to persist failure to DB: {e}")

    return entry


def check_extraction_completeness(
    page_text: str,
    extracted_facts: List[Dict[str, Any]],
    page_number: int,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Quality audit: Counts numeric tokens on a page vs facts actually extracted.
    Flags pages where numbers/tables were present but under-extracted.
    """
    if not page_text:
        return {"page_number": page_number, "status": "empty", "numeric_tokens_count": 0, "facts_count": 0, "is_under_extracted": False}

    # Find numeric tokens on page (excluding pure single digits 0-9)
    raw_nums = re.findall(r"(?:[₹$€£]\s*)?[-+]?\d[\d,]*\.?\d+%?", page_text)
    # Filter out standalone 1-2 digit page numbers or dates like 2022
    numeric_tokens = [n.strip() for n in raw_nums if len(n.replace(",", "").strip()) >= 2]
    num_count = len(numeric_tokens)
    facts_count = len(extracted_facts)

    ratio = (facts_count / num_count) if num_count > 0 else 1.0
    is_under_extracted = False
    warning_reason = None

    # If page contains substantial numeric data (>= 6 numbers) but extracted 0 or very few facts (< 25% ratio)
    if num_count >= 6 and facts_count == 0:
        is_under_extracted = True
        warning_reason = f"Page {page_number} contains {num_count} numeric figures but 0 facts were extracted."
    elif num_count >= 10 and ratio < 0.20:
        is_under_extracted = True
        warning_reason = f"Page {page_number} has low fact extraction density ({facts_count} facts for {num_count} numbers, ratio {ratio:.2f})."

    result = {
        "page_number": page_number,
        "status": "warning" if is_under_extracted else "ok",
        "numeric_tokens_count": num_count,
        "facts_count": facts_count,
        "completeness_ratio": round(ratio, 2),
        "is_under_extracted": is_under_extracted,
        "warning_reason": warning_reason,
    }

    if is_under_extracted:
        log_failure(
            error_type="UNDER_EXTRACTION_WARNING",
            details=warning_reason,
            page_number=page_number,
            context={"numeric_tokens_sample": numeric_tokens[:8], "facts_count": facts_count},
            db=db,
        )

    return result


def flag_low_confidence_relationships(
    relationships: List[Dict[str, Any]],
    threshold: float = 0.50,
    db: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Surfaces any LLM relationship verdict under confidence threshold for human review
    rather than silently accepting it.
    """
    flagged = []
    for rel in relationships:
        confidence = float(rel.get("confidence", 1.0))
        if confidence < threshold:
            flag_entry = {
                "relationship": rel,
                "confidence": confidence,
                "reason": f"Relationship confidence ({confidence:.2f}) below threshold ({threshold:.2f}). Needs human review.",
            }
            flagged.append(flag_entry)
            log_failure(
                error_type="LOW_CONFIDENCE_RELATIONSHIP",
                details=f"Relationship between fact {rel.get('fact_id_1')} and {rel.get('fact_id_2')} classified as '{rel.get('relationship_type')}' with low confidence {confidence:.2f}.",
                context=rel,
                db=db,
            )

    return flagged


def get_failure_report(db: Optional[Any] = None) -> Dict[str, Any]:
    """
    Pulls complete failure history and statistics, formatted for the demo UI, API,
    and README 'Limitations and Next Steps' section.
    """
    logs = list(_FAILURE_LOGS)

    if db is not None:
        try:
            from backend.db import FailureLog
            db_logs = db.query(FailureLog).order_by(FailureLog.id.desc()).all()
            if db_logs:
                logs = [
                    {
                        "id": l.id,
                        "timestamp": l.created_at.isoformat() if l.created_at else datetime.utcnow().isoformat(),
                        "error_type": l.error_type,
                        "details": l.details,
                        "page_number": l.page_number,
                        "fact_id": l.fact_id,
                        "context": json.loads(l.context_data) if l.context_data else {},
                    }
                    for l in db_logs
                ]
        except Exception as e:
            logger.debug(f"Failed to query failure logs from DB: {e}")

    # Summary by error type
    type_counts: Dict[str, int] = {}
    for entry in logs:
        etype = entry.get("error_type", "UNKNOWN")
        type_counts[etype] = type_counts.get(etype, 0) + 1

    return {
        "total_failures_logged": len(logs),
        "failures_by_type": type_counts,
        "logs": logs,
        "audit_timestamp": datetime.utcnow().isoformat(),
        "status": "healthy" if len(logs) == 0 else "attention_required",
    }


def clear_failure_logs():
    """Clear in-memory failure logs (used in test fixtures)."""
    global _FAILURE_LOGS
    _FAILURE_LOGS = []

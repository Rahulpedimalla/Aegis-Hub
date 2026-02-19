import json
import os
import random
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from database import MobileDispatchAttempt, MobileIncident


def _http_post_json(
    url: str,
    payload: Dict[str, Any],
    idempotency_key: str,
    timeout_seconds: int = 12,
) -> Tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key,
        "X-Idempotency-Key": idempotency_key,
    }
    auth_token = os.getenv("MOBILE_TICKET_ENDPOINT_AUTH_TOKEN", "").strip()
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    req = urllib.request.Request(
        url=url,
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            status = int(response.status)
            text = response.read().decode("utf-8")
            return status, text
    except urllib.error.HTTPError as exc:
        status = int(exc.code or 500)
        text = exc.read().decode("utf-8", errors="ignore")
        return status, text


def dispatch_ticket_with_retry(
    db: Session,
    incident: MobileIncident,
    payload: Dict[str, Any],
    endpoint: str,
) -> Dict[str, Any]:
    max_attempts = max(1, int(os.getenv("MOBILE_DISPATCH_MAX_ATTEMPTS", "6")))
    base_backoff_seconds = max(0.2, float(os.getenv("MOBILE_DISPATCH_INITIAL_BACKOFF_SECONDS", "1.0")))

    response_payload: Dict[str, Any] = {}
    last_error = ""
    last_status: Optional[int] = None

    for attempt_no in range(1, max_attempts + 1):
        started = time.time()
        success = False
        response_body = ""
        error_message = None
        status_code = None

        try:
            status_code, response_body = _http_post_json(
                url=endpoint,
                payload=payload,
                idempotency_key=incident.idempotency_key,
                timeout_seconds=12,
            )
            success = (200 <= status_code < 300) or status_code == 409
            if response_body:
                try:
                    response_payload = json.loads(response_body)
                except Exception:
                    response_payload = {"raw": response_body}
        except Exception as exc:
            error_message = str(exc)
            last_error = error_message

        latency_ms = int((time.time() - started) * 1000)
        attempt_row = MobileDispatchAttempt(
            incident_id=incident.id,
            attempt_no=attempt_no,
            success=success,
            http_status=status_code,
            latency_ms=latency_ms,
            response_body=response_body[:4000] if response_body else None,
            error_message=error_message,
        )
        db.add(attempt_row)
        db.commit()

        last_status = status_code
        if success:
            ticket_id = (
                str(response_payload.get("ticket_id") or response_payload.get("sos_id") or "").strip()
                or incident.external_id
            )
            incident.dispatch_status = "Dispatched"
            incident.dispatched_ticket_id = ticket_id
            incident.dispatch_error = None
            db.commit()
            return {
                "success": True,
                "status_code": status_code,
                "ticket_id": ticket_id,
                "attempts": attempt_no,
                "response": response_payload,
            }

        # Non-retryable range: client-side validation/auth errors except 429.
        if status_code is not None and status_code < 500 and status_code not in (408, 409, 429):
            last_error = response_body[:500] if response_body else "non_retryable_client_error"
            break

        if attempt_no < max_attempts:
            sleep_seconds = base_backoff_seconds * (2 ** (attempt_no - 1))
            sleep_seconds += random.uniform(0, sleep_seconds * 0.2)
            time.sleep(min(sleep_seconds, 30))

    incident.dispatch_status = "Queued"
    incident.dispatch_error = (
        last_error
        or (f"dispatch_failed_status_{last_status}" if last_status is not None else "dispatch_failed_unknown")
    )[:2000]
    db.commit()

    return {
        "success": False,
        "status_code": last_status,
        "ticket_id": None,
        "attempts": max_attempts,
        "response": response_payload,
        "error": incident.dispatch_error,
    }

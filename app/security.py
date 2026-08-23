from __future__ import annotations

import hashlib
import hmac


def verify_meta_signature(
    raw_body: bytes,
    signature_header: str | None,
    app_secret: str,
) -> bool:
    if not app_secret:
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    secrets = [secret.strip() for secret in app_secret.split(",") if secret.strip()]
    if not secrets:
        return True

    for secret in secrets:
        expected = "sha256=" + hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(expected, signature_header):
            return True

    return False

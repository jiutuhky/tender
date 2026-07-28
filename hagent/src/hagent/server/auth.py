from __future__ import annotations

import hmac
import os
import warnings

from fastapi import HTTPException, Request, status

_DEV_MODE_WARNED = False


def require_api_key(request: Request) -> None:
    global _DEV_MODE_WARNED
    expected = os.environ.get("HAGENT_API_KEY")
    if not expected:
        if not _DEV_MODE_WARNED:
            warnings.warn(
                "HAGENT_API_KEY unset — server is unauthenticated (dev mode). "
                "Set HAGENT_API_KEY to require Bearer auth.",
                RuntimeWarning,
                stacklevel=2,
            )
            _DEV_MODE_WARNED = True
        return
    auth = request.headers.get("Authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")

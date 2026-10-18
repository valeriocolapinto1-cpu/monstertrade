"""Accesso all'API: solo il frontend (lato server) conosce il segreto condiviso.

Il controllo è un middleware, quindi avviene prima di qualsiasi altra dipendenza
(connessione al database, chiamate al broker).
"""

import hmac
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from app.config import get_settings

HEADER = "X-API-Key"
PROTECTED_PREFIX = "/api/"


def authorized(provided: str | None) -> tuple[bool, int]:
    settings = get_settings()
    secret = settings.api_shared_secret
    if secret is None:
        # Senza segreto si lavora solo in locale: in produzione si rifiuta tutto.
        if settings.environment == "production":
            return False, status.HTTP_503_SERVICE_UNAVAILABLE
        return True, status.HTTP_200_OK
    ok = provided is not None and hmac.compare_digest(
        provided.encode(), secret.get_secret_value().encode()
    )
    return ok, status.HTTP_200_OK if ok else status.HTTP_401_UNAUTHORIZED


async def api_key_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.url.path.startswith(PROTECTED_PREFIX):
        ok, code = authorized(request.headers.get(HEADER))
        if not ok:
            detail = "API non configurata" if code == 503 else "Non autorizzato"
            return JSONResponse({"detail": detail}, status_code=code)
    return await call_next(request)

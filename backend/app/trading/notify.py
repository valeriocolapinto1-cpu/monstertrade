"""Notifiche delle nuove proposte con ntfy.sh (facoltative).

L'argomento ntfy funziona come una password: va in NTFY_TOPIC, mai nel repository.
Il messaggio contiene solo strumento, orizzonte, etichetta di rischio e importo.
"""

import logging

import httpx

log = logging.getLogger("trading.notify")


def notify(topic: str | None, title: str, message: str, client: httpx.Client | None = None) -> bool:
    if not topic:
        return False
    own = client is None
    http = client or httpx.Client()
    try:
        response = http.post(
            f"https://ntfy.sh/{topic}",
            content=message.encode(),
            headers={"Title": title, "Tags": "chart_with_upwards_trend", "Priority": "default"},
            timeout=10,
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError:
        log.warning("notifica non inviata")
        return False
    finally:
        if own:
            http.close()

import os
import time
import random
import logging
from .transport import UrllibTransport
from .rest_errors import RetriableError, AmbiguousError, FatalError

log = logging.getLogger("tradesys.kite_rest")
KITE_BASE_URL = "https://api.kite.trade"


class KiteRestClient:
    """Kite connect API class .. handles everything"""

    def __init__(self, api_key=None, access_token=None, transport=None, base_url=KITE_BASE_URL,
                 max_retries=3, backoff_base=0.5, sleep_fn=time.sleep, reconcile_fn=None):
        self.api_key = api_key or os.environ.get("KITE_API_KEY")
        self.access_token = access_token or os.environ.get("KITE_ACCESS_TOKEN")
        self.transport = transport or UrllibTransport()
        self.base_url = base_url
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.sleep_fn = sleep_fn
        self.reconcile_fn = reconcile_fn  # (tag) -> existing order_id or None

    def _headers(self):
        return {"Authorization": f"token {self.api_key}:{self.access_token}"}

    def place_order(self, *, tradingsymbol, exchange, side, qty, order_type, product, tag):
        params = {"tradingsymbol": tradingsymbol, "exchange": exchange, "transaction_type": side,
                  "quantity": qty, "order_type": order_type, "product": product, "tag": tag}
        return self._send_with_retry("POST", f"{self.base_url}/orders/regular", params, tag)

    def _send_with_retry(self, method, url, params, idempotent_tag):
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self.transport.send(method, url, self._headers(), params)
            except AmbiguousError:
                log.warning("AMBIGUOUS_RESPONSE", extra={"attempt": attempt, "tag": idempotent_tag})
                existing = self.reconcile_fn(idempotent_tag) if self.reconcile_fn else None
                if existing:
                    log.info("RECONCILED_EXISTING_ORDER", extra={"tag": idempotent_tag, "order_id": existing})
                    return existing
                if attempt > self.max_retries:
                    raise
                self._sleep_backoff(attempt)
                continue
            except RetriableError as e:
                log.warning("RETRIABLE_ERROR", extra={"attempt": attempt, "error": str(e)})
                if attempt > self.max_retries:
                    raise
                self._sleep_backoff(attempt)
                continue

            if resp.status >= 500 or resp.status == 429:
                log.warning("RETRIABLE_STATUS", extra={"status": resp.status, "attempt": attempt})
                if attempt > self.max_retries:
                    raise RetriableError(f"exhausted retries, last status {resp.status}")
                self._sleep_backoff(attempt)
                continue
            if resp.status >= 400:
                raise FatalError(f"status {resp.status}: {resp.body}")
            return resp.body["data"]["order_id"]

    def _sleep_backoff(self, attempt):
        delay = self.backoff_base * (2 ** (attempt - 1)) + random.uniform(0, self.backoff_base)
        self.sleep_fn(delay)

import time
import logging
from ...data.tick_codec import split_packets, decode_packet
from ...data.validation import TickValidator

log = logging.getLogger("tradesys.kite_ws")


class KiteTickerClient:
    """Reconnect+backoff+resubscribe wrapper around a transport. Same
    reconnect logic whether the transport is the real Kite websocket or
    FakeTickerTransport in a test -- the transport is the only thing that
    changes, same principle as the order adapters."""

    def __init__(self, transport, on_tick, max_backoff=8.0, sleep_fn=time.sleep, validator=None):
        self.transport = transport
        self.on_tick = on_tick
        self.max_backoff = max_backoff
        self.sleep_fn = sleep_fn
        self.validator = validator or TickValidator()
        self._tokens, self._mode = [], "ltp"
        self.reconnect_count = 0

    def subscribe(self, tokens, mode="ltp"):
        self._tokens, self._mode = list(tokens), mode

    def run(self, max_messages=None):
        self._connect_and_subscribe()
        processed, backoff = 0, 0.5
        while max_messages is None or processed < max_messages:
            try:
                frame = self.transport.recv(timeout=1.0)
            except ConnectionError:
                self.reconnect_count += 1
                log.warning("WS_DISCONNECTED", extra={"reconnect_attempt": self.reconnect_count})
                self.sleep_fn(backoff)
                backoff = min(backoff * 2, self.max_backoff)
                self._connect_and_subscribe()
                continue
            backoff = 0.5
            if not frame:
                continue  # heartbeat / idle
            for packet in split_packets(frame):
                tick = decode_packet(packet)
                reason = self.validator.validate(tick)
                if reason:
                    log.warning("TICK_REJECTED", extra={"reason": reason, "instrument_token": tick.instrument_token})
                    continue
                self.on_tick(tick)
                processed += 1

    def _connect_and_subscribe(self):
        self.transport.connect()
        if self._tokens:
            self.transport.subscribe(self._tokens, self._mode)

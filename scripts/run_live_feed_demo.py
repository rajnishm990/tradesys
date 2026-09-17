import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tradesys.adapters.kite.rest_client import KiteRestClient
from tradesys.adapters.kite.rest_errors import RetriableError
from tradesys.adapters.kite.transport import HttpResponse
from tradesys.adapters.kite.ws_transport import FakeTickerTransport
from tradesys.adapters.kite.ws_client import KiteTickerClient
from tradesys.data.tick_codec import encode_message, encode_ltp_packet, split_packets, decode_packet


class FlakyTransport:
    """Fails twice with a 502, then succeeds , simulates a broker having
    a bad few seconds, which is the normal case retry/backoff exists for."""
    def __init__(self):
        self.calls = 0
    def send(self, method, url, headers, data):
        self.calls += 1
        if self.calls <= 2:
            raise RetriableError("simulated 502")
        return HttpResponse(200, {"data": {"order_id": f"OID{self.calls}"}})


def section(t):
    print(f"\n- - -  {t} - - - ")


def main():
    section("1. REST retry/backoff against a flaky broker")
    delays = []
    client = KiteRestClient(api_key="demo", access_token="demo", transport=FlakyTransport(), sleep_fn=delays.append)
    order_id = client.place_order(tradingsymbol="NIFTY24DECFUT", exchange="NFO", side="BUY", qty=1,
                                   order_type="MARKET", product="MIS", tag="demo1")
    print(f"order placed after retries: {order_id}, backoff delays used: {[round(d, 3) for d in delays]}")

    section("2. Websocket reconnect on a dropped connection")
    frames = [encode_message([encode_ltp_packet(256265, 100.0)]),
              encode_message([encode_ltp_packet(256265, 100.2)]),
              "DISCONNECT",
              encode_message([encode_ltp_packet(256265, 99.8)])]
    ticks = []
    ws = KiteTickerClient(FakeTickerTransport(frames), on_tick=ticks.append, sleep_fn=lambda d: None)
    ws.subscribe([256265], mode="ltp")
    ws.run(max_messages=3)
    print(f"ticks received: {[t.last_price for t in ticks]}, reconnects: {ws.reconnect_count}")

    section("3. Hot-path parse throughput")
    packets = [encode_ltp_packet(256265 + i, 100.0 + i * 0.1) for i in range(50)]
    message = encode_message(packets)
    n_iterations = 20_000
    start = time.perf_counter()
    for _ in range(n_iterations):
        for p in split_packets(message):
            decode_packet(p)
    elapsed = time.perf_counter() - start
    total_ticks = n_iterations * len(packets)
    print(f"parsed {total_ticks:,} ticks in {elapsed:.3f}s -> {total_ticks / elapsed:,.0f} ticks/sec")


if __name__ == "__main__":
    main()

import pytest
from tradesys.adapters.kite.rest_client import KiteRestClient
from tradesys.adapters.kite.rest_errors import RetriableError, AmbigousError, FatalError
from tradesys.adapters.kite.transport import HttpResponse


class ScriptedTransport:
    """Fake transport driven by a scripted list of outcomes -- no network."""
    def __init__(self, script):
        self.script = list(script)

    def send(self, method, url, headers, data):
        action = self.script.pop(0)
        if action[0] == "retriable":
            raise RetriableError("simulated connection refused")
        if action[0] == "ambiguous":
            raise AmbigousError("simulated timeout")
        if action[0] == "status":
            return HttpResponse(action[1], action[2])
        raise AssertionError("bad script action")


def _client(script, **kwargs):
    sleeps = []
    c = KiteRestClient(api_key="x", access_token="y", transport=ScriptedTransport(script),
                        sleep_fn=sleeps.append, max_retries=3, **kwargs)
    return c, sleeps

def _place(c):
    return c.place_order(tradingsymbol="NIFTY", exchange="NFO", side="BUY", qty=1,
                          order_type="MARKET", product="MIS", tag="t")


def test_retries_on_transient_error_then_succeeds():
    c, sleeps = _client([("retriable",), ("retriable",), ("status", 200, {"data": {"order_id": "OID1"}})])
    assert _place(c) == "OID1"
    assert len(sleeps) == 2            # one sleep before each retry, none after success
    assert sleeps[1] > sleeps[0]       # exponential backoff grows

def test_fatal_status_does_not_retry():
    c, sleeps = _client([("status", 400, {"error": "bad tradingsymbol"})])
    with pytest.raises(FatalError):
        _place(c)
    assert sleeps == []

def test_exhausting_retries_on_5xx_raises_retriable():
    c, sleeps = _client([("status", 502, {}), ("status", 502, {}), ("status", 502, {}), ("status", 502, {})])
    with pytest.raises(RetriableError):
        _place(c)
    assert len(sleeps) == 3  # max_retries=3: 4 attempts total, 3 backoff sleeps between them

def test_ambiguous_timeout_reconciles_instead_of_blindly_retrying():
    seen_tags = []
    def reconcile(tag):
        seen_tags.append(tag)
        return "OID_EXISTING"
    c, sleeps = _client([("ambiguous",)], reconcile_fn=reconcile)
    assert _place(c) == "OID_EXISTING"
    assert seen_tags == ["t"]
    assert sleeps == []  # resolved via reconciliation, no retry needed at all

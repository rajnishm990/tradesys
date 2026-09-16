import logging

log = logging.getLogger("tradesys.alerts")


def check_deviation(label: str, expected: float, actual: float, tolerance: float) -> bool:
    """ Logs CRITICAL and returns True
    if live has drifted from what was expected by more than `tolerance`."""
    diff = abs(expected - actual)
    breached = diff > tolerance
    if breached:
        log.critical("DEVIATION_ALERT", extra={"label": label, "expected": expected, "actual": actual, "diff": diff})
    return breached

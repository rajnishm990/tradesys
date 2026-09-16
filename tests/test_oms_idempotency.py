import tempfile, os
from tradesys.data.bars import BarSeries
from tradesys.data.sample_loader import generate_synthetic_bars
from tradesys.strategy.grid import GridStrategy, GridConfig, Order, OrderSide, OrderReason
from tradesys.adapters.live_stub import LiveStubAdapter
from tradesys.oms.store import OrderStore
from tradesys.observability.blotter import Blotter
from tradesys.engine.runner import run, make_client_order_id


def test_duplicate_intent_is_a_no_op():
    store = OrderStore()
    order = Order(OrderSide.BUY, 1, OrderReason.ENTRY, seq=1)
    coid = make_client_order_id("s", 1)
    assert store.record_intent(coid, order, bar_index=0) is True
    # simulates a crash right after send, then a naive retry re-submitting
    # the identical intent -- must be rejected, not double-counted
    assert store.record_intent(coid, order, bar_index=0) is False
    assert store.count_orders() == 1


def test_restart_mid_run_reproduces_the_uninterrupted_result():
    bars = generate_synthetic_bars(n_bars=150, seed=9, vol=0.012)
    crash_at = 80
    db_path = tempfile.mktemp(suffix=".db")

    # ground truth: one uninterrupted run
    baseline = GridStrategy("s", GridConfig())
    run(baseline, LiveStubAdapter(bars), bars, OrderStore(), Blotter())

    # phase 1: process bars 0..79 against a durable store, then "die"
    store = OrderStore(db_path)
    phase1_strategy = GridStrategy("s", GridConfig())
    phase1_bars = BarSeries([bars.bar_at(i) for i in range(crash_at)])
    run(phase1_strategy, LiveStubAdapter(phase1_bars), phase1_bars, store, Blotter())
    del phase1_strategy, store  # simulate the process being gone

    # phase 2: brand-new objects, same durable store on disk -- state is
    # rebuilt from fills on disk, not inherited from the dead process
    store2 = OrderStore(db_path)
    lots, avg_entry, last_entry = store2.reconciled_position()
    resumed = GridStrategy("s", GridConfig())
    resumed.seed_position(lots, avg_entry, last_entry)
    resumed.seed_sequence(store2.count_orders())
    run(resumed, LiveStubAdapter(bars), bars, store2, Blotter(), start_index=crash_at)

    assert resumed.lots == baseline.lots
    assert resumed.avg_entry == baseline.avg_entry
    assert resumed.halted == baseline.halted

    # a retried order from just before the crash must still be rejected
    dup_order = Order(OrderSide.BUY, 1, OrderReason.ENTRY, seq=1)
    dup_coid = make_client_order_id("s", 1)
    assert store2.record_intent(dup_coid, dup_order, bar_index=0) is False

    os.remove(db_path)

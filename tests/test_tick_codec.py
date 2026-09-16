import pytest
from tradesys.data.tick_codec import split_packets, decode_packet, encode_message, encode_ltp_packet


def test_round_trip_single_ltp_packet():
    message = encode_message([encode_ltp_packet(256265, 101.55)])
    packets = split_packets(message)
    assert len(packets) == 1
    tick = decode_packet(packets[0])
    assert tick.instrument_token == 256265
    assert round(tick.last_price, 2) == 101.55
    assert tick.mode == "ltp"

def test_round_trip_multiple_packets_in_one_message():
    message = encode_message([encode_ltp_packet(1, 10.0), encode_ltp_packet(2, 20.5)])
    decoded = [decode_packet(p) for p in split_packets(message)]
    assert [(t.instrument_token, t.last_price) for t in decoded] == [(1, 10.0), (2, 20.5)]

def test_heartbeat_message_yields_no_packets():
    assert split_packets(b"\x00") == []
    assert split_packets(b"") == []

def test_short_packet_raises_instead_of_silently_misparsing():
    with pytest.raises(ValueError):
        decode_packet(b"\x00\x00\x00")

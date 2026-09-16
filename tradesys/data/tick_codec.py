import struct
from dataclasses import dataclass

_HEADER = struct.Struct(">H")        # number of packets in the message
_PACKET_LEN = struct.Struct(">H")    # per-packet length prefix
_LTP_PREFIX = struct.Struct(">ii")   # instrument_token, price*100 , common prefix of every mode

LTP_LEN, QUOTE_LEN, FULL_LEN = 8, 44, 164


@dataclass(frozen=True, slots=True)
class Tick:
    instrument_token: int
    last_price: float
    mode: str
    raw_extra: bytes = b""


def split_packets(message: bytes) -> list:
    """Kite's otuer frame spec,  2-byte packet count, then each packet is a
    2-byte length prefix followed by that many bytes. A <=1 byte message is
    a heartbeat and carries no packets."""
    if len(message) <= 1:
        return []
    n = _HEADER.unpack_from(message, 0)[0]
    packets, offset = [], _HEADER.size
    for _ in range(n):
        length = _PACKET_LEN.unpack_from(message, offset)[0]
        offset += _PACKET_LEN.size
        packets.append(message[offset:offset + length])
        offset += length
    return packets


def decode_packet(payload: bytes) -> Tick:
    if len(payload) < LTP_LEN:
        raise ValueError(f"packet too short: {len(payload)} bytes")
    token, price_paise = _LTP_PREFIX.unpack_from(payload, 0)
    mode = "ltp" if len(payload) == LTP_LEN else "quote" if len(payload) == QUOTE_LEN else "full"
    # Quote/full packets carry more fields (volumes, OHLC, 5-level depth) at
    # fixed offsets after byte 8 , NOT decoded here. 
    return Tick(instrument_token=token, last_price=price_paise / 100.0, mode=mode, raw_extra=payload[8:])


def encode_message(packets: list) -> bytes:
    """ make exact kite order ,Used by the fake ticker transport so tests exercise the real decode path, not a shortcut."""
    body = _HEADER.pack(len(packets))
    for p in packets:
        body += _PACKET_LEN.pack(len(p)) + p
    return body


def encode_ltp_packet(instrument_token: int, price_rupees: float) -> bytes:
    return _LTP_PREFIX.pack(instrument_token, round(price_rupees * 100))

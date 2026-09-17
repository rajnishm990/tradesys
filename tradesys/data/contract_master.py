from dataclasses import dataclass 
from datetime import datetime, date 
from typing import Optional , Dict , List 



@dataclass(frozen=True) 
class Instrument:
    token: int 
    symbol : str 
    expiry: date 
    lot_size : int 
    segment: str # NFO-FUT or MCX-FUT 


class ContractMaster:
    def __init__(self):
        self._master: Dict[str, List[Instrument]] = {} 

    def load_instruments(self, records: List[dict]):
        """Parses raw broker contract definitions."""
        self._master.clear()
        for row in records:
            base_sym = row["name"]
            expiry = datetime.strptime(row["expiry"], "%Y-%m-%d").date()
            inst = Instrument(
                token=int(row["instrument_token"]),
                symbol=row["tradingsymbol"],
                expiry=expiry,
                lot_size=int(row["lot_size"]),
                segment=row["segment"]
            )
            self._master.setdefault(base_sym, []).append(inst)

        # Sort each instrument chain by expiry ascending
        for sym in self._master:
            self._master[sym].sort(key=lambda x: x.expiry)

    def get_active_contract(self, base_symbol: str, as_of: date) -> Optional[Instrument]:
        """Returns the current front-month contract."""
        chain = self._master.get(base_symbol, [])
        valid = [inst for inst in chain if inst.expiry >= as_of]
        return valid[0] if valid else None

    def check_rollover_signal(self, base_symbol: str, current_token: int, as_of: date, dte_threshold: int = 1) -> Optional[Instrument]:
        """
        Determines if the front contract must roll to the next-month contract.
        Returns target Instrument if roll is required, None otherwise.
        """
        chain = [inst for inst in self._master.get(base_symbol, []) if inst.expiry >= as_of]
        if len(chain) < 2:
            return None  # No back-month contract available to roll into
        
        current_contract = next((i for i in chain if i.token == current_token), None)
        if not current_contract:
            return None

        dte = (current_contract.expiry - as_of).days
        if dte <= dte_threshold:
            # Signal: Roll from chain[0] to chain[1]
            return chain[1]
            
        return None
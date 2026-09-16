from typing import Optional 


class RealKiteWebSockterTransport:
    """  Talsk to wss://ws.kite.trade using KITE_API_KEY and Token ..  """

    def __init__(self, api_key=None , access_token=None):
        import os 
        self.api_key = api_key or os.environ.get("KITE_API_KEY") 
        self.access_token = access_token or os.environ.get("KITE_ACCESS_TOKEN")
        self._ws = None 

    def connect(self, tokens: list , mode: str) -> None:
        import json 
        self._ws.send(json.dumps({"a": "subscribe", "v": list(tokens)}))
        self._ws.send(json.dumps({"a": "mode", "v": [mode, list(tokens)]})) 

    def recv(self , timeout:float) -> Optional[bytes]:
        return self._ws.recv(timeout=timeout)

    def close(self) -> None:
        if self._ws:
            self._ws.close()



class FakeTickerTransport:
    """Test/demo transport: replays a scripted list of frames. An item
    equal to the string 'DISCONNECT' raises ConnectionError once, to
    exercise the reconnect path without a real socket."""

    def __init__(self, frames):
        self._frames = list(frames)
        self.connect_count = 0
        self.subscriptions = []

    def connect(self) -> None:
        self.connect_count += 1

    def subscribe(self, tokens: list, mode: str) -> None:
        self.subscriptions.append((tuple(tokens), mode))

    def recv(self, timeout: float) -> Optional[bytes]:
        if not self._frames:
            return None
        item = self._frames.pop(0)
        if item == "DISCONNECT":
            raise ConnectionError("simulated disconnect")
        return item

    def close(self) -> None:
        pass

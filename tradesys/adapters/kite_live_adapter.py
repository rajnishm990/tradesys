from .base import Fill 
from .kite.rest_client import KiteRestClient 


class KiteLiveAdapter:
    """ Actual broker adpater , same submit signature as backtester one 
        and live one .. So the Engine loop doesn't change to us it ..
        only tocuhes network if KITE_API_KEY and token are set .. else this will inject client with fake transport for tests and demos 
      
       
    """

    def __init__(self, tradingsymbol: str , exchange:str="NFO", client: KiteRestClient=None):
        self.tradingsymbol= tradingsymbol 
        self.exchange=exchange 
        self.client = client or KiteRestClient()

    def submit(self, order, client_order_id:str , bar_index:int) -> Fill:
        order_id = self.client.place_order(
            tradingsymbol=self.tradingsymbol, exchange=self.exchange, side=order.side.value , qty=order.qty, order_type="MARKET", product="MIS", tag= client_order_id[:20]
        )

        # NOTE : place_order only confirms if kite accepted our order or not , the fill price that needs an order status poll or a listener updating the OMS  row from pending to filled not build yet .. 
        #      The OMS schema already contains status col
        return Fill(client_order_id, price= float("nan"), qty=order.qty , cost=0.0 ,ts=bar_index) 
class RetriableError(Exception):
    """ defo didn't succeed could be connection refused , 5xx ,  4xx coded error , safe to retry """

class AmbigousError(Exception):
    """  Unknown Whether the order reached the broker , must reconcile aginst broker before retyring  """


class FatalError(Exception):
    """ Broker Rejected the request (bad params , not enough margin etc). retrying won't help """
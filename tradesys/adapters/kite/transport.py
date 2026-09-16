import json 
import urllib.request 
import urllib.error 
import urllib.parse 

from .rest_errors import RetriableError , AmbigousError 

class HttpResponse:
    def __init__(self, status:int, body: dict):
        self.status = status 
        self.body = body 


class UrllibTransport:
    """  
    actual transport , only comes into play when KITE access token or api keys are set 
    this is never called in testsss .. Test inects fake transport  
    """

    def send(self, method: str, url: str, headers: dict, data: dict) -> HttpResponse:
        body = urllib.parse.urlencode(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return HttpResponse(resp.status, json.loads(resp.read() or b"{}"))
        except urllib.error.HTTPError as e:
            return HttpResponse(e.code, json.loads(e.read() or b"{}"))
        except TimeoutError as e:
            raise AmbigousError(str(e))
        except urllib.error.URLError as e:
            raise RetriableError(str(e))
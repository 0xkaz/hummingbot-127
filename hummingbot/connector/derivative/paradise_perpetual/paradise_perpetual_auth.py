import hashlib
import hmac
import json
import time
from decimal import Decimal
from typing import Any, Dict, List

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class ParadisePerpetualAuth(AuthBase):
    """
    Auth class required by Paradise Perpetual API
    """
    def __init__(self, api_key: str, secret_key: str):
        self._api_key: str = api_key
        self._secret_key: str = secret_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        request = await self._authenticate(request)
        return request    
    
    async def _authenticate(self, request: RESTRequest) -> RESTRequest:
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.header_for_authentication(request))
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. OKX does not use this
        functionality
        """
        return request  # pass-through

    def get_ws_auth_payload(self) -> List[str]:
        """
        Generates a dictionary with all required information for the authentication process
        :return: a dictionary of authentication info including the request signature
        """
        expires = self._get_expiration_timestamp()        
        raw_signature = f"/ws/futures{expires}"
        signature = hmac.new(
            self._secret_key.encode("utf-8"), raw_signature.encode("utf-8"), hashlib.sha384
        ).hexdigest()        
        auth_message = {
            "op": "authKeyExpires",
            "args": [self._api_key, expires, signature]
        }
        return auth_message

    def header_for_authentication(self, request: RESTRequest) -> Dict[str, str]:
        lang = "utf-8"
        nonce = str(int(time.time() * 1000))
        path = request.url.replace("https://api.paradise.exchange/futures", "").replace("https://api.testparadise.exchange/futures", "")
        # if request.params != None:
        #     path += '?' + str(request.params)
        message = path + nonce
        if request.method == RESTMethod.POST:
            message += str(request.data)
        signature = hmac.new(bytes(self._secret_key, lang), msg=bytes(message, lang), digestmod=hashlib.sha384).hexdigest()
        headers = {
            "request-api": self._api_key,
            "request-nonce": nonce,
            "request-sign": signature
        }        
        
        return headers

    @staticmethod
    def _get_timestamp():
        return str(int(time.time() * 1e3))

    @staticmethod
    def _get_expiration_timestamp():
        return str(int((round(time.time()) + 5) * 1e3))

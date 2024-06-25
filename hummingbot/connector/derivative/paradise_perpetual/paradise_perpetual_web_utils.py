from typing import Any, Callable, Dict, List, Optional

from hummingbot.connector.derivative.paradise_perpetual import paradise_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class HeadersContentRESTPreProcessor(RESTPreProcessorBase):
    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        request.headers = request.headers or {}
        request.headers["Content-Type"] = "application/json"
        return request


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(throttler=throttler))
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
            HeadersContentRESTPreProcessor(),
        ],
    )
    return api_factory


def create_throttler(trading_pairs: List[str] = None) -> AsyncThrottler:
    throttler = AsyncThrottler(build_rate_limits(trading_pairs))
    return throttler


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None, domain: str = CONSTANTS.DEFAULT_DOMAIN
) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    endpoint = CONSTANTS.SERVER_TIME_PATH_URL
    url = get_rest_url_for_endpoint(endpoint=endpoint, domain=domain)
    limit_id = endpoint
    response = await rest_assistant.execute_request(
        url=url,
        throttler_limit_id=limit_id,
        method=RESTMethod.GET,
    )
    server_time = float(response["epoch"])

    return server_time


def endpoint_from_message(message: Dict[str, Any]) -> Optional[str]:
    endpoint = None
    if isinstance(message, dict):
        if "topic" in message.keys():
            endpoint = message["topic"]
        elif endpoint is None and "channel" in message.keys() and len(message["channel"]) > 0:
            endpoint = message["channel"][0]
    return endpoint


def payload_from_message(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload = []
    if "data" in message:
        payload = message["data"]
    return payload


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


def get_rest_url_for_endpoint(
    endpoint: Dict[str, str], trading_pair: Optional[str] = None, domain: str = CONSTANTS.DEFAULT_DOMAIN
):
    variant = domain if domain else CONSTANTS.DEFAULT_DOMAIN
    return CONSTANTS.REST_URLS.get(variant) + endpoint


def get_pair_specific_limit_id(base_limit_id: str, trading_pair: str) -> str:
    limit_id = f"{base_limit_id}-{trading_pair}"
    return limit_id


def get_rest_api_limit_id_for_endpoint(endpoint: Dict[str, str], trading_pair: Optional[str] = None) -> str:
    limit_id = endpoint
    if trading_pair is not None:
        limit_id = get_pair_specific_limit_id(limit_id, trading_pair)
    return limit_id


def _wss_url(endpoint: Dict[str, str], connector_variant_label: Optional[str]) -> str:
    variant = connector_variant_label if connector_variant_label else CONSTANTS.DEFAULT_DOMAIN
    return endpoint.get(variant)


def build_rate_limits(trading_pairs: Optional[List[str]] = None) -> List[RateLimit]:
    trading_pairs = trading_pairs or []
    rate_limits = []

    rate_limits.extend(_build_global_rate_limits())
    rate_limits.extend(_build_public_rate_limits())
    rate_limits.extend(_build_private_rate_limits(trading_pairs))

    return rate_limits


def _build_private_general_rate_limits() -> List[RateLimit]:
    rate_limits = [
        RateLimit(
            limit_id=CONSTANTS.GET_WALLET_BALANCE_PATH_URL,
            limit=120,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        ),
        RateLimit(
            limit_id=CONSTANTS.SET_POSITION_MODE_URL,
            limit=120,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        ),
    ]
    return rate_limits


def _build_global_rate_limits() -> List[RateLimit]:
    rate_limits = [
        RateLimit(limit_id=CONSTANTS.GET_LIMIT_ID, limit=CONSTANTS.GET_RATE, time_interval=1),
        RateLimit(limit_id=CONSTANTS.POST_LIMIT_ID, limit=CONSTANTS.POST_RATE, time_interval=1),
    ]
    return rate_limits


def _build_public_rate_limits():
    public_rate_limits = [
        RateLimit(
            limit_id=CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT,
            limit=CONSTANTS.GET_RATE,
            time_interval=1,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        ),
        RateLimit(
            limit_id=CONSTANTS.QUERY_SYMBOL_ENDPOINT,
            limit=CONSTANTS.GET_RATE,
            time_interval=1,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        ),
        RateLimit(
            limit_id=CONSTANTS.ORDER_BOOK_ENDPOINT,
            limit=CONSTANTS.GET_RATE,
            time_interval=1,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        ),
        RateLimit(
            limit_id=CONSTANTS.SERVER_TIME_PATH_URL,
            limit=CONSTANTS.GET_RATE,
            time_interval=1,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        )
    ]
    return public_rate_limits


def _build_private_rate_limits(trading_pairs: List[str]) -> List[RateLimit]:
    rate_limits = []

    rate_limits.extend(_build_private_pair_specific_rate_limits(trading_pairs))
    rate_limits.extend(_build_private_general_rate_limits())

    return rate_limits


def _build_private_pair_specific_rate_limits(trading_pairs: List[str]) -> List[RateLimit]:
    rate_limits = []

    for trading_pair in trading_pairs:
        rate_limits.extend(_build_private_pair_specific__rate_limits(trading_pair))
    return rate_limits


def _build_private_pair_specific__rate_limits(trading_pair: str) -> List[RateLimit]:
    rate_limits = [
        RateLimit(limit_id=CONSTANTS.REQUEST_WEIGHT, limit=2400, time_interval=CONSTANTS.ONE_MINUTE),
        RateLimit(limit_id=CONSTANTS.ORDERS_1MIN, limit=1200, time_interval=CONSTANTS.ONE_MINUTE),
        RateLimit(limit_id=CONSTANTS.ORDERS_1SEC, limit=300, time_interval=10),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.SET_LEVERAGE_PATH_URL, trading_pair=trading_pair
            ),
            limit=75,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.POST_LIMIT_ID),
                           LinkedLimitWeightPair(CONSTANTS.REQUEST_WEIGHT)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL,
                trading_pair=trading_pair,
            ),
            limit=120,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID),
                           LinkedLimitWeightPair(CONSTANTS.REQUEST_WEIGHT)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.GET_PREDICTED_FUNDING_RATE_PATH_URL,
                trading_pair=trading_pair,
            ),
            limit=120,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID),
                           LinkedLimitWeightPair(CONSTANTS.REQUEST_WEIGHT)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.GET_POSITIONS_PATH_URL, trading_pair=trading_pair
            ),
            limit=120,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID),
                           LinkedLimitWeightPair(CONSTANTS.REQUEST_WEIGHT)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL,
                trading_pair=trading_pair,
            ),
            limit=100,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.POST_LIMIT_ID),
                           LinkedLimitWeightPair(CONSTANTS.ORDERS_1SEC)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL,
                trading_pair=trading_pair,
            ),
            limit=100,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.POST_LIMIT_ID),
                           LinkedLimitWeightPair(CONSTANTS.ORDERS_1SEC)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL,
                trading_pair=trading_pair,
            ),
            limit=600,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID),
                           LinkedLimitWeightPair(CONSTANTS.REQUEST_WEIGHT)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.USER_TRADE_RECORDS_PATH_URL,
                trading_pair=trading_pair,
            ),
            limit=120,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        ),
    ]

    return rate_limits

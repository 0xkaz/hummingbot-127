from hummingbot.core.data_type.common import OrderType, PositionMode

EXCHANGE_NAME = "paradise_perpetual"

DEFAULT_DOMAIN = "paradise_perpetual_main"

DEFAULT_TIME_IN_FORCE = "GTC"

REST_URLS = {"paradise_perpetual_main": "https://api.paradise.exchange/",
             "paradise_perpetual_testnet": "https://api.testparadise.exchange/"}

WSS_URLS = {"paradise_perpetual_main": "wss://ws.paradise.exchange/ws/futures",
            "paradise_perpetual_testnet": "wss://ws.testparadise.exchange/ws/futures"}

WSS_OB_URLS = {"paradise_perpetual_main": "wss://ws.paradise.exchange/ws/oss/futures",
               "paradise_perpetual_testnet": "wss://ws.testparadise.exchange/ws/oss/futures"}

REST_API_VERSION = "futures/api/v2.1"

HBOT_BROKER_ID = "Hummingbot"

MAX_ID_LEN = 36
SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 30
POSITION_IDX_ONEWAY = 0
POSITION_IDX_HEDGE_BUY = 1
POSITION_IDX_HEDGE_SELL = 2

ORDER_TYPE_MAP = {
    OrderType.LIMIT: "Limit",
    OrderType.MARKET: "Market",
    OrderType.LIMIT_MAKER: "AlgoOrder"
}

POSITION_MODE_API_ONEWAY = "ONE_WAY"
POSITION_MODE_API_HEDGE = "HEDGE"
POSITION_MODE_MAP = {
    PositionMode.ONEWAY: POSITION_MODE_API_ONEWAY,
    PositionMode.HEDGE: POSITION_MODE_API_HEDGE,
}

REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS_1MIN = "ORDERS_1MIN"
ORDERS_1SEC = "ORDERS_1SEC"

ONE_HOUR = 3600
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

LATEST_SYMBOL_INFORMATION_ENDPOINT = f"{REST_API_VERSION}/price"
QUERY_SYMBOL_ENDPOINT = f"{REST_API_VERSION}/market_summary"
ORDER_BOOK_ENDPOINT = f"{REST_API_VERSION}/orderbook/L2"
SERVER_TIME_PATH_URL = "/spot/api/v3.2/time"
# REST API Private Endpoints
SET_LEVERAGE_PATH_URL = f"{REST_API_VERSION}/leverage"
GET_LAST_FUNDING_RATE_PATH_URL = f"{REST_API_VERSION}/market_summary"
GET_PREDICTED_FUNDING_RATE_PATH_URL = f"{REST_API_VERSION}/market_summary"
GET_POSITIONS_PATH_URL = f"{REST_API_VERSION}/user/positions"
PLACE_ACTIVE_ORDER_PATH_URL = f"{REST_API_VERSION}/order"
CANCEL_ACTIVE_ORDER_PATH_URL = f"{REST_API_VERSION}/order"
# CANCEL_ALL_ACTIVE_ORDERS_PATH_URL = f"{REST_API_VERSION}"
QUERY_ACTIVE_ORDER_PATH_URL = f"{REST_API_VERSION}/order"
USER_TRADE_RECORDS_PATH_URL = f"{REST_API_VERSION}/user/trade_history"
GET_WALLET_BALANCE_PATH_URL = f"{REST_API_VERSION}/user/wallet"
SET_POSITION_MODE_URL = f"{REST_API_VERSION}/position_mode"

# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (5, 5)  # seconds before snapshot, seconds after snapshot

# WebSocket Public Endpoints
WS_PING_REQUEST = "ping"
WS_ORDER_BOOK_EVENTS_TOPIC = "snapshotL1"
WS_TRADES_TOPIC = "tradeHistoryApi"
WS_INSTRUMENTS_INFO_TOPIC = "instrument_info.100ms"
WS_AUTHENTICATE_USER_ENDPOINT_NAME = "auth"
WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME = "positions"
WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME = "fills"
WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME = "notificationApiV2"
WS_SUBSCRIPTION_WALLET_ENDPOINT_NAME = "wallet"

# Order Statuses
ORDER_STATE = {
    "Inserted": 2,
    "Transacted": 3,
    "Filled": 4,
    "PartiallyFilled": 5,
    "Cancelled": 6,
    "Refunded": 7,
    "Rejected": 15,
    "NotFound": 16,
    "Failed": 17,
    "TriggerInserted": 9,
    "TriggerActivated": 10
}

GET_LIMIT_ID = "GETLimit"
POST_LIMIT_ID = "POSTLimit"
GET_RATE = 49  # per second
POST_RATE = 19  # per second

# Request error codes
RET_CODE_OK = 20
RET_CODE_PARAMS_ERROR = 10001
RET_CODE_API_KEY_INVALID = 10003
RET_CODE_AUTH_TIMESTAMP_ERROR = 10021
RET_CODE_ORDER_NOT_EXISTS = 20001
RET_CODE_MODE_POSITION_NOT_EMPTY = 30082
RET_CODE_MODE_NOT_MODIFIED = 30083
RET_CODE_MODE_ORDER_NOT_EMPTY = 30086
RET_CODE_API_KEY_EXPIRED = 33004
RET_CODE_LEVERAGE_UNDERGOING_LIQUIDATION = 64
RET_CODE_POSITION_ZERO = 130125

from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0006"),
    taker_percent_fee_decimal=Decimal("0.0001"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"


def get_paradise_symbol(trading_pair: str) -> str:
    paradise_symbol = f"{trading_pair.split('-')[0]}PFC"
    return paradise_symbol


def get_trading_pair_name(symbol: str) -> str:
    name = symbol.replace('PFC', '-USD')
    return name


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    active = exchange_info.get("active")
    return active


def get_next_funding_timestamp(current_timestamp: float) -> float:
    # On Paradise Perpetuals, funding occurs every 8 hours at 00:00UTC, 08:00UTC and 16:00UTC.
    # Reference: https://help.paradise.com/hc/en-us/articles/360039261134-Funding-fee-calculation
    int_ts = int(current_timestamp)
    eight_hours = 8 * 60 * 60
    mod = int_ts % eight_hours
    return float(int_ts - mod + eight_hours)


class ParadisePerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="paradise_perpetual", client_data=None)
    paradise_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Paradise Perpetual API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    paradise_perpetual_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Paradise Perpetual secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "paradise_perpetual"


KEYS = ParadisePerpetualConfigMap.construct()

OTHER_DOMAINS = ["paradise_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"paradise_perpetual_testnet": "paradise_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"paradise_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {
    "paradise_perpetual_testnet": TradeFeeSchema(
        maker_percent_fee_decimal=Decimal("-0.00025"),
        taker_percent_fee_decimal=Decimal("0.00075"),
    )
}


class ParadisePerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="paradise_perpetual_testnet", client_data=None)
    paradise_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Paradise Perpetual Testnet API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    paradise_perpetual_testnet_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Paradise Perpetual Testnet secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "paradise_perpetual_testnet"


OTHER_DOMAINS_KEYS = {
    "paradise_perpetual_testnet": ParadisePerpetualTestnetConfigMap.construct()
}

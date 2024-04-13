from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USD"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.002"),
    taker_percent_fee_decimal=Decimal("0.002"),
    buy_percent_fee_deducted_from_returns=True
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("active") is True and exchange_info.get("futures") is False


class ParadiseConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="paradise", const=True, client_data=None)
    paradise_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Paradise API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    paradise_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Paradise API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "paradise"


KEYS = ParadiseConfigMap.construct()

OTHER_DOMAINS = ["paradise_testnet"]
OTHER_DOMAINS_PARAMETER = {"paradise_testnet": "paradise_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"paradise_testnet": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"paradise_testnet": DEFAULT_FEES}


class ParadiseTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="paradise_testnet", const=True, client_data=None)
    paradise_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Paradise Testnet API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    paradise_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Paradise Testnet API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "paradise_testnet"


OTHER_DOMAINS_KEYS = {"paradise_testnet": ParadiseTestnetConfigMap.construct()}

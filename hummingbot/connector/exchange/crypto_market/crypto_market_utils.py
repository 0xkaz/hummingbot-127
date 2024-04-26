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


class CryptoMarketConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="crypto_market", const=True, client_data=None)
    crypto_market_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your CryptoMarket API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    crypto_market_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your CryptoMarket API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "crypto_market"


KEYS = CryptoMarketConfigMap.construct()

OTHER_DOMAINS = ["crypto_market_testnet"]
OTHER_DOMAINS_PARAMETER = {"crypto_market_testnet": "crypto_market_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"crypto_market_testnet": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"crypto_market_testnet": DEFAULT_FEES}


class CryptoMarketTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="crypto_market_testnet", const=True, client_data=None)
    crypto_market_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your CryptoMarket Testnet API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    crypto_market_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your CryptoMarket Testnet API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "crypto_market_testnet"


OTHER_DOMAINS_KEYS = {"crypto_market_testnet": CryptoMarketTestnetConfigMap.construct()}

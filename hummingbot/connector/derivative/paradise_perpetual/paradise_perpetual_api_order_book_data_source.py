import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from hummingbot.connector.derivative.paradise_perpetual import (
    paradise_perpetual_constants as CONSTANTS,
    paradise_perpetual_utils,
    paradise_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book import OrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.paradise_perpetual.paradise_perpetual_derivative import ParadisePerpetualDerivative


class ParadisePerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'ParadisePerpetualDerivative',
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._nonce_provider = NonceCreator.for_microseconds()

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        funding_info_response = await self._request_complete_funding_info(trading_pair)
        general_info = funding_info_response[0][0]
        predicted_funding = funding_info_response[1][0]

        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(general_info["indexPrice"])),
            mark_price=Decimal(str(general_info["markPrice"])),
            next_funding_utc_timestamp=int(pd.Timestamp(general_info["fundingTime"]).timestamp()),
            rate=Decimal(str(predicted_funding["fundingRate"])),
        )
        return funding_info


    async def listen_for_subscriptions(self):
        """
        Subscribe to all required events and start the listening cycle.
        """
        tasks_future = None
        try:
            tasks = []            
            tasks.append(self._listen_for_subscriptions_on_url(
                url=CONSTANTS.WSS_URLS[self._domain],
                trading_pairs=self._trading_pairs))
            if tasks:
                tasks_future = asyncio.gather(*tasks)
                await tasks_future

        except asyncio.CancelledError:
            tasks_future and tasks_future.cancel()
            raise

    async def _listen_for_subscriptions_on_url(self, url: str, trading_pairs: List[str]):
        """
        Subscribe to all required events and start the listening cycle.
        :param url: the wss url to connect to
        :param trading_pairs: the trading pairs for which the function should listen events
        """

        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws = await self._get_connected_websocket_assistant(url)
                await self._subscribe_to_channels(ws, trading_pairs)
                await self._process_websocket_messages(ws)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    f"Unexpected error occurred when listening to order book streams {url}. Retrying in 5 seconds..."
                )
                await self._sleep(5.0)
            finally:
                ws and await ws.disconnect()

    async def _get_connected_websocket_assistant(self, ws_url: str) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=ws_url, message_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE
        )
        return ws
#NTI
    async def _subscribe_to_channels(self, ws: WSAssistant, trading_pairs: List[str]):
        try:
            symbols = [
                await self._connector.exchange_symbol_associated_to_pair(trading_pair=paradise_perpetual_utils.get_paradise_symbol(trading_pair))
                for trading_pair in trading_pairs
            ]
            symbols_str = "|".join(symbols)

            payload = {
                "op": "subscribe",
                "args": [f"{CONSTANTS.WS_TRADES_TOPIC}:{symbols_str}"],
            }
            subscribe_trade_request = WSJSONRequest(payload=payload)

            payload = {
                "op": "subscribe",
                "args": [f"{CONSTANTS.WS_ORDER_BOOK_EVENTS_TOPIC}:{symbols_str}"],
            }
            subscribe_orderbook_request = WSJSONRequest(payload=payload)

            payload = {
                "op": "subscribe",
                "args": [f"{CONSTANTS.WS_INSTRUMENTS_INFO_TOPIC}.{symbols_str}"],
            }
            subscribe_instruments_request = WSJSONRequest(payload=payload)

            await ws.send(subscribe_trade_request)  # not rate-limited
            await ws.send(subscribe_orderbook_request)  # not rate-limited
            await ws.send(subscribe_instruments_request)  # not rate-limited
            self.logger().info("Subscribed to public order book, trade and funding info channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    # async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
    #         """
    #         Listen for orderbook diffs using websocket book channel
    #         """
    #         while True:
    #             try:
    #                 ws: WSAssistant = await self._api_factory.get_ws_assistant()
    #                 await ws.connect(ws_url=CONSTANTS.WSS_OB_URLS[self._domain], ping_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE)
                    
    #                 diff_params = []                
    #                 for trading_pair in self._trading_pairs:
    #                     symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
    #                     paradise_symbol = paradise_perpetual_utils.get_paradise_symbol(symbol)
    #                     diff_params.append(f"update:{paradise_symbol}_0")  
    #                 payload = {
    #                     "op": "subscribe",
    #                     "args": diff_params,
    #                 }
    #                 subscribe_diff_request: WSJSONRequest = WSJSONRequest(payload=payload)                
    #                 await ws.send(subscribe_diff_request)
    #                 async for ws_response in ws.iter_messages():
    #                     msg = ws_response.data
    #                 with open('output.txt', 'w') as outputFile:
    #                     outputFile.write(str(msg))
    #                     await self._parse_order_book_diff_message(msg, output)
    #             except asyncio.CancelledError:
    #                 raise
    #             except Exception:
    #                 self.logger().network(
    #                     "Unexpected error with WebSocket connection.", exc_info=True,
    #                     app_warning_msg="Unexpected error with WebSocket connection. Retrying in 30 seconds. "
    #                                     "Check network connection.")
    #                 await self._sleep(30.0)
    #             finally:
    #                 await ws.disconnect()

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        while True:
            try:
                await super()._process_websocket_messages(websocket_assistant=websocket_assistant)
            except asyncio.TimeoutError:
                # ping_request = WSJSONRequest(payload={"op": "ping"})
                await websocket_assistant.send("ping")

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "success" not in event_message:
            event_channel = event_message["topic"]
            event_channel = ".".join(event_channel.split(":")[:-1])
            if event_channel == CONSTANTS.WS_TRADES_TOPIC:
                channel = self._trade_messages_queue_key
            elif event_channel == CONSTANTS.WS_ORDER_BOOK_EVENTS_TOPIC:
                channel = self._diff_messages_queue_key
            # elif event_channel == CONSTANTS.WS_INSTRUMENTS_INFO_TOPIC:
            #     channel = self._funding_info_messages_queue_key
        return channel

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        event_type = raw_message["data"]["type"]

        if event_type == "delta":
            symbol = raw_message["topic"].split(":")[-1]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
            timestamp_us = int(raw_message["data"]["timestamp"])
            update_id = self._nonce_provider.get_tracking_nonce(timestamp=timestamp_us * 1e-6)
            diffs_data = raw_message["data"]            
            order_book_message_content = {
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": diffs_data["bids"],
                "asks": diffs_data["asks"],
            }
            diff_message = OrderBookMessage(
                message_type=OrderBookMessageType.DIFF,
                content=order_book_message_content,
                timestamp=timestamp_us * 1e-6,
            )
            message_queue.put_nowait(diff_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trade_updates = raw_message["data"]

        for trade_data in trade_updates:
            symbol = trade_data["symbol"]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
            ts_ms = int(trade_data["timestamp"])
            trade_type = float(TradeType.SELL.value) if trade_data["side"] == "SELL" else float(TradeType.BUY.value)
            message_content = {
                "trade_id": trade_data["tradeId"],
                "trading_pair": trading_pair,
                "trade_type": trade_type,
                "amount": trade_data["size"],
                "price": trade_data["price"],
            }
            trade_message = OrderBookMessage(
                message_type=OrderBookMessageType.TRADE,
                content=message_content,
                timestamp=ts_ms * 1e-3,
            )
            message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass
    #     event_type = raw_message["type"]
    #     if event_type == "delta":
    #         symbol = raw_message["topic"].split(".")[-1]
    #         trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
    #         entries = raw_message["data"]["update"]
    #         for entry in entries:
    #             info_update = FundingInfoUpdate(trading_pair)
    #             if "index_price" in entry:
    #                 info_update.index_price = Decimal(str(entry["index_price"]))
    #             if "mark_price" in entry:
    #                 info_update.mark_price = Decimal(str(entry["mark_price"]))
    #             if "next_funding_time" in entry:
    #                 info_update.next_funding_utc_timestamp = int(
    #                     pd.Timestamp(str(entry["next_funding_time"]), tz="UTC").timestamp()
    #                 )
    #             if "predicted_funding_rate_e6" in entry:
    #                 info_update.rate = (
    #                     Decimal(str(entry["predicted_funding_rate_e6"])) * Decimal(1e-6)
    #                 )
    #             message_queue.put_nowait(info_update)

    async def _request_complete_funding_info(self, trading_pair: str):
        tasks = []
        params = {
            "symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        endpoint_info = CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT
        url_info = web_utils.get_rest_url_for_endpoint(endpoint=endpoint_info, trading_pair=trading_pair, domain=self._domain)
        limit_id = web_utils.get_rest_api_limit_id_for_endpoint(endpoint_info)
        tasks.append(rest_assistant.execute_request(
            url=url_info,
            throttler_limit_id=limit_id,
            params=params,
            method=RESTMethod.GET,
        ))
        endpoint_predicted = CONSTANTS.GET_PREDICTED_FUNDING_RATE_PATH_URL
        url_predicted = web_utils.get_rest_url_for_endpoint(endpoint=endpoint_predicted, trading_pair=trading_pair, domain=self._domain)
        limit_id_predicted = web_utils.get_rest_api_limit_id_for_endpoint(endpoint_predicted, trading_pair)
        tasks.append(rest_assistant.execute_request(
            url=url_predicted,
            throttler_limit_id=limit_id_predicted,
            params=params,
            method=RESTMethod.GET,
            is_auth_required=True
        ))

        responses = await asyncio.gather(*tasks)
        return responses

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_data = await self._request_order_book_snapshot(trading_pair)        
        timestamp = float(snapshot_data["timestamp"])
        update_id = self._nonce_provider.get_tracking_nonce(timestamp=timestamp)

        bids, asks = self._get_bids_and_asks_from_rest_msg_data(snapshot_data)
        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": bids,
            "asks": asks,
        }
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=order_book_message_content,
            timestamp=timestamp,
        )

        return snapshot_msg

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        params = {
            "symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        endpoint = CONSTANTS.ORDER_BOOK_ENDPOINT
        url = web_utils.get_rest_url_for_endpoint(endpoint=endpoint, trading_pair=trading_pair, domain=self._domain)
        limit_id = web_utils.get_rest_api_limit_id_for_endpoint(endpoint)
        data = await rest_assistant.execute_request(
            url=url,
            throttler_limit_id=limit_id,
            params=params,
            method=RESTMethod.GET,
        )

        return data

    @staticmethod
    def _get_bids_and_asks_from_rest_msg_data(snapshot: List[Dict[str, Any]]) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        """
        Rebase the snapshot JSON object to the standard like binance response

        :param snapshot: The snapshot is the response from snaptshot api of paradise

        :return: return standard JSON object
        """
        bids = []
        asks = []

        for item in snapshot["sellQuote"]:
            asks.append([item["price"], item["size"]])
        for item in snapshot["buyQuote"]:
            bids.append([item["price"], item["size"]])
        return bids, asks

    @staticmethod
    def _get_bids_and_asks_from_ws_msg_data(
        snapshot: Dict[str, List[Dict[str, Union[str, int, float]]]]
    ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        bids = []
        asks = []
        for action, rows_list in snapshot.items():
            if action not in ["delete", "update", "insert"]:
                continue
            is_delete = action == "delete"
            for row_dict in rows_list:
                row_price = row_dict["price"]
                row_size = 0.0 if is_delete else row_dict["size"]
                row_tuple = (row_price, row_size)
                if row_dict["side"] == "Buy":
                    bids.append(row_tuple)
                else:
                    asks.append(row_tuple)
        return bids, asks

    async def _connected_websocket_assistant(self) -> WSAssistant:
        pass  # unused

    async def _subscribe_channels(self, ws: WSAssistant):
        pass  # unused

import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import pandas as pd
from bidict import bidict

import hummingbot.connector.derivative.paradise_perpetual.paradise_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.paradise_perpetual.paradise_perpetual_utils as paradise_utils
from hummingbot.connector.derivative.paradise_perpetual import paradise_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.paradise_perpetual.paradise_perpetual_api_order_book_data_source import (
    ParadisePerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.paradise_perpetual.paradise_perpetual_auth import ParadisePerpetualAuth
from hummingbot.connector.derivative.paradise_perpetual.paradise_perpetual_user_stream_data_source import (
    ParadisePerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


class ParadisePerpetualDerivative(PerpetualDerivativePyBase):

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        paradise_perpetual_api_key: str = None,
        paradise_perpetual_secret_key: str = None,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):

        self.paradise_perpetual_api_key = paradise_perpetual_api_key
        self.paradise_perpetual_secret_key = paradise_perpetual_secret_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._last_trade_history_timestamp = None

        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> ParadisePerpetualAuth:
        return ParadisePerpetualAuth(self.paradise_perpetual_api_key, self.paradise_perpetual_secret_key)

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return web_utils.build_rate_limits(self.trading_pairs)

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.QUERY_SYMBOL_ENDPOINT

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.QUERY_SYMBOL_ENDPOINT

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.SERVER_TIME_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        return 120

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def start(self, clock: Clock, timestamp: float):
        super().start(clock, timestamp)
        if self._domain == CONSTANTS.DEFAULT_DOMAIN and self.is_trading_required:
            self.set_position_mode(PositionMode.HEDGE)

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        ts_error_target_str = self._format_ret_code_for_print(ret_code=CONSTANTS.RET_CODE_AUTH_TIMESTAMP_ERROR)
        param_error_target_str = (
            f"{self._format_ret_code_for_print(ret_code=CONSTANTS.RET_CODE_PARAMS_ERROR)} - invalid timestamp"
        )
        is_time_synchronizer_related = (
            ts_error_target_str in error_description
            or param_error_target_str in error_description
        )
        return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        # TODO: implement this method correctly for the connector
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_lost_order_removed_if_not_found_during_order_status_update
        # when replacing the dummy implementation
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        # TODO: implement this method correctly for the connector
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_cancel_order_not_found_in_the_exchange when replacing the
        # dummy implementation
        return False

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        # data = {"symbol": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair)}
        data = {"symbol": paradise_utils.get_paradise_symbol(tracked_order.trading_pair)}
        if tracked_order.exchange_order_id:
            data["orderID"] = tracked_order.exchange_order_id
        else:
            data["clOrderID"] = tracked_order.client_order_id
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL,
            data=data,
            is_auth_required=True,
            trading_pair=tracked_order.trading_pair,
        )
        response_code = cancel_result["status"]

        if response_code != CONSTANTS.RET_CODE_OK:
            if response_code == CONSTANTS.RET_CODE_ORDER_NOT_EXISTS:
                await self._order_tracker.process_order_not_found(order_id)
            formatted_ret_code = self._format_ret_code_for_print(response_code)
            raise IOError(f"{formatted_ret_code}")

        return True

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction = PositionAction.NIL,
        **kwargs,
    ) -> Tuple[str, float]:        
        position_idx = self._get_position_idx(trade_type, position_action)
        data = {
            "side": "BUY" if trade_type == TradeType.BUY else "SELL",
            # "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
            "symbol": paradise_utils.get_paradise_symbol(trading_pair),
            "size": float(amount),
            "time_in_force": CONSTANTS.DEFAULT_TIME_IN_FORCE,            
            "clOrderID": order_id,
            "reduceOnly": position_action == PositionAction.CLOSE,
            "positionMode": position_idx,
            "type": CONSTANTS.ORDER_TYPE_MAP[order_type],
        }
        if order_type.is_limit_type():
            data["price"] = float(price)

        resp = await self._api_post(
            path_url=CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL,
            data=data,
            is_auth_required=True,
            trading_pair=trading_pair,
            headers={"referer": CONSTANTS.HBOT_BROKER_ID},
            **kwargs,
        )        

        if resp["status"] != CONSTANTS.RET_CODE_OK:
            formatted_ret_code = self._format_ret_code_for_print(resp['status'])
            raise IOError(f"Error submitting order {order_id}: {formatted_ret_code}")

        return str(resp[0]["orderID"]), self.current_timestamp

    def _get_position_idx(self, trade_type: TradeType, position_action: PositionAction) -> int:
        if position_action == PositionAction.NIL:
            raise NotImplementedError
        if self.position_mode == PositionMode.ONEWAY:
            position_idx = CONSTANTS.POSITION_IDX_ONEWAY
        elif trade_type == TradeType.BUY:
            if position_action == PositionAction.CLOSE:
                position_idx = CONSTANTS.POSITION_IDX_HEDGE_SELL
            else:  # position_action == PositionAction.Open
                position_idx = CONSTANTS.POSITION_IDX_HEDGE_BUY
        elif trade_type == TradeType.SELL:
            if position_action == PositionAction.CLOSE:
                position_idx = CONSTANTS.POSITION_IDX_HEDGE_BUY
            else:  # position_action == PositionAction.Open
                position_idx = CONSTANTS.POSITION_IDX_HEDGE_SELL
        else:  # trade_type == TradeType.RANGE
            raise NotImplementedError

        return position_idx

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = is_maker or False
        fee = build_trade_fee(
            self.name,
            is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )
        return fee

    async def _update_trading_fees(self):
        pass

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return ParadisePerpetualAPIOrderBookDataSource(
            self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return ParadisePerpetualUserStreamDataSource(
            auth=self._auth,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_trade_history(),
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _update_trade_history(self):
        """
        Calls REST API to get trade history (order fills)
        """

        trade_history_tasks = []

        for trading_pair in self._trading_pairs:
            # exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=paradise_utils.get_paradise_symbol(trading_pair))
            exchange_symbol = paradise_utils.get_paradise_symbol(trading_pair)
            body_params = {
                "symbol": exchange_symbol,
                "count": 200,
            }
            if self._last_trade_history_timestamp:
                body_params["startTime"] = int(int(self._last_trade_history_timestamp) * 1e3)

            trade_history_tasks.append(
                asyncio.create_task(self._api_get(
                    path_url=CONSTANTS.USER_TRADE_RECORDS_PATH_URL,
                    params=body_params,
                    is_auth_required=True,
                    trading_pair=trading_pair,
                ))
            )

        raw_responses: List[Dict[str, Any]] = await safe_gather(*trade_history_tasks, return_exceptions=True)        

        # Initial parsing of responses. Joining all the responses
        parsed_history_resps: List[Dict[str, Any]] = []
        for trading_pair, resp in zip(self._trading_pairs, raw_responses):            
            if len(resp) > 0:
                if not isinstance(resp, Exception) and len(resp) > 0:
                    self._last_trade_history_timestamp = float(resp["timestamp"])
                    # log_required
                    trade_entries = resp
                    if trade_entries:
                        parsed_history_resps.extend(trade_entries)
                else:
                    self.logger().network(
                        f"Error fetching status update for {trading_pair}: {resp}.",
                        app_warning_msg=f"Failed to fetch status update for {trading_pair}."
                    )

        # Trade updates must be handled before any order status updates.
        if len(parsed_history_resps)>0:
            for trade in parsed_history_resps:
                self._process_trade_event_message(trade)

    async def _update_order_status(self):
        """
        Calls REST API to get order status
        """

        active_orders: List[InFlightOrder] = list(self.in_flight_orders.values())

        tasks = []
        for active_order in active_orders:
            tasks.append(asyncio.create_task(self._request_order_status_data(tracked_order=active_order)))
        #log_required
        raw_responses: List[Dict[str, Any]] = await safe_gather(*tasks, return_exceptions=True)

        # Initial parsing of responses. Removes Exceptions.
        parsed_status_responses: List[Dict[str, Any]] = []
        for resp, active_order in zip(raw_responses, active_orders):
            if not isinstance(resp, Exception):
                parsed_status_responses.append(resp[0])
            else:
                self.logger().network(
                    f"Error fetching status update for the order {active_order.client_order_id}: {resp}.",
                    app_warning_msg=f"Failed to fetch status update for the order {active_order.client_order_id}."
                )
                await self._order_tracker.process_order_not_found(active_order.client_order_id)
        if len(parsed_status_responses)>0:
            for order_status in parsed_status_responses:
                self._process_order_event_message(order_status)

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances
        """
        wallet_balance: Dict[str, Dict[str, Any]] = await self._api_get(
            path_url=CONSTANTS.GET_WALLET_BALANCE_PATH_URL,
            params={"wallet": "CROSS@"},
            is_auth_required=True,
        )

        # if wallet_balance["status"] != CONSTANTS.RET_CODE_OK:
        #     formatted_ret_code = self._format_ret_code_for_print(wallet_balance['ret_code'])
        #     raise IOError(f"{formatted_ret_code} - {wallet_balance['ret_msg']}")

        self._account_available_balances.clear()
        self._account_balances.clear()

        if wallet_balance[0] is not None:
            for balance_json in wallet_balance[0]["assets"]:
                self._account_balances[balance_json["currency"]] = Decimal(str(balance_json["balance"]))
                self._account_available_balances[balance_json["currency"]] = Decimal(str(wallet_balance[0]["availableBalance"]))

    async def _update_positions(self):
        """
        Retrieves all positions using the REST API.
        """
        position_tasks = []

        for trading_pair in self._trading_pairs:
            # ex_trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair)
            ex_trading_pair = paradise_utils.get_paradise_symbol(trading_pair)
            body_params = {"symbol": ex_trading_pair}
            position_tasks.append(
                asyncio.create_task(self._api_get(
                    path_url=CONSTANTS.GET_POSITIONS_PATH_URL,
                    # params=body_params,
                    is_auth_required=True,
                    trading_pair=trading_pair,
                ))
            )

        raw_responses: List[Dict[str, Any]] = await safe_gather(*position_tasks, return_exceptions=True)
        #log_required        
        # Initial parsing of responses. Joining all the responses
        parsed_resps: List[Dict[str, Any]] = []
        for resp, trading_pair in zip(raw_responses, self._trading_pairs):
            if not isinstance(resp, Exception):
                result = resp
                if result:
                    position_entries = result if isinstance(result, list) else [result]
                    parsed_resps.extend(position_entries)
            else:
                self.logger().error(f"Error fetching positions for {trading_pair}. Response: {resp}")

        for position in parsed_resps:
            data = position
            ex_trading_pair = data.get("symbol")
            hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(ex_trading_pair)
            position_side = PositionSide.LONG if data["side"] == "BUY" else PositionSide.SHORT
            unrealized_pnl = Decimal(str(data["unrealizedProfitLoss"]))
            entry_price = Decimal(str(data["entryPrice"]))
            amount = Decimal(str(data["size"]))
            leverage = Decimal(str(data["currentLeverage"]))
            pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)
            if amount != s_decimal_0:
                position = Position(
                    trading_pair=hb_trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount * (Decimal("-1.0") if position_side == PositionSide.SHORT else Decimal("1.0")),
                    leverage=leverage,
                )
                self._perpetual_trading.set_position(pos_key, position)
            else:
                self._perpetual_trading.remove_position(pos_key)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            try:
                all_fills_response = await self._request_order_fills(order=order)
                #log_required
                fills_data = all_fills_response

                if fills_data is not None:
                    for fill_data in fills_data:
                        trade_update = self._parse_trade_update(trade_msg=fill_data, tracked_order=order)
                        trade_updates.append(trade_update)
            except IOError as ex:
                if not self._is_request_exception_related_to_time_synchronizer(request_exception=ex):
                    raise

        return trade_updates

    async def _request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:
        # exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
        exchange_symbol = paradise_utils.get_paradise_symbol(order.trading_pair)
        body_params = {
            "orderID": order.exchange_order_id,
            "symbol": exchange_symbol,
        }
        res = await self._api_get(
            path_url=CONSTANTS.USER_TRADE_RECORDS_PATH_URL,
            params=body_params,
            is_auth_required=True,
            trading_pair=order.trading_pair,
        )
        return res

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        try:
            order_status_data = await self._request_order_status_data(tracked_order=tracked_order)
            order_msg = order_status_data
            client_order_id = str(order_msg["clOrderID"])

            order_update: OrderUpdate = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=CONSTANTS.ORDER_STATE[order_msg["status"]],
                client_order_id=client_order_id,
                exchange_order_id=order_msg["orderID"],
            )

            return order_update

        except IOError as ex:
            if self._is_request_exception_related_to_time_synchronizer(request_exception=ex):
                order_update = OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=tracked_order.current_state,
                )
            else:
                raise

        return order_update

    async def _request_order_status_data(self, tracked_order: InFlightOrder) -> Dict:
        # exchange_symbol = await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair)
        exchange_symbol = paradise_utils.get_paradise_symbol(tracked_order.trading_pair)
        query_params = {
            "symbol": exchange_symbol,
            "clOrderID": tracked_order.client_order_id
        }
        if tracked_order.exchange_order_id is not None:
            query_params["orderID"] = tracked_order.exchange_order_id

        resp = await self._api_get(
            path_url=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL,
            params=query_params,
            is_auth_required=True,
            trading_pair=tracked_order.trading_pair,
        )

        return resp

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                pass
                endpoint = web_utils.endpoint_from_message(event_message)
                payload = web_utils.payload_from_message(event_message)                
                # if endpoint == CONSTANTS.WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME:
                #     for position_msg in payload:
                #         await self._process_account_position_event(position_msg)
                # elif endpoint == CONSTANTS.WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME:
                #     for order_msg in payload:
                #         self._process_order_event_message(order_msg)
                # elif endpoint == CONSTANTS.WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME:
                #     for trade_msg in payload:
                #         self._process_trade_event_message(trade_msg)
                # elif endpoint == CONSTANTS.WS_SUBSCRIPTION_WALLET_ENDPOINT_NAME:
                #     for wallet_msg in payload:
                #         self._process_wallet_event_message(wallet_msg)
                # elif endpoint is None:
                #     self.logger().error(f"Could not extract endpoint from {event_message}.")
                    # raise ValueError
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    async def _process_account_position_event(self, position_msg: Dict[str, Any]):
        """
        Updates position
        :param position_msg: The position event message payload
        """        
        ex_trading_pair = str(position_msg["marketName"]).split("-")[0]
        trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=ex_trading_pair)
        position_side = PositionSide.SHORT if position_msg["orderModeName"] == "MODE_SELL" else PositionSide.LONG
        position_value = Decimal(str(position_msg["totalValue"]))
        entry_price = Decimal(str(position_msg["entryPrice"]))
        amount = Decimal(str(position_msg["originalAmount"]))
        leverage = Decimal(str(position_msg["currentLeverage"]))
        unrealized_pnl = position_value - (amount * entry_price * leverage)
        pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
        if amount != s_decimal_0:
            position = Position(
                trading_pair=trading_pair,
                position_side=position_side,
                unrealized_pnl=unrealized_pnl,
                entry_price=entry_price,
                amount=amount * (Decimal("-1.0") if position_side == PositionSide.SHORT else Decimal("1.0")),
                leverage=leverage,
            )
            self._perpetual_trading.set_position(pos_key, position)
        else:
            self._perpetual_trading.remove_position(pos_key)

        # Trigger balance update because Paradise doesn't have balance updates through the websocket
        safe_ensure_future(self._update_balances())

    def _process_trade_event_message(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        :param trade_msg: The trade event message payload
        """

        client_order_id = str(trade_msg["clOrderID"])
        fillable_order = self._order_tracker.all_fillable_orders.get(client_order_id)

        if fillable_order is not None:
            trade_update = self._parse_trade_update(trade_msg=trade_msg, tracked_order=fillable_order)
            self._order_tracker.process_trade_update(trade_update)

    def _parse_trade_update(self, trade_msg: Dict, tracked_order: InFlightOrder) -> TradeUpdate:
        trade_id: str = str(trade_msg["serialId"])

        fee_asset = tracked_order.quote_asset
        fee_amount = Decimal(trade_msg["feeAmount"])
        position_side = trade_msg["side"]
        position_action = (PositionAction.OPEN
                           if (tracked_order.trade_type is TradeType.BUY and position_side == "BUY"
                               or tracked_order.trade_type is TradeType.SELL and position_side == "SELL")
                           else PositionAction.CLOSE)

        flat_fees = [] if fee_amount == Decimal("0") else [TokenAmount(amount=fee_amount, token=fee_asset)]

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent_token=fee_asset,
            flat_fees=flat_fees,
        )

        exec_price = Decimal(trade_msg["triggerPrice"]) if "triggerPrice" in trade_msg else Decimal(trade_msg["price"])
        exec_time = trade_msg["timestamp"]

        trade_update: TradeUpdate = TradeUpdate(
            trade_id=trade_id,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(trade_msg["orderId"]),
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=exec_time,
            fill_price=exec_price,
            fill_base_amount=Decimal(trade_msg["filledSize"]),
            fill_quote_amount=exec_price * Decimal(trade_msg["filledSize"]),
            fee=fee,
        )

        return trade_update

    def _process_order_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order event message payload
        """
        order_status = CONSTANTS.ORDER_STATE[order_msg["status"]]
        client_order_id = str(order_msg["clOrderID"])
        updatable_order = self._order_tracker.all_updatable_orders.get(client_order_id)

        if updatable_order is not None:
            new_order_update: OrderUpdate = OrderUpdate(
                trading_pair=updatable_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=order_status,
                client_order_id=client_order_id,
                exchange_order_id=order_msg["orderID"],
            )
            self._order_tracker.process_order_update(new_order_update)

    def _process_wallet_event_message(self, wallet_msg: Dict[str, Any]):
        """
        Updates account balances.
        :param wallet_msg: The account balance update message payload
        """
        if "coin" in wallet_msg:  # non-linear
            symbol = wallet_msg["coin"]
        else:  # linear
            symbol = "USDT"
        self._account_balances[symbol] = Decimal(str(wallet_msg["wallet_balance"]))
        self._account_available_balances[symbol] = Decimal(str(wallet_msg["available_balance"]))

    async def _format_trading_rules(self, instrument_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Converts JSON API response into a local dictionary of trading rules.
        :param instrument_info_dict: The JSON API response.
        :returns: A dictionary of trading pair to its respective TradingRule.
        """
        trading_rules = {}
        symbol_map = await self.trading_pair_symbol_map()
        for instrument in instrument_info_dict:
            try:
                exchange_symbol = instrument["symbol"]
                if exchange_symbol in symbol_map:
                    trading_pair = combine_to_hb_trading_pair(instrument['base'], instrument['quote'])
                    trading_rules[trading_pair] = TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=Decimal(str(instrument["minOrderSize"])),
                        max_order_size=Decimal(str(instrument["maxOrderSize"])),
                        min_price_increment=Decimal(str(instrument["minPriceIncrement"])),
                        min_base_amount_increment=Decimal(str(instrument["minSizeIncrement"])),
                        buy_order_collateral_token=instrument['quote'],
                        sell_order_collateral_token=instrument['base'],
                    )
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule: {instrument}. Skipping...")
        return list(trading_rules.values())

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(paradise_utils.is_exchange_information_valid, exchange_info):
            exchange_symbol = symbol_data["symbol"]
            base = symbol_data["base"]
            quote = symbol_data["quote"]
            trading_pair = combine_to_hb_trading_pair(base, quote)
            if trading_pair in mapping.inverse:
                self._resolve_trading_pair_symbols_duplicate(mapping, exchange_symbol, base, quote)
            else:
                mapping[exchange_symbol] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    def _resolve_trading_pair_symbols_duplicate(self, mapping: bidict, new_exchange_symbol: str, base: str, quote: str):
        """Resolves name conflicts provoked by futures contracts.

        If the expected BASEQUOTE combination matches one of the exchange symbols, it is the one taken, otherwise,
        the trading pair is removed from the map and an error is logged.
        """
        expected_exchange_symbol = f"{base}{quote}"
        trading_pair = combine_to_hb_trading_pair(base, quote)
        current_exchange_symbol = mapping.inverse[trading_pair]
        if current_exchange_symbol == expected_exchange_symbol:
            pass
        elif new_exchange_symbol == expected_exchange_symbol:
            mapping.pop(current_exchange_symbol)
            mapping[new_exchange_symbol] = trading_pair
        else:
            self.logger().error(f"Could not resolve the exchange symbols {new_exchange_symbol} and {current_exchange_symbol}")
            mapping.pop(current_exchange_symbol)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        # exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        exchange_symbol = paradise_utils.get_paradise_symbol(trading_pair)
        params = {"symbol": exchange_symbol}

        resp_json = await self._api_get(
            path_url=CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT,
            params=params,
        )

        price = float(resp_json[0]["lastPrice"])
        return price

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        msg = ""
        success = True

        api_mode = CONSTANTS.POSITION_MODE_MAP[mode]

        # exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=paradise_utils.get_paradise_symbol(trading_pair))
        exchange_symbol = paradise_utils.get_paradise_symbol(trading_pair)
        data = {"symbol": exchange_symbol, "mode": api_mode}

        response = await self._api_post(
            path_url=CONSTANTS.SET_POSITION_MODE_URL,
            data=data,
            is_auth_required=True,
        )

        response_code = response["status"]

        if response_code not in [CONSTANTS.RET_CODE_OK, CONSTANTS.RET_CODE_MODE_NOT_MODIFIED]:
            formatted_ret_code = self._format_ret_code_for_print(response_code)
            msg = f"{formatted_ret_code} - {response['message']}"
            success = False
        return success, msg

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        # exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        exchange_symbol = paradise_utils.get_paradise_symbol(trading_pair)

        data = {
            "symbol": exchange_symbol,
            "leverage": leverage
        }

        resp: Dict[str, Any] = await self._api_post(
            path_url=CONSTANTS.SET_LEVERAGE_PATH_URL,
            data=data,
            is_auth_required=True,
            trading_pair=trading_pair,
        )

        success = False
        msg = ""
        if resp["status"] == CONSTANTS.RET_CODE_OK or resp["status"] == CONSTANTS.RET_CODE_LEVERAGE_UNDERGOING_LIQUIDATION:
            success = True
        else:
            formatted_ret_code = self._format_ret_code_for_print(resp['status'])
            msg = f"{formatted_ret_code} - {resp['message']}"

        return success, msg

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:        
        # exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)        
        exchange_symbol = paradise_utils.get_paradise_symbol(trading_pair)
        params = {
            "symbol": exchange_symbol,
            "listFullAttributes": 'true'
        }
        raw_response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL,
            params=params,
            is_auth_required=True,
            trading_pair=trading_pair,
        )
        data: Dict[str, Any] = raw_response[0]
        if not data:
            # An empty funding fee/payment is retrieved.
            timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")
        else:
            funding_rate: Decimal = Decimal(str(data["fundingRate"]))
            position_size: Decimal = Decimal(str(data["contractSize"]))
            payment: Decimal = funding_rate * position_size            
            timestamp: int = int(pd.Timestamp(data["fundingTime"], tz="UTC").timestamp())

        return timestamp, funding_rate, payment

    async def _api_request(self,
                           path_url,
                           method: RESTMethod = RESTMethod.GET,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           return_err: bool = False,
                           limit_id: Optional[str] = None,
                           trading_pair: Optional[str] = None,
                           **kwargs) -> Dict[str, Any]:

        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        if limit_id is None:
            limit_id = web_utils.get_rest_api_limit_id_for_endpoint(
                endpoint=path_url,
                trading_pair=trading_pair,
            )
        url = web_utils.get_rest_url_for_endpoint(endpoint=path_url, trading_pair=trading_pair, domain=self._domain)

        resp = await rest_assistant.execute_request(
            url=url,
            params=params,
            data=data,
            method=method,
            is_auth_required=is_auth_required,
            return_err=return_err,
            throttler_limit_id=limit_id if limit_id else path_url,
        )
        return resp

    @staticmethod
    def _format_ret_code_for_print(ret_code: Union[str, int]) -> str:
        return f"ret_code <{ret_code}>"

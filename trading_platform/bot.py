from binance.client import Client
from typing import Callable
import pandas as pd
from enum import Enum
from time import sleep
from dataclasses import dataclass
from typing import Optional
import json


BOT_STATUS_WAITING_FOR_SIGNAL = "WAITING_FOR_SIGNAL"
BOT_STATUS_ORDER_PLACED = "ORDER_PLACED"
BOT_STATUS_TIMEOUT = "TIMEOUT"

ORDER_SIDE_BUY = "BUY"
ORDER_SIDE_SELL = "SELL"


@dataclass
class Position:
    entry_price: float
    side: str
    order_id: str
    quantity: float
    sl_price: Optional[float] = None
    sl_order_id: Optional[str] = None
    tp_price: Optional[float] = None
    tp_order_id: Optional[str] = None
    closed: bool = False
    success: bool = False

class TradingBot:

    def __init__(self, api_key: str, api_secret: str, symbol: str, qty: float, check_signal: Callable[[pd.DataFrame], str], after_success: Callable[[Position], None], after_failure: Callable[[Position], None], polling_seconds=60, testnet=True, backup_file: str = None, window_size: int = 50, interval: str = '15m', sl_diff: float = 0.01, tp_diff: float = 0.02, timeout_minutes: int = 0):
        self.last_position_time = None
        self.backup_file = backup_file
        self.polling_seconds = polling_seconds
        self.client = Client(api_key, api_secret, testnet=testnet)
        self.symbol = symbol
        self.check_signal = check_signal
        self.backup_file = backup_file
        self.window_size = window_size
        self.qty = qty
        self.interval = interval
        self.sl_diff = sl_diff
        self.tp_diff = tp_diff
        self.after_success = after_success
        self.after_failure = after_failure
        self.timeout = timeout_minutes * 60  # Convert minutes to seconds
        print(f"Bot for {symbol} trading initialized successfully. Waiting for first signal...")
        self.status = BOT_STATUS_WAITING_FOR_SIGNAL

        self.load_backup()
        

    def start(self):
        while True:
            if self.status == BOT_STATUS_WAITING_FOR_SIGNAL:
                self.wait_for_signal()
            elif self.status == BOT_STATUS_ORDER_PLACED:
                self.check_order_status()
            elif self.status == BOT_STATUS_TIMEOUT:
                self.check_timeout_passed()
            self.save_backup()
            sleep(self.polling_seconds)


    def wait_for_signal(self):
        print("Checking for trading signal...")
        signal = self.check_signal(self.get_market_data())

        if signal=='BUY':
            print("Buy signal detected. Placing order...")
            self.create_position(ORDER_SIDE_BUY)
        elif signal=='SELL':
            print("Sell signal detected. Placing order...")
            self.create_position(ORDER_SIDE_SELL)

    def get_market_data(self):
        client = Client()
        klines = client.get_klines(symbol=self.symbol, interval=self.interval, limit=self.window_size)

        df_klines = pd.DataFrame(klines, columns=[
            'Open time', 'Open', 'High', 'Low', 'Close', 'Volume',
            'Close time', 'Quote asset volume', 'Number of trades',
            'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'
        ])

        df_klines['Open time'] = pd.to_datetime(df_klines['Open time'], unit='ms')
        df_klines.set_index('Open time', inplace=True)
        df_klines[['Open', 'High', 'Low', 'Close', 'Volume']] = df_klines[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
        return df_klines
    
    def create_position(self, side: str):
        SL_value = 1 - self.sl_diff if side == ORDER_SIDE_BUY else 1 + self.sl_diff
        TP_value = 1 + self.tp_diff if side == ORDER_SIDE_BUY else self.tp_diff
        limit_order_side = ORDER_SIDE_SELL if side == ORDER_SIDE_BUY else ORDER_SIDE_BUY

        pos_order = self.client.futures_create_order(symbol=self.symbol, side=side, type='MARKET', quantity=self.qty)
        mark_price = float(self.client.futures_mark_price(symbol=self.symbol)["markPrice"])

        sl_order = self.client.futures_create_order(symbol=self.symbol,side=limit_order_side, type="STOP_MARKET", stopPrice=round(SL_value * mark_price, 2), closePosition=True, timeInForce='GTC', workingType="MARK_PRICE")
        tp_order = self.client.futures_create_order(symbol=self.symbol, side=limit_order_side, type="TAKE_PROFIT_MARKET", stopPrice=round(TP_value * mark_price, 2), closePosition=True, timeInForce='GTC', workingType="MARK_PRICE")

        self.position = Position(
            entry_price=mark_price,
            side=side,
            order_id=pos_order['orderId'],
            quantity=self.qty,
            sl_price=round(SL_value * mark_price, 2),
            sl_order_id=sl_order['orderId'],
            tp_price=round(TP_value * mark_price, 2),
            tp_order_id=tp_order['orderId']
        )

        self.status = BOT_STATUS_ORDER_PLACED


    def check_order_status(self):
        sl_order = self.client.futures_get_order(symbol=self.symbol, orderId=self.position.sl_order_id)
        tp_order = self.client.futures_get_order(symbol=self.symbol, orderId=self.position.tp_order_id)

        if sl_order['status'] == 'FILLED' or tp_order['status'] == 'FILLED':
            self.position.closed = True
            if tp_order['status'] == 'FILLED':
                self.position.success = True
                self.after_success(self.position)
                self.client.futures_cancel_order(orderId=self.position.sl_order_id, symbol=self.symbol)
            else:
                self.position.success = False
                self.after_failure(self.position)
                self.client.futures_cancel_order(orderId=self.position.tp_order_id, symbol=self.symbol)

            self.status = BOT_STATUS_TIMEOUT
            self.last_position_time = pd.Timestamp.now()

    def check_timeout_passed(self):
        if pd.Timestamp.now() - self.last_position_time > pd.Timedelta(seconds=self.timeout):
            self.status = BOT_STATUS_WAITING_FOR_SIGNAL
            self.position = None

    def save_backup(self):
        if self.backup_file:

            last_position_time = self.last_position_time.isoformat() if self.last_position_time is not None else None

            state = {
                'status': self.status,
                'symbol': self.symbol,
                'position': None,
                'last_position_time': last_position_time
            }

            if self.position:
                pos_dict = self.position.__dict__.copy()
                state['position'] = pos_dict

            with open(self.backup_file, 'w') as file:
                json.dump(state, file, indent=4)
        else:
            print("No backup file specified. Skipping backup.")

    def load_backup(self):
        if self.backup_file:
            try:
                with open(self.backup_file, 'r') as file:
                    state = json.load(file)
                    self.status = state['status']
                    self.symbol = state['symbol']
                    if state['position']:
                        self.position = Position(**state['position'])
                    else:
                        self.position = None
                    if 'last_position_time' in state and state['last_position_time']:
                        self.last_position_time = pd.Timestamp(state['last_position_time'])
                    else:
                        self.last_position_time = None
                print("Backup loaded successfully.")
            except FileNotFoundError:
                print("Backup file not found. Starting fresh.")
            except json.JSONDecodeError:
                print("Error decoding backup file. Starting fresh.")
        else:
            print("No backup file specified. Skipping load.")

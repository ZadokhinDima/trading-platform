from binance.client import Client
from typing import Callable
import pandas as pd
from enum import Enum
from time import sleep

class TradingBot:

    def __init__(self, api_key: str, api_secret: str, symbol: str, check_signal: Callable[[pd.DataFrame], str], polling_seconds=60, testnet=True, backup_file: str = None):
        
        self.polling_seconds = polling_seconds
        self.client = Client(api_key, api_secret, testnet=testnet)
        self.symbol = symbol
        self.check_signal = check_signal
        self.backup_file = backup_file
        print(f"Bot for {symbol} trading initialized successfully. Waiting for first signal...")
        self.status = BotStatus.WAITING_FOR_SIGNAL
        

    def start(self):
        while True:
            if self.status == BotStatus.WAITING_FOR_SIGNAL:
                self.wait_for_signal()
            elif self.status == BotStatus.ORDER_PLACED:
                self.check_order_status()
            elif self.status == BotStatus.TIMEOUT:
                self.check_timeout_passed()

            sleep(self.polling_seconds)


    def wait_for_signal(self):
        print("Checking for trading signal...")
        signal = self.check_signal(self.get_market_data())

        if signal=='BUY':
            print("Buy signal detected. Placing order...")
            self.place_order(OrderSide.BUY)
        elif signal=='SELL':
            print("Sell signal detected. Placing order...")
            self.place_order(OrderSide.SELL)


    def check_order_status(self):
        print("Checking order status...")
        # Logic to check the status of an order
        # This could involve querying an API or checking a database

    def check_timeout_passed(self):
        print("Checking if timeout has passed...")
        # Logic to check if a timeout has passed
        # This could involve comparing timestamps or checking a timer


class BotStatus(Enum):
    WAITING_FOR_SIGNAL = "WAITING_FOR_SIGNAL"
    ORDER_PLACED = "ORDER_PLACED"
    TIMEOUT = "TIMEOUT"

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

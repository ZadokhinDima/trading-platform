from trading_platform.bot import TradingBot
from dotenv import load_dotenv
import os

load_dotenv()

def check_signal(data):
    # Placeholder for signal checking logic
    return "BUY"  # or "SELL" based on your strategy

bot = TradingBot(
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET"),
    symbol="BTCUSDT",
    qty=0.001,
    check_signal=check_signal,
    after_success=lambda pos: print(f"Position {pos.order_id} closed successfully."),
    after_failure=lambda pos: print(f"Position {pos.order_id} closed with failure."),
    polling_seconds=60,
    testnet=True,
    backup_file="backup.json",
    window_size=50,
    interval='15m',
    sl_diff=0.0005,
    tp_diff=0.0008,
    timeout_minutes=0
)

bot.start()
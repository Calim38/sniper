import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Configurações de logging
LOG_LEVEL = logging.DEBUG
LOG_FILE = 'trading_log.log'
POSITIONS_FILE = 'positions.json'
CLOSED_POSITIONS_FILE = 'closed_positions.json'
CYCLE_DELAY_SECONDS = 60
TESTNET_MODE = True
BASE_URL = 'https://api.binance.com/api/v3'
TESTNET_BASE_URL = 'https://testnet.binance.vision'
KLINE_INTERVAL = '30m'
KLINE_LIMIT = 1000
MAX_OPEN_POSITIONS = 20
MIN_TRADE_AMOUNT_USDT = 10
TRADE_AMOUNT_USDT = 100

# Parâmetros da estratégia
SMA_FAST_PERIOD = 5
SMA_SLOW_PERIOD = 10
RSI_PERIOD = 14
OVERBOUGHT_RSI = 80
OVERSOLD_RSI = 40
TRADE_AMOUNT_PERCENTAGE = 0.1
STOP_LOSS_PERCENT = 0.05
TAKE_PROFIT_PERCENT = 0.1
TRAILING_STOP_PERCENT = 0.05

# Outras configurações
BACKTEST_START_DATE = '2020-01-01'
BACKTEST_END_DATE = '2022-12-31'
DATA_SOURCE = 'yahoo'

# Configurações da API
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
import pandas as pd
import logging
from datetime import datetime
import settings

# Configurações do logger
logger = logging.getLogger(__name__)

class TradingStrategy:
    def __init__(self):
        # Parâmetros da estratégia
        self.sma_fast_period = settings.SMA_FAST_PERIOD
        self.sma_slow_period = settings.SMA_SLOW_PERIOD
        self.rsi_period = settings.RSI_PERIOD
        self.overbought_rsi = settings.OVERBOUGHT_RSI
        self.oversold_rsi = settings.OVERSOLD_RSI
        self.trade_amount_percentage = settings.TRADE_AMOUNT_PERCENTAGE
        self.stop_loss_percent = settings.STOP_LOSS_PERCENT
        self.take_profit_percent = settings.TAKE_PROFIT_PERCENT
        self.trailing_stop_percent = settings.TRAILING_STOP_PERCENT  # Novo parâmetro para trailing stop

        # Estado da estratégia (poderia ser mais complexo para múltiplos ativos)
        self.in_position = False
        self.position_data = {}  # Armazena dados da posição se estiver aberta

        logging.info("Estratégia de Trading inicializada.")

    def _calculate_smas(self, data):
        """Calcula as Médias Móveis Simples (SMAs) para os dados fornecidos."""
        # Garante que 'Close' exista e é numérico
        if 'Close' not in data.columns or not pd.api.types.is_numeric_dtype(data['Close']):
            logger.warning("Coluna 'Close' ausente ou não numérica para cálculo de SMA.")
            return data

        data['SMA_Fast'] = data['Close'].rolling(window=self.sma_fast_period).mean()
        data['SMA_Slow'] = data['Close'].rolling(window=self.sma_slow_period).mean()
        return data

    def _calculate_rsi(self, data):
        """Calcula o Índice de Força Relativa (RSI)."""
        # Garante que 'Close' exista e é numérico
        if 'Close' not in data.columns or not pd.api.types.is_numeric_dtype(data['Close']):
            logger.warning("Coluna 'Close' ausente ou não numérica para cálculo de RSI.")
            return data

        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()

        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        return data

    def execute_strategy_cycle(self, current_capital, current_positions, current_price_data, historical_data):
        """
        Gera sinais de compra e venda baseados na estratégia.

        Args:
            current_capital (float): Capital disponível atualmente no backtest.
            current_positions (dict): Dicionário de posições abertas.
            current_price_data (dict): {'symbol': str, 'price': float, 'timestamp': int (ms)} da vela atual.
            historical_data (pd.DataFrame): DataFrame com dados históricos ATÉ a vela atual.

        Returns:
            tuple: (positions_to_close, new_position_data)
                positions_to_close (list): Lista de tuplas (symbol, reason) para fechar.
                new_position_data (dict or None): Dicionário com dados para uma nova compra, ou None.
        """
        symbol = current_price_data['symbol']
        current_price = current_price_data['price']
        current_timestamp = datetime.fromtimestamp(current_price_data['timestamp'] / 1000)  # Converte ms para datetime

        positions_to_close = []
        new_position_bought_data = None

        # Certifique-se de que temos dados suficientes para calcular os indicadores
        # A quantidade de velas necessárias é o maior período dos indicadores + 1
        min_candles_needed = max(self.sma_slow_period, self.rsi_period) + 1

        # O DataFrame `historical_data` já vem fatiado até a vela atual
        if len(historical_data) < min_candles_needed:
            logger.debug(f"Dados insuficientes para {symbol} em {current_timestamp}. Necessário: {min_candles_needed} velas, Disponível: {len(historical_data)}")
            return (positions_to_close, new_position_bought_data)

        # Restante do código...
        # ...
        print("Valor de retorno:", (positions_to_close, new_position_bought_data))
        return (positions_to_close, new_position_bought_data)
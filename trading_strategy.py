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
        self.trailing_stop_percent = settings.TRAILING_STOP_PERCENT

        # Estado da estratégia
        self.in_position = False
        self.position_data = {}

        logging.info("Estratégia de Trading inicializada.")

    def _calculate_smas(self, data):
        """Calcula as Médias Móveis Simples (SMAs) para os dados fornecidos."""
        if 'close' not in data.columns or not pd.api.types.is_numeric_dtype(data['close']):
            logger.warning("Coluna 'close' ausente ou não numérica para cálculo de SMA.")
            return data

        data['SMA_Fast'] = data['close'].rolling(window=self.sma_fast_period).mean()
        data['SMA_Slow'] = data['close'].rolling(window=self.sma_slow_period).mean()
        return data

    def _calculate_rsi(self, data):
        """Calcula o Índice de Força Relativa (RSI)."""
        if 'close' not in data.columns or not pd.api.types.is_numeric_dtype(data['close']):
            logger.warning("Coluna 'close' ausente ou não numérica para cálculo de RSI.")
            return data

        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()

        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        return data

    def _calculate_macd(self, data):
        """Calcula o MACD e a linha de sinal."""
        if 'close' not in data.columns or not pd.api.types.is_numeric_dtype(data['close']):
            logger.warning("Coluna 'close' ausente ou não numérica para cálculo de MACD.")
            return data

        exp1 = data['close'].ewm(span=12, adjust=False).mean()
        exp2 = data['close'].ewm(span=26, adjust=False).mean()
        data['MACD'] = exp1 - exp2
        data['Signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
        return data

    def _simulate_buy(self, symbol, price, timestamp, trade_amount):
        """Simula uma compra e retorna os dados da nova posição."""
        quantity = trade_amount / price
        position = {
            'symbol': symbol,
            'entry_price': price,
            'bought_quantity': quantity,
            'entry_time': datetime.fromtimestamp(timestamp / 1000),
            'order_id': 'SIMULATED_BUY_' + str(int(timestamp)),
            'current_high': price,
            'last_price_checked': price
        }
        logger.info(f"SIMULANDO COMPRA: {quantity:.4f} {symbol} @ {price:.4f}")
        return position

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
        current_timestamp = datetime.fromtimestamp(current_price_data['timestamp'] / 1000)

        positions_to_close = []
        new_position_data = None

        # Certifique-se de que temos dados suficientes para calcular os indicadores
        min_candles_needed = max(self.sma_slow_period, self.rsi_period, 26) + 1
        if len(historical_data) < min_candles_needed:
            logger.debug(f"Dados insuficientes para {symbol} em {current_timestamp}. Necessário: {min_candles_needed} velas, Disponível: {len(historical_data)}")
            logger.debug(f"Últimas 5 velas: {historical_data.tail(5)}")
            return (positions_to_close, new_position_data)

        # Calcular indicadores
        data = historical_data.copy()
        data = self._calculate_smas(data)
        data = self._calculate_rsi(data)
        data = self._calculate_macd(data)

        # Verificar se há dados válidos para os indicadores
        if data['SMA_Fast'].iloc[-1] is None or data['SMA_Slow'].iloc[-1] is None or data['RSI'].iloc[-1] is None or data['MACD'].iloc[-1] is None:
            logger.debug(f"Indicadores não calculados para {symbol} devido a dados insuficientes ou inválidos. SMA_Fast: {data['SMA_Fast'].iloc[-1]}, SMA_Slow: {data['SMA_Slow'].iloc[-1]}, RSI: {data['RSI'].iloc[-1]}, MACD: {data['MACD'].iloc[-1]}")
            return (positions_to_close, new_position_data)

        # Logar os valores dos indicadores para depuração
        logger.debug(f"Indicadores para {symbol}: SMA_Fast={data['SMA_Fast'].iloc[-1]:.4f}, SMA_Slow={data['SMA_Slow'].iloc[-1]:.4f}, RSI={data['RSI'].iloc[-1]:.2f}, MACD={data['MACD'].iloc[-1]:.4f}, Signal={data['Signal'].iloc[-1]:.4f}, Preço Atual={current_price:.4f}")

        # Verificar se há uma posição aberta para este símbolo
        if symbol in current_positions:
            position = current_positions[symbol]
            entry_price = position['entry_price']
            current_high = max(position['current_high'], current_price)

            # Atualizar o maior preço atingido (para trailing stop)
            position['current_high'] = current_high

            # Verificar condições de saída (venda)
            # 1. Stop-Loss
            if current_price <= entry_price * (1 - self.stop_loss_percent):
                positions_to_close.append((symbol, "Stop-Loss atingido"))
                logger.info(f"Sinal de venda para {symbol}: Stop-Loss atingido @ {current_price:.4f}")
                return (positions_to_close, None)

            # 2. Take-Profit
            if current_price >= entry_price * (1 + self.take_profit_percent):
                positions_to_close.append((symbol, "Take-Profit atingido"))
                logger.info(f"Sinal de venda para {symbol}: Take-Profit atingido @ {current_price:.4f}")
                return (positions_to_close, None)

            # 3. Trailing Stop
            trailing_stop_price = current_high * (1 - self.trailing_stop_percent)
            if current_price <= trailing_stop_price:
                positions_to_close.append((symbol, "Trailing Stop atingido"))
                logger.info(f"Sinal de venda para {symbol}: Trailing Stop atingido @ {current_price:.4f}")
                return (positions_to_close, None)

            # 4. Sinal de venda por RSI (sobrecomprado)
            if data['RSI'].iloc[-1] >= self.overbought_rsi:
                positions_to_close.append((symbol, "RSI Sobrecomprado"))
                logger.info(f"Sinal de venda para {symbol}: RSI Sobrecomprado ({data['RSI'].iloc[-1]:.2f})")
                return (positions_to_close, None)

        else:
            # Verificar condições de entrada (compra)
            # 1. Tendência de alta baseada em SMA (SMA_Fast > SMA_Slow)
            if data['SMA_Fast'].iloc[-1] > data['SMA_Slow'].iloc[-1]:
                # 2. RSI não está sobrecomprado
                if data['RSI'].iloc[-1] <= self.overbought_rsi:
                    score = 100 - data['RSI'].iloc[-1]
                    new_position_data = {
                        'symbol': symbol,
                        'price': current_price,
                        'timestamp': current_price_data['timestamp'],
                        'score': score
                    }
                    logger.info(f"Sinal de compra para {symbol}: SMA_Fast > SMA_Slow e RSI {data['RSI'].iloc[-1]:.2f}, Score: {score:.2f}")
            # 2. RSI sobrevendido
            elif data['RSI'].iloc[-1] <= self.oversold_rsi:
                # Verificar tendência de alta (SMA_Fast > SMA_Slow)
                if data['SMA_Fast'].iloc[-1] > data['SMA_Slow'].iloc[-1]:
                    score = 100 - data['RSI'].iloc[-1]
                    new_position_data = {
                        'symbol': symbol,
                        'price': current_price,
                        'timestamp': current_price_data['timestamp'],
                        'score': score
                    }
                    logger.info(f"Sinal de compra para {symbol}: RSI Sobrevendido ({data['RSI'].iloc[-1]:.2f}) e tendência de alta, Score: {score:.2f}")
            # 3. Cruzamento de MACD
            elif (data['MACD'].iloc[-1] > data['Signal'].iloc[-1] and
                  data['MACD'].iloc[-2] <= data['Signal'].iloc[-2] and
                  data['RSI'].iloc[-1] <= self.overbought_rsi):
                score = 100 - data['RSI'].iloc[-1]
                new_position_data = {
                    'symbol': symbol,
                    'price': current_price,
                    'timestamp': current_price_data['timestamp'],
                    'score': score
                }
                logger.info(f"Sinal de compra para {symbol}: MACD cruzamento e RSI {data['RSI'].iloc[-1]:.2f}, Score: {score:.2f}")

        logger.debug(f"Valor de retorno para {symbol}: {([s for s, _ in positions_to_close], new_position_data)}")
        return (positions_to_close, new_position_data)
import pandas as pd
import logging
import os
from datetime import datetime, timedelta

# Importa suas configurações
import settings

# Importa suas classes existentes
from trading_strategy import TradingStrategy

# Importa as funções do seu data_manager.py
try:
    from data_manager import get_historical_klines, save_dataframe_to_csv, load_dataframe_from_csv
except ImportError:
    logging.error("Erro: 'data_manager.py' não encontrado ou funções não importáveis. Verifique o caminho.")
    exit()  # Sai se as funções essenciais de gerenciamento de dados não puderem ser carregadas

class Backtester:
    def __init__(self, initial_capital, symbol, interval, start_date, end_date):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.symbol = symbol
        self.interval = interval
        self.start_date = start_date
        self.end_date = end_date
        self.trading_strategy = TradingStrategy()
        self.current_positions = {}  # {symbol: {entry_price, bought_quantity, entry_time, order_id, current_high}}
        self.trade_history = []  # Lista de trades concluídos
        self.historical_data_df = pd.DataFrame()  # Onde os dados históricos serão carregados

        logging.info(f"Backtester inicializado com capital: {self.initial_capital:.2f} USDT.")

    def _simulate_buy(self, symbol, current_price, quantity, timestamp):
        cost = current_price * quantity
        # Opcional: Adicione uma pequena taxa de deslizamento (slippage) ou comissão de corretagem aqui
        # cost = current_price * quantity * (1 + settings.SIMULATED_FEE_PERCENT)

        if self.capital >= cost:
            self.capital -= cost
            position = {
                'symbol': symbol,
                'entry_price': current_price,
                'bought_quantity': quantity,
                'entry_time': timestamp,
                'order_id': 'SIMULATED_BUY_' + str(int(timestamp.timestamp())),
                'current_high': current_price,  # Para trailing stop (precisa ser atualizado no loop)
                'last_price_checked': current_price  # Para evitar recalculos repetidos no mesmo ponto
            }
            self.current_positions[symbol] = position
            logging.info(f"[Backtest] COMPRA EXECUTADA: {quantity:.4f} {symbol} @ {current_price:.4f}. Capital restante: {self.capital:.2f}")
            return True
        else:
            logging.warning(f"[Backtest] COMPRA FALHOU: Capital insuficiente para comprar {quantity:.4f} {symbol} @ {current_price:.4f}. Capital: {self.capital:.2f}")
            return False

    def _simulate_sell(self, symbol, current_price, quantity, timestamp, reason):
        if symbol in self.current_positions:
            position = self.current_positions[symbol]
            revenue = current_price * quantity
            # Opcional: Subtraia taxas de comissão da receita
            # revenue = current_price * quantity * (1 - settings.SIMULATED_FEE_PERCENT)
            self.capital += revenue

            pnl = (current_price - position['entry_price']) * quantity
            # Evita divisão por zero
            pnl_percent = (pnl / (position['entry_price'] * quantity)) * 100 if (position['entry_price'] * quantity) > 0 else 0

            trade = {
                'symbol': symbol,
                'entry_price': position['entry_price'],
                'exit_price': current_price,
                'quantity': quantity,
                'entry_time': position['entry_time'],
                'exit_time': timestamp,
                'pnl': pnl,
                'pnl_percent': pnl_percent,
                'reason': reason
            }
            self.trade_history.append(trade)
            del self.current_positions[symbol]  # Remove a posição
            logging.info(f"[Backtest] VENDA EXECUTADA: {quantity:.4f} {symbol} @ {current_price:.4f}. PnL: {pnl:.2f} ({pnl_percent:.2f}%). Razão: {reason}. Capital atual: {self.capital:.2f}")
            return True
        else:
            logging.warning(f"[Backtest] VENDA FALHOU: Posição para {symbol} não encontrada.")
            return False

   
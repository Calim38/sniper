from flask import Flask, render_template
import json
import os
from datetime import datetime
from binance_utils import BinanceClient
from settings import POSITIONS_FILE, CLOSED_POSITIONS_FILE, TESTNET_MODE

app = Flask(__name__)

def load_open_positions():
    """Carrega as posições abertas do arquivo JSON."""
    if os.path.exists(POSITIONS_FILE):
        try:
            with open(POSITIONS_FILE, 'r') as f:
                positions = json.load(f)
                for symbol, data in positions.items():
                    if 'entry_time' in data and isinstance(data['entry_time'], (int, float)):
                        data['entry_time'] = datetime.fromtimestamp(data['entry_time'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                return positions
        except Exception as e:
            print(f"Erro ao carregar posições abertas: {e}")
            return {}
    return {}

def load_closed_positions():
    """Carrega as posições fechadas do arquivo JSON."""
    if os.path.exists(CLOSED_POSITIONS_FILE):
        try:
            with open(CLOSED_POSITIONS_FILE, 'r') as f:
                positions = json.load(f)
                for data in positions:
                    if 'entry_time' in data and isinstance(data['entry_time'], (int, float)):
                        data['entry_time'] = datetime.fromtimestamp(data['entry_time'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    if 'close_time' in data and isinstance(data['close_time'], (int, float)):
                        data['close_time'] = datetime.fromtimestamp(data['close_time'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                return positions
        except Exception as e:
            print(f"Erro ao carregar posições fechadas: {e}")
            return []
    return []

def get_current_prices(symbols):
    """Obtém os preços atuais dos símbolos via BinanceClient."""
    binance_client = BinanceClient()
    prices = {}
    for symbol in symbols:
        try:
            klines = binance_client.get_klines(symbol=symbol, interval='1m', limit=1)
            if klines is not None and not klines.empty:
                prices[symbol] = float(klines['close'].iloc[-1])
            else:
                prices[symbol] = None
        except Exception as e:
            print(f"Erro ao obter preço para {symbol}: {e}")
            prices[symbol] = None
    return prices

@app.route('/')
def dashboard():
    # Carregar posições abertas e fechadas
    open_positions = load_open_positions()
    closed_positions = load_closed_positions()

    # Obter preços atuais para posições abertas
    symbols = list(open_positions.keys())
    current_prices = get_current_prices(symbols) if symbols else {}

    # Calcular ganhos/perdas para posições abertas
    open_positions_data = []
    total_open_pl = 0
    for symbol, data in open_positions.items():
        current_price = current_prices.get(symbol, data['entry_price'])
        pl = (current_price - data['entry_price']) * data['bought_quantity'] if current_price else 0
        total_open_pl += pl
        open_positions_data.append({
            'symbol': symbol,
            'entry_price': data['entry_price'],
            'quantity': data['bought_quantity'],
            'current_price': current_price,
            'profit_loss': pl,
            'entry_time': data['entry_time']
        })

    # Calcular ganhos/perdas para posições fechadas
    total_closed_pl = sum(data['profit_loss'] for data in closed_positions)

    # Calcular saldo inicial e atual (assumindo saldo inicial fixo para simplificação)
    initial_balance = 10000  # Ajuste conforme necessário
    current_balance = initial_balance + total_open_pl + total_closed_pl

    return render_template('dashboard.html', 
                         open_positions=open_positions_data,
                         closed_positions=closed_positions,
                         initial_balance=initial_balance,
                         current_balance=current_balance,
                         total_open_pl=total_open_pl,
                         total_closed_pl=total_closed_pl)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
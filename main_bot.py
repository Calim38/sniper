import logging
import time
import json
import os
from filelock import FileLock, Timeout
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from settings import LOG_FILE, POSITIONS_FILE, CYCLE_DELAY_SECONDS, TESTNET_MODE, BASE_URL, TESTNET_BASE_URL, KLINE_INTERVAL, KLINE_LIMIT, MAX_OPEN_POSITIONS, MIN_TRADE_AMOUNT_USDT, TRADE_AMOUNT_USDT
from binance_utils import BinanceClient
from trading_strategy import TradingStrategy

# Configuração de Logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

LOCK_FILE = "bot.lock"
CLOSED_POSITIONS_FILE = "closed_positions.json"

def load_open_positions():
    """Carrega as posições abertas do arquivo JSON."""
    if os.path.exists(POSITIONS_FILE):
        try:
            with open(POSITIONS_FILE, 'r') as f:
                positions = json.load(f)
                for symbol, data in positions.items():
                    if 'entry_time' in data and isinstance(data['entry_time'], (int, float)):
                        data['entry_time'] = datetime.fromtimestamp(data['entry_time'] / 1000)
                return positions
        except json.JSONDecodeError:
            logging.error(f"Erro ao decodificar JSON do arquivo {POSITIONS_FILE}. Criando um novo.")
            return {}
        except Exception as e:
            logging.error(f"Erro inesperado ao carregar posições: {e}")
            return {}
    return {}

def save_open_positions(positions):
    """Salva as posições abertas no arquivo JSON."""
    try:
        positions_to_save = {}
        for symbol, data in positions.items():
            saved_data = data.copy()
            if 'entry_time' in saved_data and isinstance(saved_data['entry_time'], datetime):
                saved_data['entry_time'] = int(saved_data['entry_time'].timestamp() * 1000)
            positions_to_save[symbol] = saved_data
        
        with open(POSITIONS_FILE, 'w') as f:
            json.dump(positions_to_save, f, indent=4)
        logging.info(f"Posições salvas em {POSITIONS_FILE}.")
    except Exception as e:
        logging.error(f"Erro ao salvar posições: {e}")

def save_closed_position(symbol, position, close_price, reason):
    """Salva uma posição fechada no arquivo closed_positions.json."""
    try:
        closed_positions = []
        if os.path.exists(CLOSED_POSITIONS_FILE):
            with open(CLOSED_POSITIONS_FILE, 'r') as f:
                closed_positions = json.load(f)
        
        closed_position = {
            'symbol': symbol,
            'entry_price': position['entry_price'],
            'close_price': close_price,
            'quantity': position['bought_quantity'],
            'entry_time': int(position['entry_time'].timestamp() * 1000),
            'close_time': int(datetime.now().timestamp() * 1000),
            'reason': reason,
            'profit_loss': (close_price - position['entry_price']) * position['bought_quantity']
        }
        closed_positions.append(closed_position)
        
        with open(CLOSED_POSITIONS_FILE, 'w') as f:
            json.dump(closed_positions, f, indent=4)
        logging.info(f"Posição fechada salva: {symbol} @ {close_price:.4f}, Lucro/Prejuízo: {closed_position['profit_loss']:.4f}")
    except Exception as e:
        logging.error(f"Erro ao salvar posição fechada para {symbol}: {e}")

def analyze_symbol(symbol, binance_client, trading_strategy, current_usdt_balance, open_positions):
    """Analisa um símbolo específico e retorna sinais de compra/venda."""
    logging.info(f"Analisando símbolo: {symbol}")
    historical_klines_df = binance_client.get_klines(symbol=symbol, interval=KLINE_INTERVAL, limit=KLINE_LIMIT)
    if historical_klines_df is None or historical_klines_df.empty:
        logging.warning(f"Não foi possível obter dados históricos para {symbol} ou DataFrame vazio.")
        return symbol, [], None
    current_price = float(historical_klines_df['close'].iloc[-1])
    current_timestamp_ms = historical_klines_df['open_time'].iloc[-1].timestamp() * 1000
    current_price_data = {'symbol': symbol, 'price': current_price, 'timestamp': current_timestamp_ms}
    positions_to_close, potential_buy_signal = trading_strategy.execute_strategy_cycle(
        current_usdt_balance, open_positions, current_price_data, historical_klines_df
    )
    return symbol, positions_to_close, potential_buy_signal

def run_bot():
    lock = FileLock(LOCK_FILE, timeout=5)

    logging.info(f"Modo de Operação: {'TESTNET' if TESTNET_MODE else 'REAL'}")
    logging.info(f"Base URL: {TESTNET_BASE_URL if TESTNET_MODE else BASE_URL}")

    try:
        with lock:
            logging.info("--- Bot Iniciado ---")

            binance_client = BinanceClient()
            trading_strategy = TradingStrategy()

            last_pairs_update = 0
            cached_usdt_pairs = []

            while True:
                logging.info(f"--- Ciclo de Verificação Iniciado ---")

                # Atualiza a lista de pares USDT a cada hora (3600 segundos)
                if time.time() - last_pairs_update > 3600:
                    cached_usdt_pairs = binance_client.get_usdt_pairs(min_volume_24h=5000000)
                    last_pairs_update = time.time()
                    if not cached_usdt_pairs:
                        logging.error("Não foi possível obter a lista de pares USDT. Pulando ciclo atual.")
                        time.sleep(CYCLE_DELAY_SECONDS)
                        continue
                    logging.info(f"Lista de pares USDT atualizada: {len(cached_usdt_pairs)} pares encontrados: {cached_usdt_pairs}")

                # Para testar com pares fixos, descomente as linhas abaixo e comente a chamada a get_usdt_pairs acima
                # cached_usdt_pairs = ['BTCUSDT', 'ETHUSDT']
                # last_pairs_update = time.time()
                # logging.info(f"Usando pares fixos para teste: {cached_usdt_pairs}")

                open_positions = load_open_positions()
                positions_modified_in_cycle = False

                current_usdt_balance = binance_client.get_account_balance(asset='USDT')
                if current_usdt_balance is None:
                    logging.error("Não foi possível obter saldo USDT. Pulando ciclo atual.")
                    time.sleep(CYCLE_DELAY_SECONDS)
                    continue

                logging.info(f"Posições atualmente rastreadas: {list(open_positions.keys())}")
                logging.info(f"Saldo USDT disponível: {current_usdt_balance:.4f}")

                potential_buy_signals = []
                all_positions_to_close_in_cycle = []

                # Analisar símbolos em paralelo
                with ThreadPoolExecutor(max_workers=10) as executor:
                    results = executor.map(
                        lambda symbol: analyze_symbol(symbol, binance_client, trading_strategy, current_usdt_balance, open_positions),
                        cached_usdt_pairs
                    )
                    for symbol, positions_to_close_for_symbol, potential_buy_signal_for_symbol in results:
                        if positions_to_close_for_symbol:
                            for s, reason in positions_to_close_for_symbol:
                                if s in open_positions:
                                    # Obter preço atual para salvar na posição fechada
                                    historical_klines_df = binance_client.get_klines(symbol=s, interval=KLINE_INTERVAL, limit=1)
                                    close_price = float(historical_klines_df['close'].iloc[-1]) if historical_klines_df is not None and not historical_klines_df.empty else open_positions[s]['entry_price']
                                    save_closed_position(s, open_positions[s], close_price, reason)
                            all_positions_to_close_in_cycle.extend(positions_to_close_for_symbol)
                        if potential_buy_signal_for_symbol:
                            potential_buy_signals.append(potential_buy_signal_for_symbol)

                for s, reason in all_positions_to_close_in_cycle:
                    if s in open_positions:
                        logging.info(f"Removendo posição {s} do rastreamento do bot (concluída ou erro/ajuste manual - Razão: {reason}).")
                        del open_positions[s]
                        positions_modified_in_cycle = True

                potential_buy_signals.sort(key=lambda x: x['score'], reverse=True)
                logging.info(f"Sinais de compra potenciais encontrados (ordenados por score): {[(s['symbol'], s['score']) for s in potential_buy_signals]}")

                trades_executed_in_this_cycle = 0
                slots_available = MAX_OPEN_POSITIONS - len(open_positions)
                
                if slots_available <= 0:
                    logging.info(f"Nenhum slot disponível para novas compras. Limite de {MAX_OPEN_POSITIONS} posições atingido.")
                else:
                    for signal in potential_buy_signals:
                        if len(open_positions) >= MAX_OPEN_POSITIONS:
                            logging.info(f"Limite de {MAX_OPEN_POSITIONS} posições atingido. Parando de buscar novas compras.")
                            break

                        trade_amount_for_this_signal = TRADE_AMOUNT_USDT
                        if trade_amount_for_this_signal > current_usdt_balance:
                            trade_amount_for_this_signal = current_usdt_balance
                            
                        if trade_amount_for_this_signal >= MIN_TRADE_AMOUNT_USDT:
                            new_position = trading_strategy._simulate_buy(
                                signal['symbol'], 
                                signal['price'], 
                                signal['timestamp'], 
                                trade_amount_for_this_signal
                            )
                            open_positions[new_position['symbol']] = new_position
                            current_usdt_balance -= trade_amount_for_this_signal
                            trades_executed_in_this_cycle += 1
                            slots_available -= 1
                            positions_modified_in_cycle = True
                            logging.info(f"COMPRA EXECUTADA (SIMULADA): {signal['symbol']} com score {signal['score']}. Capital restante: {current_usdt_balance:.2f}. Posições abertas: {len(open_positions)}/{MAX_OPEN_POSITIONS}")
                        else:
                            logging.info(f"Sinal para {signal['symbol']} ignorado: Capital insuficiente ({current_usdt_balance:.2f}) para trade mínimo de {MIN_TRADE_AMOUNT_USDT}.")
                            break
                
                if trades_executed_in_this_cycle > 0:
                    logging.info(f"Total de {trades_executed_in_this_cycle} novas compras simuladas neste ciclo.")

                if positions_modified_in_cycle:
                    save_open_positions(open_positions)
                    logging.info("Posições salvas devido a modificações no ciclo.")
                else:
                    logging.info("Nenhuma modificação nas posições neste ciclo.")

                logging.info(f"--- Ciclo de Verificação Concluído. Aguardando {CYCLE_DELAY_SECONDS} segundos ---")
                time.sleep(CYCLE_DELAY_SECONDS)

    except Timeout:
        logging.error(f"Outra instância do bot já está rodando. O arquivo de lock '{LOCK_FILE}' está ativo (timeout de 5s). Saíndo.")
    except KeyboardInterrupt:
        logging.info("Bot encerrado pelo usuário (Ctrl+C).")
    except Exception as e:
        logging.exception(f"Ocorreu um erro crítico e inesperado no bot: {e}")
    finally:
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
                logging.info(f"Lockfile '{LOCK_FILE}' removido.")
            except Exception as e:
                logging.error(f"Erro ao remover lockfile '{LOCK_FILE}': {e}")

if __name__ == "__main__":
    run_bot()
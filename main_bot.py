import logging
import time
import json
import os
from filelock import FileLock, Timeout
from datetime import datetime

# Importa as configurações do settings.py, incluindo as novas variáveis
from settings import LOG_FILE, POSITIONS_FILE, CYCLE_DELAY_SECONDS, TESTNET_MODE, BASE_URL, LOG_LEVEL, TRADE_SYMBOLS, KLINE_INTERVAL, KLINE_LIMIT, MAX_OPEN_POSITIONS, MIN_TRADE_AMOUNT_USDT, TRADE_AMOUNT_USDT
from binance_utils import BinanceClient
from trading_strategy import TradingStrategy

# --- Configuração de Logging ---
logging.basicConfig(
    level=LOG_LEVEL, # Usa o nível de log definido em settings.py
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# --- Caminho do Lockfile ---
LOCK_FILE = "bot.lock"

# --- Funções de Manipulação de Posições ---
def load_open_positions():
    """Carrega as posições abertas do arquivo JSON."""
    if os.path.exists(POSITIONS_FILE):
        try:
            with open(POSITIONS_FILE, 'r') as f:
                positions = json.load(f)
                # Converte timestamps numéricos de volta para ISO format se necessário
                for symbol, data in positions.items():
                    if 'entry_time' in data and isinstance(data['entry_time'], (int, float)):
                        data['entry_time'] = datetime.fromtimestamp(data['entry_time'] / 1000) # Convertendo para datetime object
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
        # Converte datetime objects para timestamp antes de salvar
        positions_to_save = {}
        for symbol, data in positions.items():
            saved_data = data.copy()
            if 'entry_time' in saved_data and isinstance(saved_data['entry_time'], datetime):
                saved_data['entry_time'] = int(saved_data['entry_time'].timestamp() * 1000) # Convertendo para ms
            positions_to_save[symbol] = saved_data
        
        with open(POSITIONS_FILE, 'w') as f:
            json.dump(positions_to_save, f, indent=4)
        logging.info(f"Posições salvas em {POSITIONS_FILE}.")
    except Exception as e:
        logging.error(f"Erro ao salvar posições: {e}")


# --- Função Principal do Bot ---
def run_bot():
    lock = FileLock(LOCK_FILE, timeout=5)

    logging.info(f"Modo de Operação: {'TESTNET' if TESTNET_MODE else 'REAL'}")
    logging.info(f"Base URL: {BASE_URL}") 

    try:
        with lock:
            logging.info("--- Bot Iniciado ---")

            binance_client = BinanceClient()
            trading_strategy = TradingStrategy()

            while True:
                logging.info(f"--- Ciclo de Verificação Iniciado ---")

                open_positions = load_open_positions()
                positions_modified_in_cycle = False # Flag para saber se algo mudou neste ciclo

                current_usdt_balance = binance_client.get_account_balance(asset='USDT')
                if current_usdt_balance is None:
                    logging.error("Não foi possível obter saldo USDT. Pulando ciclo atual.")
                    time.sleep(CYCLE_DELAY_SECONDS)
                    continue

                logging.info(f"Posições atualmente rastreadas: {list(open_positions.keys())}")
                logging.info(f"Saldo USDT disponível: {current_usdt_balance:.4f}")

                potential_buy_signals = []
                all_positions_to_close_in_cycle = [] # Coleta todas as posições a serem fechadas neste ciclo

                # --- FASE 1: Obter dados e verificar SINAIS DE VENDA/COMPRA POTENCIAL para CADA SÍMBOLO ---
                for symbol in TRADE_SYMBOLS:
                    logging.info(f"Analisando símbolo: {symbol}")
                    
                    # Obter preço atual (para lógica de venda e para current_price_data)
                    # Note: get_klines já traz o preço de fechamento do último candle, que pode ser usado como "preço atual"
                    # Para um preço mais "em tempo real", precisaríamos de um endpoint de ticker, mas o klines serve para a estratégia
                    
                    # Obter dados históricos (klines)
                    historical_klines_df = binance_client.get_klines(
                        symbol=symbol,
                        interval=KLINE_INTERVAL,
                        limit=KLINE_LIMIT
                    )
                    
                    if historical_klines_df is None or historical_klines_df.empty:
                        logging.warning(f"Não foi possível obter dados históricos para {symbol} ou DataFrame vazio. Pulando análise deste símbolo.")
                        continue
                    
                    # O último kline contém o preço atual e timestamp de abertura
                    current_price = float(historical_klines_df['close'].iloc[-1])
                    current_timestamp_ms = historical_klines_df['open_time'].iloc[-1].timestamp() * 1000 # Timestamp em ms

                    current_price_data = {
                        'symbol': symbol,
                        'price': current_price,
                        'timestamp': current_timestamp_ms
                    }

                    # Chamar a estratégia para verificar sinais de VENDA (para posições já abertas)
                    # e SINAIS DE COMPRA POTENCIAIS (se não houver posição aberta para o símbolo)
                    positions_to_close_for_symbol, potential_buy_signal_for_symbol = trading_strategy.execute_strategy_cycle(
                        current_usdt_balance, 
                        open_positions, # Passa o dicionário de posições, a estratégia verifica se o símbolo está lá
                        current_price_data, 
                        historical_klines_df # Passa o DataFrame de dados históricos
                    )
                    
                    # Adiciona as posições a serem fechadas deste símbolo à lista geral
                    if positions_to_close_for_symbol:
                        all_positions_to_close_in_cycle.extend(positions_to_close_for_symbol)
                    
                    # Se um sinal de compra potencial foi gerado para este símbolo, adicione-o à lista
                    if potential_buy_signal_for_symbol:
                        potential_buy_signals.append(potential_buy_signal_for_symbol)

                # --- FASE 2: Processar VENDAS (para liberar slots e capital) ---
                for s, reason in all_positions_to_close_in_cycle:
                    if s in open_positions:
                        logging.info(f"Removendo posição {s} do rastreamento do bot (concluída ou erro/ajuste manual - Razão: {reason}).")
                        # Aqui você chamaria binance_client.create_order(s, 'SELL', 'MARKET', open_positions[s]['bought_quantity'])
                        # E verificaria o sucesso da venda antes de deletar
                        del open_positions[s]
                        positions_modified_in_cycle = True
                        # Recalcular saldo USDT após a venda (se for um bot real)
                        # current_usdt_balance = binance_client.get_account_balance(asset='USDT')


                # --- FASE 3: Classificar e Executar as MELHORES COMPRAS ---

                # 1. Classificar os sinais potenciais do maior score para o menor
                potential_buy_signals.sort(key=lambda x: x['score'], reverse=True)
                
                logging.info(f"Sinais de compra potenciais encontrados (ordenados por score): {[(s['symbol'], s['score']) for s in potential_buy_signals]}")

                trades_executed_in_this_cycle = 0
                
                # Calcular quantos slots ainda temos disponíveis
                slots_available = MAX_OPEN_POSITIONS - len(open_positions)
                
                if slots_available <= 0:
                    logging.info(f"Nenhum slot disponível para novas compras. Limite de {MAX_OPEN_POSITIONS} posições atingido.")
                else:
                    # Iterar sobre os melhores sinais até atingir o limite de posições ou o capital
                    for signal in potential_buy_signals:
                        if len(open_positions) >= MAX_OPEN_POSITIONS:
                            logging.info(f"Limite de {MAX_OPEN_POSITIONS} posições atingido. Parando de buscar novas compras.")
                            break # Sai do loop de sinais potenciais

                        # Calcular o valor do trade para esta compra
                        # Opção 1: Valor fixo por trade (definido em settings.TRADE_AMOUNT_USDT)
                        trade_amount_for_this_signal = TRADE_AMOUNT_USDT

                        # Opção 2: Alocar capital igualmente entre os slots restantes (mais dinâmico)
                        # if slots_available > 0:
                        #     trade_amount_for_this_signal = current_usdt_balance / slots_available
                        # else:
                        #     trade_amount_for_this_signal = 0 # Não deveria acontecer se slots_available > 0
                        
                        # Garanta que não exceda o capital disponível e que seja maior que o mínimo
                        if trade_amount_for_this_signal > current_usdt_balance:
                            trade_amount_for_this_signal = current_usdt_balance
                            
                        if trade_amount_for_this_signal >= MIN_TRADE_AMOUNT_USDT:
                            # Simular a compra
                            new_position = trading_strategy._simulate_buy(
                                signal['symbol'], 
                                signal['price'], 
                                signal['timestamp'], 
                                trade_amount_for_this_signal
                            )
                            open_positions[new_position['symbol']] = new_position
                            current_usdt_balance -= trade_amount_for_this_signal # Reduz o capital disponível
                            trades_executed_in_this_cycle += 1
                            slots_available -= 1 # Reduz os slots disponíveis
                            positions_modified_in_cycle = True
                            logging.info(f"COMPRA EXECUTADA (SIMULADA): {signal['symbol']} com score {signal['score']}. Capital restante: {current_usdt_balance:.2f}. Posições abertas: {len(open_positions)}/{MAX_OPEN_POSITIONS}")
                        else:
                            logging.info(f"Sinal para {signal['symbol']} ignorado: Capital insuficiente ({current_usdt_balance:.2f}) para trade mínimo de {MIN_TRADE_AMOUNT_USDT}.")
                            # Se não há capital para o trade atual, provavelmente não haverá para os próximos
                            break 
                
                if trades_executed_in_this_cycle > 0:
                    logging.info(f"Total de {trades_executed_in_this_cycle} novas compras simuladas neste ciclo.")


                # --- FIM DA OBTENÇÃO DE DADOS DE MERCADO E EXECUÇÃO DE TRADES ---

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
        # Garante que o lockfile seja removido ao encerrar o bot
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
                logging.info(f"Lockfile '{LOCK_FILE}' removido.")
            except Exception as e:
                logging.error(f"Erro ao remover lockfile '{LOCK_FILE}': {e}")

if __name__ == "__main__":
    run_bot()
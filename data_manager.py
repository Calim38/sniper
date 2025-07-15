import pandas as pd
from binance.client import Client
import os
from datetime import datetime, timedelta
import logging

import settings # Importa suas configurações

# Configurações do logger
logger = logging.getLogger(__name__)

# Certifique-se de que a pasta 'data' exista
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def get_binance_client():
    """Retorna uma instância do cliente Binance, configurado para testnet ou produção."""
    api_key = settings.API_KEY
    api_secret = settings.API_SECRET
    
    # Usamos 'tld' aqui. Se 'us' não funcionar para a Testnet, podemos tentar 'com'.
    if settings.TESTNET_MODE:
        return Client(api_key, api_secret, tld='us') # Tentar 'us' para a Testnet
    else:
        return Client(api_key, api_secret, tld='com')


def get_historical_klines(symbol, interval, start_str, end_str=None):
    """
    Busca dados históricos de klines da Binance em chunks, se o período for longo.
    Retorna um DataFrame pandas.
    """
    client = get_binance_client() # Chamando a função definida acima, que cria o binance.client.Client
    
    # Converte as strings de data para timestamps de milissegundos
    start_ts = int(datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)
    end_ts = None
    if end_str:
        end_ts = int(datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)

    all_klines = []
    current_start_ts = start_ts
    
    # Definindo o mapeamento de intervalos para milissegundos para calcular o próximo chunk
    interval_to_ms = {
        "1m": 60 * 1000, "3m": 3 * 60 * 1000, "5m": 5 * 60 * 1000, "15m": 15 * 60 * 1000, 
        "30m": 30 * 60 * 1000, "1h": 60 * 60 * 1000, "2h": 2 * 60 * 60 * 1000, 
        "4h": 4 * 60 * 60 * 1000, "6h": 6 * 60 * 60 * 1000, "8h": 8 * 60 * 60 * 1000, 
        "12h": 12 * 60 * 60 * 1000, "1d": 24 * 60 * 60 * 1000, "3d": 3 * 24 * 60 * 60 * 1000, 
        "1w": 7 * 24 * 60 * 60 * 1000, "1M": 30 * 24 * 60 * 60 * 1000 
    }
    
    if interval not in interval_to_ms:
        logger.error(f"Intervalo {interval} não reconhecido. Adicione-o ao 'interval_to_ms'.")
        return pd.DataFrame()

    while True:
        logger.info(f"Buscando klines para {symbol} de {datetime.fromtimestamp(current_start_ts / 1000)}...")
        
        try:
            klines = client.get_historical_klines(
                symbol, interval, current_start_ts, limit=1000
            )

        except Exception as e:
            logger.error(f"Erro ao buscar klines da API: {e}")
            break 

        if not klines:
            logger.info("Nenhum dado retornado ou final da série de dados. Finalizando coleta.")
            break

        all_klines.extend(klines)
        
        last_klines_open_time = klines[-1][0] 
        current_start_ts = last_klines_open_time + interval_to_ms[interval]

        if end_ts and current_start_ts >= end_ts:
            logger.info("Período final do backtest atingido. Finalizando coleta de dados.")
            break

    if not all_klines:
        logger.error("Não foi possível coletar dados históricos. Verifique o símbolo, intervalo ou período.")
        return pd.DataFrame()

    df = pd.DataFrame(all_klines, columns=[
        'Open time', 'Open', 'High', 'Low', 'Close', 'Volume',
        'Close time', 'Quote asset volume', 'Number of trades',
        'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'
    ])

    df['Open time'] = pd.to_datetime(df['Open time'], unit='ms')
    df.set_index('Open time', inplace=True)
    
    numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume', 
                    'Quote asset volume', 'Taker buy base asset volume', 
                    'Taker buy quote asset volume']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col])

    logger.info(f"Coleta de dados concluída. Total de {len(df)} velas para {symbol}.")
    return df

def save_dataframe_to_csv(df, symbol, interval):
    """Salva um DataFrame de klines em um arquivo CSV."""
    file_path = os.path.join(DATA_DIR, f"{symbol}_{interval}_historical.csv")
    df.to_csv(file_path)
    logger.info(f"Dados salvos em {file_path}")

def load_dataframe_from_csv(symbol, interval):
    """Carrega um DataFrame de klines de um arquivo CSV."""
    file_path = os.path.join(DATA_DIR, f"{symbol}_{interval}_historical.csv")
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path, index_col='Open time', parse_dates=True)
            logger.info(f"Dados carregados de {file_path}")
            return df
        except Exception as e:
            logger.error(f"Erro ao carregar CSV {file_path}: {e}")
            return pd.DataFrame()
    else:
        logger.warning(f"Arquivo de dados históricos não encontrado: {file_path}")
        return pd.DataFrame()

# Exemplo de uso (apenas para teste direto do data_manager)
if __name__ == '__main__':
    logging.basicConfig(level=settings.LOG_LEVEL,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[
                            logging.FileHandler(os.path.join(settings.LOG_DIR, settings.LOG_FILE)), 
                            logging.StreamHandler()
                        ])
    logger.info("Data Manager test run.")
    
    df_test = get_historical_klines(settings.SYMBOL, settings.INTERVAL, settings.START_DATE, settings.END_DATE)
    if not df_test.empty:
        print(f"Primeiras 5 linhas dos dados coletadas:\n{df_test.head()}")
        print(f"Últimas 5 linhas dos dados coletadas:\n{df_test.tail()}")
        print(f"Total de velas coletadas: {len(df_test)}")
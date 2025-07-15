import logging
from binance.client import Client
from binance_utils import BinanceClient # Importe sua classe BinanceClient
from datetime import datetime

# Configuração de logging (igual ao settings para ver o DEBUG)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_historical_klines():
    print("Iniciando teste de klines históricos...")
    client = BinanceClient()

    symbol = "BTCUSDT"
    interval = Client.KLINE_INTERVAL_1DAY
    
    # Datas que você está usando
    start_date_str = "01 Jan, 2024"
    end_date_str = "31 Mar, 2024"

    try:
        start_timestamp_ms = int(datetime.strptime(start_date_str, "%d %b, %Y").timestamp() * 1000)
        end_timestamp_ms = int(datetime.strptime(end_date_str, "%d %b, %Y").timestamp() * 1000)
    except ValueError as e:
        logging.error(f"Erro ao converter datas: {e}")
        return

    print(f"Tentando baixar klines para {symbol} de {start_timestamp_ms} a {end_timestamp_ms}")

    # Chame o get_historical_klines da sua classe BinanceClient
    klines = client.get_historical_klines(symbol, interval, str(start_timestamp_ms), str(end_timestamp_ms))

    if klines:
        print(f"SUCESSO! Baixados {len(klines)} klines.")
        # Opcional: imprimir as primeiras e últimas velas para verificar
        print("Primeira vela:", klines[0])
        print("Última vela:", klines[-1])
    else:
        print("FALHA! Nenhum kline foi baixado. Verifique os logs acima para erros da API.")

if __name__ == "__main__":
    test_historical_klines()
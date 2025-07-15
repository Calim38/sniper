# get_usdt_pairs.py
import requests
import logging

# Configuração básica de logging para este script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_all_usdt_pairs(testnet=True):
    """
    Obtém uma lista de todos os pares de negociação com USDT como moeda base
    e que estão em status 'TRADING' (negociáveis).
    """
    base_url = "https://testnet.binance.vision" if testnet else "https://api.binance.com"
    endpoint = "/api/v3/exchangeInfo"
    url = f"{base_url}{endpoint}"

    logging.info(f"Buscando informações de câmbio em: {url}")

    try:
        response = requests.get(url)
        response.raise_for_status() # Lança um HTTPError para status de erro (4xx ou 5xx)
        data = response.json()
        
        usdt_pairs = []
        for symbol_info in data['symbols']:
            # Verifica se a moeda de cotação é USDT e se o status é 'TRADING'
            if symbol_info['quoteAsset'] == 'USDT' and symbol_info['status'] == 'TRADING':
                usdt_pairs.append(symbol_info['symbol'])
        
        logging.info(f"Encontrados {len(usdt_pairs)} pares USDT negociáveis.")
        return usdt_pairs
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao obter pares USDT da Binance: {e}")
        return []
    except Exception as e:
        logging.error(f"Erro inesperado ao processar pares USDT: {e}")
        return []

if __name__ == "__main__":
    # Altere para False se quiser pegar os pares da Binance real
    all_usdt_symbols = get_all_usdt_pairs(testnet=True)
    
    if all_usdt_symbols:
        print("\n--- Lista de Pares USDT Negociáveis (para copiar para settings.py) ---")
        print("TRADE_SYMBOLS = [")
        for symbol in all_usdt_symbols:
            print(f"    \"{symbol}\",")
        print("]")
        print("\n--- Fim da Lista ---")
    else:
        print("Não foi possível obter a lista de pares USDT.")
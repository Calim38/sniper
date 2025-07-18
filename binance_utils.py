import hashlib
import hmac
import time
import requests
import logging
import pandas as pd
import settings # Importar settings para acessar as configurações

class BinanceClient:
    def __init__(self):
        # As chaves são carregadas do ambiente (pelo settings.py que chamou load_dotenv)
        self.api_key = settings.API_KEY
        self.api_secret = settings.API_SECRET
        
        # Seleciona a URL base com base no modo de teste
        self.base_url = settings.TESTNET_BASE_URL if settings.TESTNET_MODE else settings.BASE_URL
        
        # Validação das chaves
        if not self.api_key or not self.api_secret:
            logging.error("Chaves API da Binance (BINANCE_API_KEY, BINANCE_API_SECRET) não encontradas nas variáveis de ambiente. Verifique seu arquivo .env.")
            raise ValueError("Chaves API da Binance ausentes.")

        logging.info(f"BinanceClient inicializado com base URL: {self.base_url}")

    def _get_server_time(self):
        """Obtém o tempo do servidor da Binance para evitar erros de timestamp."""
        try:
            response = requests.get(f"{self.base_url}/api/v3/time")
            response.raise_for_status()
            return response.json()['serverTime']
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro ao obter tempo do servidor da Binance: {e}")
            return None

    def _create_signature(self, params):
        """Cria a assinatura HMAC SHA256 para requisições autenticadas."""
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        m = hmac.new(self.api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
        return m.hexdigest()

    def _send_signed_request(self, http_method, path, params=None):
        """Envia uma requisição AUTENTICADA para a API da Binance."""
        if params is None:
            params = {}

        server_time = self._get_server_time()
        if server_time is None:
            return None 

        params['timestamp'] = server_time
        params['recvWindow'] = 60000 # Aumentei para 60 segundos conforme sugerido anteriormente

        signature = self._create_signature(params)
        params['signature'] = signature

        headers = {
            'X-MBX-APIKEY': self.api_key
        }

        url = f"{self.base_url}{path}"
        try:
            if http_method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif http_method == 'POST':
                response = requests.post(url, headers=headers, data=params)
            elif http_method == 'PUT':
                response = requests.put(url, headers=headers, data=params)
            elif http_method == 'DELETE':
                response = requests.delete(url, headers=headers, params=params)
            else:
                raise ValueError("Método HTTP não suportado")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"Erro HTTP ao enviar requisição AUTENTICADA para {path}: {http_err} para url: {response.url}")
            return None
        except requests.exceptions.RequestException as req_err:
            logging.error(f"Erro de requisição ao enviar requisição AUTENTICADA para {path}: {req_err}")
            return None

    def get_account_balance(self, asset='USDT'):
        """Obtém o saldo de um ativo específico da conta. REQUER AUTENTICAÇÃO."""
        path = "/api/v3/account"
        response_data = self._send_signed_request('GET', path)

        if response_data:
            for balance in response_data.get('balances', []):
                if balance['asset'] == asset:
                    logging.info(f"Saldo de {asset} obtido: {float(balance['free']):.4f}")
                    return float(balance['free'])
        logging.error(f"Erro ao obter saldo da conta ({asset}): {response_data}")
        return None

    def get_klines(self, symbol, interval, limit=500):
        """
        Obtém dados históricos de Klines (velas).
        ESTE É UM ENDPOINT PÚBLICO - NÃO REQUER AUTENTICAÇÃO/ASSINATURA.
        """
        path = "/api/v3/klines"
        url = f"{self.base_url}{path}"
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        try:
            # Requisição GET simples, sem cabeçalhos ou assinatura, pois é público
            response = requests.get(url, params=params)
            response.raise_for_status() # Lança um HTTPError para status de erro (4xx ou 5xx)
            
            response_data = response.json()
            if not response_data: # Se a lista de klines estiver vazia
                logging.warning(f"Nenhum kline retornado para {symbol} com intervalo {interval}.")
                return None

            # Processar os klines para um DataFrame do Pandas para facilitar o cálculo dos indicadores
            df = pd.DataFrame(response_data, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            df['open'] = pd.to_numeric(df['open'])
            df['high'] = pd.to_numeric(df['high'])
            df['low'] = pd.to_numeric(df['low'])
            df['close'] = pd.to_numeric(df['close'])
            df['volume'] = pd.to_numeric(df['volume'])
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
            
            return df
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"Erro HTTP ao obter klines para {symbol} ({interval}): {http_err} - URL: {response.url}")
            return None
        except requests.exceptions.RequestException as req_err:
            logging.error(f"Erro de requisição ao obter klines para {symbol} ({interval}): {req_err}")
            return None
        except Exception as e:
            logging.error(f"Erro inesperado ao processar klines para {symbol}: {e}")
            return None

    def create_order(self, symbol, side, type, quantity, price=None, stopPrice=None):
        """Cria uma ordem de Spot. REQUER AUTENTICAÇÃO."""
        path = "/api/v3/order"
        params = {
            'symbol': symbol,
            'side': side, # 'BUY' ou 'SELL'
            'type': type, # 'LIMIT', 'MARKET', 'STOP_LOSS', 'TAKE_PROFIT', etc.
            'quantity': quantity
        }
        if type == 'LIMIT' and price:
            params['price'] = f"{price:.8f}" # Formata para string com precisão
            params['timeInForce'] = 'GTC' # Good Till Cancelled
        if type in ['STOP_LOSS', 'TAKE_PROFIT'] and stopPrice:
            params['stopPrice'] = f"{stopPrice:.8f}"

        response_data = self._send_signed_request('POST', path, params)
        if response_data:
            logging.info(f"Ordem criada: {response_data}")
            return response_data
        logging.error(f"Erro ao criar ordem para {symbol}: {response_data}")
        return None
    
    def get_open_orders(self, symbol=None):
        """Obtém todas as ordens abertas para um símbolo específico ou todos os símbolos. REQUER AUTENTICAÇÃO."""
        path = "/api/v3/openOrders"
        params = {'symbol': symbol} if symbol else {}
        response_data = self._send_signed_request('GET', path, params)
        if response_data:
            return response_data
        logging.error(f"Erro ao obter ordens abertas para {symbol if symbol else 'todos os símbolos'}: {response_data}")
        return []

    def cancel_order(self, symbol, orderId):
        """Cancela uma ordem existente. REQUER AUTENTICAÇÃO."""
        path = "/api/v3/order"
        params = {
            'symbol': symbol,
            'orderId': orderId
        }
        response_data = self._send_signed_request('DELETE', path, params)
        if response_data:
            logging.info(f"Ordem {orderId} cancelada: {response_data}")
            return response_data
        logging.error(f"Erro ao cancelar ordem {orderId} para {symbol}: {response_data}")
        return None

    def get_usdt_pairs(self, min_volume_24h=1000000):
        """Obtém a lista de todos os pares USDT negociáveis na Binance com volume mínimo."""
        path = "/api/v3/ticker/24hr"
        url = f"{self.base_url}{path}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            usdt_pairs = [
                item['symbol'] for item in data
                if item['symbol'].endswith('USDT') and float(item['quoteVolume']) >= min_volume_24h
            ]
            logging.info(f"Encontrados {len(usdt_pairs)} pares USDT com volume >= {min_volume_24h}.")
            return usdt_pairs
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro ao obter pares USDT da Binance: {e}")
            return []
        except Exception as e:
            logging.error(f"Erro inesperado ao processar pares USDT: {e}")
            return []
import logging
import os
from datetime import datetime
import settings # Para acessar LOG_DIR, LOG_FILE, LOG_LEVEL

class BotLogger:
    _instance = None # Para garantir que haja apenas uma instância do logger (Singleton)

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(BotLogger, cls).__new__(cls)
        return cls._instance

    def __init__(self, name='CryptoBot', level=None):
        # Impedir que o __init__ configure o logger múltiplas vezes
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._initialized = True
        self.logger = logging.getLogger(name)

        # Se o nível não for especificado, usa o do settings.py
        if level is None:
            self.logger.setLevel(settings.LOG_LEVEL)
        else:
            self.logger.setLevel(level)

        # Evita que os logs sejam propagados para o logger raiz (para evitar duplicação)
        self.logger.propagate = False 

        # Limpa handlers existentes para evitar duplicação em execuções repetidas
        # Isso é crucial ao reexecutar o backtest sem reiniciar o ambiente
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # Criar um formato para os logs
        # Adicionei %(name)s para saber de qual parte do bot o log veio
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Garante que o diretório de logs exista
        if not os.path.exists(settings.LOG_DIR):
            os.makedirs(settings.LOG_DIR)

        # Criar um handler para registrar os logs em um arquivo
        # Usando um nome de arquivo único com timestamp para cada execução
        log_file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{settings.LOG_FILE}"
        file_handler = logging.FileHandler(os.path.join(settings.LOG_DIR, log_file_name))
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Criar um handler para registrar os logs na console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Métodos para cada nível de log
    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def critical(self, message):
        self.logger.critical(message)
    
    def debug(self, message): # Adicionando o nível DEBUG
        self.logger.debug(message)

# Função auxiliar para obter a instância do logger em qualquer lugar
def get_bot_logger(name='CryptoBot'):
    return BotLogger(name).logger

# Exemplo de uso (para testar a classe isoladamente)
if __name__ == '__main__':
    # Este bloco só será executado se você rodar 'python utils/logger_setup.py' diretamente
    # Para testes, defina LOG_LEVEL e LOG_DIR aqui ou crie um settings.py temporário
    class MockSettings:
        LOG_LEVEL = logging.DEBUG
        LOG_DIR = 'logs_temp'
        LOG_FILE = 'bot_test.log'

    settings = MockSettings() # Substitui o settings real para o teste isolado

    logger = get_bot_logger('TestLogger')
    logger.info('Iniciando o bot de teste.')
    logger.debug('Esta é uma mensagem de depuração.')
    logger.warning('Aviso: o bot de teste está configurado para operar em modo de teste.')
    logger.error('Erro: não foi possível simular conexão à API da Binance no teste.')
    logger.critical('Erro crítico: o bot de teste está parando de funcionar devido a um erro grave.')
    print(f"Verifique a pasta '{settings.LOG_DIR}' para o arquivo de log gerado.")
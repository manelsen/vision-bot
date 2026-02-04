"""
Script de Entrada (Bootstrap) da Amélie 👁️🌸

Este módulo é responsável por:
1. Carregar variáveis de ambiente (.env).
2. Inicializar a infraestrutura de segurança (Blindagem Fernet).
3. Montar a Arquitetura Hexagonal (Orquestração de Portas e Adaptadores).
4. Configurar e iniciar o Loop de Eventos Assíncrono para o Bot do Telegram.
5. Garantir o Graceful Shutdown (Desligamento Gentil) para preservar a integridade das tarefas.
"""

import os
import logging
from dotenv import load_dotenv, set_key
from cryptography.fernet import Fernet
from core.service import VisionService
from adapters.vision.gemini_adapter import GeminiAdapter
from adapters.messaging.telegram_adapter import TelegramAdapter
from adapters.security.fernet_adapter import FernetSecurityAdapter
from adapters.persistence.sqlite_adapter import SQLitePersistenceAdapter

# Configuração de log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Launcher")

def setup_security_key():
    key = os.getenv("SECURITY_KEY")
    if not key:
        new_key = Fernet.generate_key().decode()
        if os.path.exists(".env"):
            set_key(".env", "SECURITY_KEY", new_key)
        return new_key
    return key

def main():
    load_dotenv()
    
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    SECURITY_KEY = setup_security_key()

    if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
        logger.error("Configurações faltando no ambiente.")
        return

    # Arquitetura Hexagonal
    ai_model = GeminiAdapter(api_key=GEMINI_API_KEY)
    security = FernetSecurityAdapter(key=SECURITY_KEY)
    persistence = SQLitePersistenceAdapter(db_path="bot_data.db")
    
    service = VisionService(ai_model=ai_model, security=security, persistence=persistence)
    bot = TelegramAdapter(token=TELEGRAM_TOKEN, vision_service=service)

    logger.info("Amélie está acordando...")
    
    # Registra os handlers
    bot.start()
    
    # O run_polling() do python-telegram-bot já trata SIGINT/SIGTERM 
    # e faz o shutdown gentil de todos os componentes automaticamente.
    bot.app.run_polling(drop_pending_updates=True)
    
    logger.info("Amélie encerrou suas atividades com sucesso. 🌸")

if __name__ == "__main__":
    main()

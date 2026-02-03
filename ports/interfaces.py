from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class MessagingPort(ABC):
    """
    Interface para adaptadores de mensagens (ex: Telegram, Discord).
    
    Define os contratos básicos para envio de mensagens e inicialização do serviço.
    """
    @abstractmethod
    def start(self):
        """Inicia o serviço de escuta de mensagens."""
        pass

    @abstractmethod
    async def send_message(self, chat_id: str, text: str):
        """
        Envia uma mensagem de texto para um chat específico.
        
        Args:
            chat_id: Identificador único do chat.
            text: Conteúdo da mensagem.
        """
        pass

class AIModelPort(ABC):
    """
    Interface para adaptadores de modelos de Inteligência Artificial (ex: Gemini, GLM).
    
    Gerencia o ciclo de vida de arquivos e a geração de conteúdo multimodal.
    """
    @abstractmethod
    async def upload_file(self, content_bytes: bytes, mime_type: str) -> str:
        """
        Realiza o upload de um arquivo para o provedor de IA.
        
        Args:
            content_bytes: Conteúdo bruto do arquivo em bytes.
            mime_type: Tipo MIME do arquivo.
            
        Returns:
            str: URI ou identificador do arquivo no cache do provedor.
        """
        pass

    @abstractmethod
    async def ask_about_file(self, file_uri: str, mime_type: str, prompt: str, history: list = None) -> str:
        """
        Faz uma pergunta contextual sobre um arquivo previamente enviado.
        
        Args:
            file_uri: URI do arquivo no cache da IA.
            mime_type: Tipo do arquivo.
            prompt: Pergunta do usuário.
            history: Histórico da conversa (opcional).
            
        Returns:
            str: Resposta gerada pela IA.
        """
        pass

    @abstractmethod
    async def delete_file(self, file_uri: str):
        """
        Remove um arquivo do cache do provedor.
        
        Args:
            file_uri: URI do arquivo a ser deletado.
        """
        pass

class SecurityPort(ABC):
    """
    Interface para serviços de criptografia e segurança.
    """
    @abstractmethod
    def encrypt(self, plain_text: str) -> str:
        """
        Criptografa um texto puro.
        
        Args:
            plain_text: Texto a ser protegido.
            
        Returns:
            str: Texto cifrado (geralmente em Base64).
        """
        pass

    @abstractmethod
    def decrypt(self, cipher_text: str) -> str:
        """
        Descriptografa um texto cifrado.
        
        Args:
            cipher_text: Texto cifrado.
            
        Returns:
            str: Texto puro original.
        """
        pass

class PersistencePort(ABC):
    """
    Interface para adaptadores de banco de dados e armazenamento.
    """
    @abstractmethod
    async def save_session(self, chat_id: str, data: Dict[str, Any]):
        """
        Salva ou atualiza os dados de sessão de um usuário.
        
        Args:
            chat_id: ID do chat.
            data: Dicionário com os dados da sessão.
        """
        pass

    @abstractmethod
    async def get_session(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Recupera os dados de sessão de um usuário.
        
        Args:
            chat_id: ID do chat.
            
        Returns:
            Optional[Dict[str, Any]]: Dados da sessão ou None se não existir.
        """
        pass

    @abstractmethod
    async def clear_session(self, chat_id: str):
        """
        Remove permanentemente a sessão de um usuário.
        
        Args:
            chat_id: ID do chat.
        """
        pass

    @abstractmethod
    async def save_preference(self, chat_id: str, key: str, value: str):
        """
        Salva uma preferência de usuário (ex: modo curto/longo).
        
        Args:
            chat_id: ID do chat.
            key: Nome da preferência.
            value: Valor da preferência.
        """
        pass

    @abstractmethod
    async def get_preference(self, chat_id: str, key: str) -> Optional[str]:
        """
        Recupera uma preferência de usuário.
        
        Args:
            chat_id: ID do chat.
            key: Nome da preferência.
            
        Returns:
            Optional[str]: Valor salvo ou None.
        """
        pass

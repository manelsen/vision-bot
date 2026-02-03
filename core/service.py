import re
import logging
import asyncio
from typing import Dict, Any, Optional
from ports.interfaces import AIModelPort, SecurityPort, PersistencePort
from core.exceptions import transientAPIError, PermanentAPIError, NoContextError

# Configuração de logging global
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger("VisionService")

class VisionService:
    """
    Cérebro da aplicação Amélie (Core Service).
    
    Orquestra a lógica de negócio, gerencia filas de processamento,
    garante a acessibilidade das respostas e coordena a blindagem de dados.
    """

    def __init__(self, ai_model: AIModelPort, security: SecurityPort, persistence: PersistencePort):
        """
        Inicializa o serviço com seus respectivos componentes injetados.

        Args:
            ai_model (AIModelPort): Adaptador da IA.
            security (SecurityPort): Adaptador de criptografia.
            persistence (PersistencePort): Adaptador de banco de dados.
        """
        self.ai_model = ai_model
        self.security = security
        self.persistence = persistence
        self.queue = asyncio.Queue()
        self.worker_task = None

    def start_worker(self):
        """Inicia o processador de fila em background (Lazy Load)."""
        if self.worker_task is None:
            logger.info("Worker blindado da Amélie iniciado.")
            self.worker_task = asyncio.create_task(self._worker())

    async def _worker(self):
        """Processa pedidos um por um para evitar sobrecarga da API."""
        while True:
            request = await self.queue.get()
            chat_id, func, args, future = request
            try:
                result = await func(*args)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            finally:
                self.queue.task_done()
                await asyncio.sleep(0.5)

    def _clean_text_for_accessibility(self, text: str) -> str:
        """Remove caracteres de Markdown (*, #, _, `) para leitores de tela."""
        text = text.replace("*", "").replace("#", "").replace("_", " ").replace("`", "")
        text = re.sub(r' +', ' ', text)
        return text.strip()

    async def _enqueue_request(self, chat_id: str, func, *args):
        """Gerencia a entrada e espera de resultados na fila global."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self.queue.put((chat_id, func, args, future))
        return await future

    async def process_file_request(self, chat_id: str, content_bytes: bytes, mime_type: str) -> str:
        """
        Lida com um novo arquivo: faz upload, criptografa a URI e gera a análise inicial.

        Args:
            chat_id: ID do usuário.
            content_bytes: Arquivo recebido.
            mime_type: Tipo do arquivo.
        """
        logger.info(f"Recebido. Tipo: {mime_type} | Chat: {chat_id}")
        
        # Limpa sessão anterior se existir
        old_session = await self.persistence.get_session(chat_id)
        if old_session:
            old_uri = self.security.decrypt(old_session["uri"])
            asyncio.create_task(self.ai_model.delete_file(old_uri))

        # Upload e Criptografia
        file_uri = await self._enqueue_request(chat_id, self.ai_model.upload_file, content_bytes, mime_type)
        encrypted_uri = self.security.encrypt(file_uri)
        
        new_session = {
            "uri": encrypted_uri,
            "mime": mime_type,
            "history": []
        }
        await self.persistence.save_session(chat_id, new_session)
        
        # Determina prompt inicial baseado em preferências
        style = await self.persistence.get_preference(chat_id, "style") or "longo"
        
        if mime_type.startswith("image/"):
            prompt = "Descreva esta imagem de forma muito breve (200 letras)." if style == "curto" else "Descreva detalhadamente."
        elif mime_type.startswith("video/"):
            video_mode = await self.persistence.get_preference(chat_id, "video_mode") or "completo"
            prompt = "Crie legendas cronológicas." if video_mode == "legenda" else "Descreva detalhadamente o vídeo."
        elif mime_type.startswith("audio/"):
            prompt = "Transcreva e analise este áudio detalhadamente."
        elif mime_type == "application/pdf":
            prompt = "Resuma este PDF de forma simples."
        else:
            prompt = "Analise este documento."

        result = await self.process_question_request(chat_id, prompt)
        logger.info(f"Processado. Tipo: {mime_type}")
        return result

    async def process_question_request(self, chat_id: str, question: str) -> str:
        """Processa uma pergunta sobre o arquivo salvo no cache criptografado."""
        session = await self.persistence.get_session(chat_id)
        if not session:
            raise NoContextError("Sem contexto.")
        
        real_uri = self.security.decrypt(session["uri"])
        real_history = []
        for h in session.get("history", []):
            real_history.append({
                "role": h["role"],
                "parts": [self.security.decrypt(p) for p in h["parts"]]
            })

        logger.info(f"Pergunta sobre cache (Chat: {chat_id})")
        
        raw_result = await self._enqueue_request(
            chat_id, self.ai_model.ask_about_file, real_uri, session["mime"], question, real_history
        )

        clean_result = self._clean_text_for_accessibility(raw_result)
        
        # Salva histórico criptografado
        session["history"].append({"role": "user", "parts": [self.security.encrypt(question)]})
        session["history"].append({"role": "model", "parts": [self.security.encrypt(clean_result)]})
        
        await self.persistence.save_session(chat_id, session)
        return clean_result

    async def process_command(self, chat_id: str, command: str) -> str:
        """Gerencia comandos de sistema e preferências do usuário."""
        if command == "/ajuda":
            return "Amélie: Enviei mídias para audiodescrição ou documentos para análise. Comandos: /curto, /longo, /legenda, /completo."
        elif command == "/curto":
            await self.persistence.save_preference(chat_id, "style", "curto")
            return "Estilo: Curto definido."
        elif command == "/longo":
            await self.persistence.save_preference(chat_id, "style", "longo")
            return "Estilo: Longo definido."
        elif command == "/legenda":
            await self.persistence.save_preference(chat_id, "video_mode", "legenda")
            return "Vídeo: Modo legenda definido."
        elif command == "/completo":
            await self.persistence.save_preference(chat_id, "video_mode", "completo")
            return "Vídeo: Modo completo definido."
        return "Comando desconhecido."

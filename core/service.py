import re
import logging
import asyncio
from typing import Dict, Any, Optional
from ports.interfaces import AIModelPort, SecurityPort, PersistencePort
from core.exceptions import VisionBotError, transientAPIError, PermanentAPIError, NoContextError

# Configuração de logging profissional global para a Amélie
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
    Cérebro central da aplicação Amélie (Core Domain Service).
    
    Responsável por orquestrar a lógica multimodal, gerenciar filas de mensagens, 
    garantir a acessibilidade via limpeza de texto e aplicar blindagem criptográfica.
    
    Esta classe implementa o padrão de Worker Serializado para evitar condições de 
    corrida e garantir que cada mídia seja processada isoladamente, respeitando 
    os limites de taxa da API de IA.
    """

    def __init__(self, ai_model: AIModelPort, security: SecurityPort, persistence: PersistencePort):
        """
        Inicializa o serviço core com os adaptadores necessários.

        Args:
            ai_model (AIModelPort): Adaptador para comunicação com o modelo de IA (Gemini).
            security (SecurityPort): Adaptador para operações de segurança e criptografia.
            persistence (PersistencePort): Adaptador para armazenamento de preferências e termos.
        """
        self.ai_model = ai_model
        self.security = security
        self.persistence = persistence
        self.queue = asyncio.Queue()
        self.worker_task = None

    def start_worker(self):
        """
        Inicia o Worker de processamento serializado no loop de eventos.
        O Worker monitora a fila global e processa as requisições sequencialmente.
        """
        if self.worker_task is None:
            logger.info("Worker blindado da Amélie iniciado com sucesso.")
            self.worker_task = asyncio.create_task(self._worker())

    async def _worker(self):
        """
        Loop infinito do Worker que processa requisições uma por uma da fila global.
        Garante um intervalo de segurança entre processamentos para evitar erros 429.
        """
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
        """
        Sanitiza o texto removendo caracteres especiais de Markdown que podem 
        atrapalhar a leitura por softwares de apoio (Screen Readers).

        Args:
            text (str): Texto bruto retornado pela IA.

        Returns:
            str: Texto limpo e linear para melhor acessibilidade.
        """
        text = text.replace("*", "").replace("#", "").replace("_", " ").replace("`", "")
        text = re.sub(r' +', ' ', text)
        return text.strip()

    async def _enqueue_request(self, chat_id: str, func, *args):
        """
        Adiciona uma requisição à fila global e aguarda a conclusão via Future.

        Args:
            chat_id (str): Identificador do chat para rastreamento.
            func: Função assíncrona a ser executada pelo worker.
            *args: Argumentos para a função.

        Returns:
            Any: Resultado da função executada.
        """
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self.queue.put((chat_id, func, args, future))
        return await future

    async def process_file_request(self, chat_id: str, content_bytes: bytes, mime_type: str, user_prompt: Optional[str] = None) -> str:
        """
        Coordena o fluxo completo de processamento de um arquivo:
        1. Validação de termos.
        2. Upload seguro para o provedor de IA.
        3. Determinação do prompt baseado no tipo de mídia e preferências.
        4. Consulta à IA sem persistência de contexto (Privacidade Total).
        5. Limpeza de acessibilidade.
        6. Deleção imediata do arquivo remoto.

        Args:
            chat_id (str): ID do usuário.
            content_bytes (bytes): Conteúdo binário da mídia.
            mime_type (str): Tipo MIME detectado.
            user_prompt (str, optional): Texto enviado na legenda da mídia.

        Returns:
            str: Resposta final processada.
        """
        logger.info(f"Recebido arquivo. Tipo: {mime_type} | Chat: {chat_id}")
        
        if not await self.persistence.has_accepted_terms(chat_id):
            return "POR_FAVOR_ACEITE_TERMOS"

        # 1. Upload para o Google
        file_uri = await self._enqueue_request(chat_id, self.ai_model.upload_file, content_bytes, mime_type)
        
        try:
            # 2. Determinação do prompt
            if user_prompt:
                prompt = user_prompt
            else:
                style = await self.persistence.get_preference(chat_id, "style") or "longo"
                if mime_type.startswith("image/"):
                    prompt = "Descreva esta imagem de forma muito breve (200 letras)." if style == "curto" else "Descreva detalhadamente esta imagem para um cego."
                elif mime_type.startswith("video/"):
                    video_mode = await self.persistence.get_preference(chat_id, "video_mode") or "completo"
                    if video_mode == "legenda":
                        prompt = "Transcreva a faixa de áudio deste vídeo palavra por palavra (verbatim), criando uma legenda fiel ao que é dito."
                    else:
                        prompt = "Descreva este vídeo detalhadamente de forma cronológica para um cego."
                elif mime_type.startswith("audio/"):
                    prompt = "Transcreva este áudio palavra por palavra (verbatim). Não inclua descrições ambientais. Apenas o texto dito."
                elif mime_type == "application/pdf":
                    prompt = "Resuma este PDF de forma simples para um cego."
                else:
                    prompt = "Analise este documento e descreva seu conteúdo para uma pessoa cega."

            # 3. Consulta à IA (Histórico SEMPRE vazio: Amélie não mantém contexto após a resposta)
            raw_result = await self._enqueue_request(
                chat_id, self.ai_model.ask_about_file, file_uri, mime_type, prompt, []
            )

            clean_result = self._clean_text_for_accessibility(raw_result)
            logger.info(f"Processado com sucesso. Tipo: {mime_type}")
            return clean_result

        finally:
            # 4. Limpeza IMEDIATA do cache do Google para privacidade e economia
            asyncio.create_task(self.ai_model.delete_file(file_uri))

    async def process_command(self, chat_id: str, command: str) -> str:
        """
        Gerencia comandos do usuário.
        """
        if command == "/start":
            if await self.persistence.has_accepted_terms(chat_id):
                return "Olá! Sou a Amélie. Como posso ajudar hoje? Envie uma mídia para começar."
            return "LGPD_NOTICE"

        if command == "/ajuda":
            return (
                "Olá! Sou a Amélie, sua assistente de audiodescrição e acessibilidade. 👁️🌸\n\n"
                "Para me usar, envie uma foto, vídeo, áudio ou documento (PDF/MD).\n"
                "Se quiser perguntar algo específico sobre o arquivo, escreva o texto na legenda da mídia.\n\n"
                "Comandos:\n"
                "/curto - Imagem: Audiodescrição breve.\n"
                "/longo - Imagem: Audiodescrição detalhada.\n"
                "/legenda - Vídeo: Transcrição literal (verbatim) do áudio.\n"
                "/completo - Vídeo: Descrição visual detalhada.\n"
                "/ajuda - Mostra esta mensagem."
            )
        
        prefs = {"/curto": ("style", "curto"), "/longo": ("style", "longo"), 
                 "/legenda": ("video_mode", "legenda"), "/completo": ("video_mode", "completo")}
        
        if command in prefs:
            key, val = prefs[command]
            await self.persistence.save_preference(chat_id, key, val)
            if command == "/curto":
                return "O modo curto foi ativado. Audiodescrições de imagem serão breves."
            elif command == "/longo":
                return "O modo longo foi ativado. Audiodescrições de imagem serão detalhadas."
            elif command == "/legenda":
                return "O modo legenda foi ativado. Vou transcrever o áudio dos vídeos palavra por palavra."
            elif command == "/completo":
                return "O modo completo foi ativado. Vídeos serão descritos detalhadamente."
        
        return "Comando desconhecido. Digite /ajuda."

    async def accept_terms(self, chat_id: str):
        """Registra o consentimento do usuário."""
        await self.persistence.accept_terms(chat_id)

    def get_lgpd_text(self) -> str:
        """Retorna o manifesto de privacidade."""
        return (
            "Olá, eu sou a Amélie! 👁️🌸\n\n"
            "Privacidade em 1º lugar: Seus arquivos são processados e deletados imediatamente após a resposta. "
            "Nenhum dado de imagem ou vídeo é armazenado de forma persistente ou acessível por humanos.\n\n"
            "Ao clicar no botão abaixo, você concorda com estes termos."
        )

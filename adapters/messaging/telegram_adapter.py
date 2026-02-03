from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
import logging
import asyncio
from ports.interfaces import MessagingPort
from core.service import VisionService
from core.exceptions import NoContextError

logger = logging.getLogger("TelegramAdapter")

class TelegramAdapter(MessagingPort):
    """
    Adaptador para a plataforma Telegram utilizando python-telegram-bot.
    
    Gerencia a recepção de mídias, textos e comandos, coordenando
    o download e o envio de respostas para o usuário.
    """

    def __init__(self, token: str, vision_service: VisionService):
        """
        Inicializa a aplicação do Telegram.

        Args:
            token (str): Token do bot fornecido pelo BotFather.
            vision_service (VisionService): Instância do serviço core.
        """
        self.token = token
        self.vision_service = vision_service
        self.app = ApplicationBuilder().token(token).read_timeout(30).write_timeout(30).build()
        
        self.supported_mimetypes = {
            "image/jpeg": "image/jpeg", "image/png": "image/png", "image/webp": "image/webp",
            "application/pdf": "application/pdf", "text/markdown": "text/markdown",
            "video/mp4": "video/mp4",
            "audio/mpeg": "audio/mpeg", "audio/mp3": "audio/mpeg", 
            "audio/ogg": "audio/ogg", "audio/wav": "audio/wav", "audio/x-wav": "audio/wav",
            "audio/webm": "audio/webm", "audio/flac": "audio/flac", "audio/aac": "audio/aac"
        }

    async def _handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processa comandos de barra (ex: /ajuda, /curto)."""
        chat_id = str(update.effective_chat.id)
        command = update.message.text.split()[0].lower()
        result = await self.vision_service.process_command(chat_id, command)
        await update.message.reply_text(result)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handler central para todas as mensagens (mídia e texto).
        
        Identifica o tipo de conteúdo, baixa arquivos se necessário e
        encaminha para o VisionService via fila de processamento.
        """
        # Inicia o worker assíncrono se for o primeiro contato
        self.vision_service.start_worker()
        
        if not update.message: return
        message = update.message
        chat_id = str(update.effective_chat.id)

        file_to_download = None
        mime_type = None

        # Roteamento baseado no tipo de mensagem
        if message.photo:
            file_to_download = await message.photo[-1].get_file()
            mime_type = "image/jpeg"
        elif message.video:
            file_to_download = await message.video.get_file()
            mime_type = message.video.mime_type or "video/mp4"
        elif message.voice:
            file_to_download = await message.voice.get_file()
            mime_type = message.voice.mime_type or "audio/ogg"
        elif message.audio:
            file_to_download = await message.audio.get_file()
            mime_type = message.audio.mime_type or "audio/mpeg"
        elif message.document:
            raw_mime = message.document.mime_type
            file_name = message.document.file_name.lower()
            if raw_mime in self.supported_mimetypes:
                mime_type = self.supported_mimetypes[raw_mime]
            elif file_name.endswith(".md"): mime_type = "text/markdown"
            elif file_name.endswith(".pdf"): mime_type = "application/pdf"
            elif file_name.endswith(".mp4"): mime_type = "video/mp4"
            elif file_name.endswith((".mp3", ".wav", ".ogg", ".flac", ".aac")):
                if "audio" not in raw_mime: mime_type = "audio/mpeg" 
            if mime_type: file_to_download = await message.document.get_file()

        # Fluxo de processamento de arquivo
        if file_to_download:
            try:
                content_bytes = await file_to_download.download_as_bytearray()
                result = await self.vision_service.process_file_request(chat_id, bytes(content_bytes), mime_type)
                await self._send_long_message(update, result)
            except Exception as e:
                logger.error(f"Erro no processamento de arquivo: {e}", exc_info=True)
            return

        # Fluxo de pergunta textual (Contextual)
        if message.text:
            try:
                result = await self.vision_service.process_question_request(chat_id, message.text)
                await self._send_long_message(update, result)
            except NoContextError:
                await update.message.reply_text("Por favor, envie um arquivo primeiro para começarmos.")
            except Exception as e:
                logger.error(f"Erro na pergunta contextual: {e}", exc_info=True)

    async def _send_long_message(self, update: Update, text: str):
        """Divide mensagens longas (>4k chars) para respeitar limites do Telegram."""
        MAX_LENGTH = 4000
        for i in range(0, len(text), MAX_LENGTH):
            chunk = text[i:i + MAX_LENGTH]
            if chunk.strip(): await update.message.reply_text(chunk)

    def start(self):
        """Configura handlers e inicia o polling do bot."""
        # Registra comandos
        self.app.add_handler(CommandHandler(["ajuda", "curto", "longo", "legenda", "completo"], self._handle_command))
        
        # Registra mensagens gerais (Mídia + Texto puro)
        handler = MessageHandler(
            filters.PHOTO | filters.VIDEO | filters.VOICE | filters.AUDIO | filters.Document.ALL | filters.TEXT & (~filters.COMMAND), 
            self._handle_message
        )
        self.app.add_handler(handler)
        
        logger.info("Bot Amélie iniciado no Telegram.")
        self.app.run_polling()

    async def send_message(self, chat_id: str, text: str):
        """Envio direto de mensagem via API."""
        await self.app.bot.send_message(chat_id=chat_id, text=text)

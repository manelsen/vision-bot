from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler, CallbackQueryHandler
import telegram.error
import logging
import asyncio
from ports.interfaces import MessagingPort
from core.service import VisionService
from core.exceptions import NoContextError

logger = logging.getLogger("TelegramAdapter")

class TelegramAdapter(MessagingPort):
    """
    Adaptador para a plataforma Telegram (python-telegram-bot).
    
    Implementa a interface MessagingPort, traduzindo eventos do Telegram 
    (mensagens, fotos, documentos, comandos) para chamadas no VisionService 
    e vice-versa. Gerencia a detecção de tipos MIME e limites de tamanho de arquivo.
    """

    def __init__(self, token: str, vision_service: VisionService):
        """
        Inicializa a aplicação Telegram e configura os tipos de mídia suportados.

        Args:
            token (str): Token do bot fornecido pelo BotFather.
            vision_service (VisionService): Instância do serviço central.
        """
        self.token = token
        self.vision_service = vision_service
        self.app = ApplicationBuilder().token(token).read_timeout(30).write_timeout(30).build()
        
        self.MAX_FILE_SIZE = 20 * 1024 * 1024 
        
        self.supported_mimetypes = {
            "image/jpeg": "image/jpeg", "image/png": "image/png", 
            "image/webp": "image/webp", "image/heic": "image/heic", 
            "image/heif": "image/heif",
            "audio/wav": "audio/wav", "audio/x-wav": "audio/wav",
            "audio/mp3": "audio/mpeg", "audio/mpeg": "audio/mpeg",
            "audio/aac": "audio/aac", "audio/ogg": "audio/ogg",
            "audio/flac": "audio/flac", "audio/x-flac": "audio/flac",
            "audio/aiff": "audio/aiff", "audio/x-aiff": "audio/aiff",
            "video/mp4": "video/mp4", "video/mpeg": "video/mpeg",
            "video/quicktime": "video/quicktime", "video/x-msvideo": "video/x-msvideo",
            "video/x-flv": "video/x-flv", "video/webm": "video/webm",
            "video/x-ms-wmv": "video/x-ms-wmv", "video/3gpp": "video/3gpp",
            "application/pdf": "application/pdf",
            "text/plain": "text/plain",
            "text/markdown": "text/markdown",
            "text/html": "text/html",
            "text/csv": "text/csv",
            "text/xml": "text/xml"
        }

    async def _handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Processa comandos iniciados por '/' (ex: /start, /ajuda).
        Traduz comandos para ações ou alterações de preferências no VisionService.
        """
        chat_id = str(update.effective_chat.id)
        command = update.message.text.split()[0].lower()
        result = await self.vision_service.process_command(chat_id, command)
        
        if result == "LGPD_NOTICE":
            keyboard = [[InlineKeyboardButton("Concordo e Aceito", callback_data='accept_lgpd')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(self.vision_service.get_lgpd_text(), reply_markup=reply_markup)
        else:
            await update.message.reply_text(result)

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Gerencia cliques em botões Inline (Interações de Callback).
        Utilizado principalmente para aceitação dos termos de privacidade.
        """
        query = update.callback_query
        await query.answer()
        if query.data == 'accept_lgpd':
            chat_id = str(update.effective_chat.id)
            await self.vision_service.accept_terms(chat_id)
            await query.edit_message_text(text="Obrigada por confiar na Amélie! 🌸 Envie uma mídia com ou sem legenda para começar.")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handler central para todas as mensagens não-comando.
        Identifica o tipo de mídia, baixa o conteúdo e encaminha para processamento.
        Ignora textos puros para forçar o uso de mídias para audiodescrição.
        """
        self.vision_service.start_worker()
        if not update.message: return
        message = update.message
        chat_id = str(update.effective_chat.id)

        media_obj = None
        mime_type = None

        # Identificação de mídia
        if message.photo:
            media_obj = message.photo[-1]
            mime_type = "image/jpeg"
        elif message.video:
            media_obj = message.video
            mime_type = message.video.mime_type or "video/mp4"
        elif message.voice:
            media_obj = message.voice
            mime_type = message.voice.mime_type or "audio/ogg"
        elif message.audio:
            media_obj = message.audio
            mime_type = message.audio.mime_type or "audio/mpeg"
        elif message.sticker:
            if message.sticker.is_animated:
                await update.message.reply_text("Desculpe, stickers animados TGS não são suportados.")
                return
            media_obj = message.sticker
            mime_type = "video/webm" if message.sticker.is_video else "image/webp"
        elif message.document:
            raw_mime = message.document.mime_type
            file_name = message.document.file_name.lower()
            if raw_mime in self.supported_mimetypes: mime_type = self.supported_mimetypes[raw_mime]
            elif file_name.endswith(".md"): mime_type = "text/markdown"
            elif file_name.endswith(".pdf"): mime_type = "application/pdf"
            if mime_type: media_obj = message.document

        if media_obj:
            if media_obj.file_size > self.MAX_FILE_SIZE:
                await update.message.reply_text("Arquivo excede o limite de 20MB.")
                return
            try:
                # Pega o texto da legenda se houver
                caption = message.caption
                
                file_to_download = await media_obj.get_file()
                content_bytes = await file_to_download.download_as_bytearray()
                
                # Envia o arquivo e a legenda opcional
                result = await self.vision_service.process_file_request(chat_id, bytes(content_bytes), mime_type, caption)
                
                if result == "POR_FAVOR_ACEITE_TERMOS":
                    await update.message.reply_text("Aceite os termos da LGPD digitando /start antes de começar.")
                else:
                    await self._send_long_message(update, result)
            except telegram.error.BadRequest as e:
                if "File is too big" in str(e):
                    await update.message.reply_text("O Telegram impediu o download do arquivo.")
                else: logger.error(f"BadRequest: {e}")
            except Exception as e:
                logger.error(f"Erro no processamento: {e}", exc_info=True)
            return

        # Mensagens apenas de texto (sem mídia) são ignoradas com aviso
        if message.text and not message.text.startswith('/'):
            await update.message.reply_text(
                "A Amélie precisa de uma mídia para ajudar. 👁️🌸\n\n"
                "1. Envie uma foto, vídeo, áudio ou PDF.\n"
                "2. Se tiver uma pergunta, escreva-a na **legenda** do arquivo.\n\n"
                "Eu não consigo responder a perguntas enviadas separadamente."
            )

    async def _send_long_message(self, update: Update, text: str):
        """
        Divide mensagens longas em fragmentos menores para evitar o limite do Telegram 
        e garantir que leitores de tela processem o texto em partes navegáveis.
        """
        MAX_LENGTH = 4000
        for i in range(0, len(text), MAX_LENGTH):
            chunk = text[i:i + MAX_LENGTH]
            if chunk.strip(): await update.message.reply_text(chunk)

    async def _setup_commands(self):
        """Configura os comandos que aparecem no botão 'Menu' do Telegram."""
        commands = [
            BotCommand("start", "Iniciar Amélie e aceitar termos"),
            BotCommand("ajuda", "Manual de uso"),
            BotCommand("curto", "Audiodescrição breve"),
            BotCommand("longo", "Audiodescrição detalhada"),
            BotCommand("legenda", "Vídeo: Transcrição áudio"),
            BotCommand("completo", "Vídeo: Descrição visual")
        ]
        await self.app.bot.set_my_commands(commands)

    def start(self):
        """Inicia o bot e configura os handlers."""
        # Adiciona handlers de comandos
        self.app.add_handler(CommandHandler(["start", "ajuda", "curto", "longo", "legenda", "completo"], self._handle_command))
        
        # Adiciona handler de callback (botões)
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))
        
        # Adiciona handler de mensagens gerais (mídias, stickers e textos)
        self.app.add_handler(MessageHandler(
            filters.PHOTO | filters.VIDEO | filters.VOICE | filters.AUDIO | filters.Document.ALL | filters.Sticker.ALL | filters.TEXT & (~filters.COMMAND), 
            self._handle_message
        ))
        
        # Configura os comandos no menu do bot
        loop = asyncio.get_event_loop()
        loop.create_task(self._setup_commands())
        
        logger.info("Bot Amélie operando.")

    async def send_message(self, chat_id: str, text: str):
        await self.app.bot.send_message(chat_id=chat_id, text=text)

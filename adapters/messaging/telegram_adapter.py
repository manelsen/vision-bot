from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import logging
from ports.interfaces import MessagingPort
from core.service import VisionService
from core.exceptions import NoContextError

logger = logging.getLogger("TelegramAdapter")

class TelegramAdapter(MessagingPort):
    def __init__(self, token: str, vision_service: VisionService):
        self.token = token
        self.vision_service = vision_service
        self.app = ApplicationBuilder().token(token).build()
        
        self.supported_mimetypes = {
            "image/jpeg": "image/jpeg", "image/png": "image/png", "image/webp": "image/webp",
            "application/pdf": "application/pdf", "text/markdown": "text/markdown",
            "video/mp4": "video/mp4"
        }

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message: return
        message = update.message
        chat_id = str(update.effective_chat.id)

        # 1. Se for ARQUIVO (Foto, Vídeo, Doc)
        file_to_download = None
        mime_type = None

        if message.photo:
            file_to_download = await message.photo[-1].get_file()
            mime_type = "image/jpeg"
        elif message.video:
            file_to_download = await message.video.get_file()
            mime_type = message.video.mime_type or "video/mp4"
        elif message.document:
            raw_mime = message.document.mime_type
            file_name = message.document.file_name.lower()
            if raw_mime in self.supported_mimetypes: mime_type = self.supported_mimetypes[raw_mime]
            elif file_name.endswith(".md"): mime_type = "text/markdown"
            elif file_name.endswith(".pdf"): mime_type = "application/pdf"
            if mime_type: file_to_download = await message.document.get_file()

        if file_to_download:
            try:
                await update.message.reply_text(f"Lendo {mime_type.split('/')[-1]}... 🔄")
                content_bytes = await file_to_download.download_as_bytearray()
                result = await self.vision_service.process_file_request(chat_id, bytes(content_bytes), mime_type)
                await self._send_long_message(update, result)
            except Exception as e:
                await update.message.reply_text("Erro ao processar o arquivo.")
            return

        # 2. Se for APENAS TEXTO (Pergunta sobre o arquivo anterior)
        if message.text:
            try:
                await update.message.reply_text("Pensando... 🤔")
                result = await self.vision_service.process_question_request(chat_id, message.text)
                await self._send_long_message(update, result)
            except NoContextError:
                await update.message.reply_text("Por favor, envie uma imagem, vídeo ou PDF primeiro para começarmos.")
            except Exception as e:
                await update.message.reply_text("Houve um erro ao processar sua pergunta.")

    async def _send_long_message(self, update, text):
        MAX_LENGTH = 4000
        for i in range(0, len(text), MAX_LENGTH):
            chunk = text[i:i + MAX_LENGTH]
            if chunk.strip(): await update.message.reply_text(chunk)

    def start(self):
        # Escuta Fotos, Vídeos, Documentos E Mensagens de Texto
        handler = MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.TEXT, self._handle_message)
        self.app.add_handler(handler)
        logger.info("Bot iniciado com suporte a perguntas contextuais.")
        self.app.run_polling()

    async def send_message(self, chat_id: str, text: str):
        await self.app.bot.send_message(chat_id=chat_id, text=text)

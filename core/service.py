import re
import logging
from ports.interfaces import AIModelPort
from core.exceptions import VisionBotError, transientAPIError, PermanentAPIError, NoContextError

logger = logging.getLogger("VisionService")

class VisionService:
    def __init__(self, ai_model: AIModelPort):
        self.ai_model = ai_model
        # Memória de sessão: chat_id -> {file_bytes, mime_type, history}
        self.sessions = {}

    def _clean_text_for_accessibility(self, text: str) -> str:
        text = text.replace("*", "")
        text = text.replace("#", "")
        text = text.replace("_", " ")
        text = text.replace("`", "")
        text = re.sub(r' +', ' ', text)
        return text.strip()

    async def process_file_request(self, chat_id: str, content_bytes: bytes, mime_type: str) -> str:
        # Novo arquivo inicia uma nova sessão para aquele chat
        self.sessions[chat_id] = {
            "bytes": content_bytes,
            "mime": mime_type,
            "history": []
        }
        
        # Prompt inicial baseado no tipo
        if mime_type.startswith("image/"): prompt = "Descreva esta imagem para um cego."
        elif mime_type.startswith("video/"): prompt = "Descreva este vídeo cronologicamente para um cego."
        elif mime_type == "application/pdf": prompt = "Resuma este PDF de forma simples para um cego."
        else: prompt = "Analise este documento."

        return await self._ask_ai(chat_id, prompt)

    async def process_question_request(self, chat_id: str, question: str) -> str:
        if chat_id not in self.sessions:
            raise NoContextError("Nenhum arquivo enviado anteriormente.")
        
        return await self._ask_ai(chat_id, question)

    async def _ask_ai(self, chat_id: str, prompt: str) -> str:
        session = self.sessions[chat_id]
        
        try:
            # Instrução de acessibilidade sempre presente
            full_prompt = f"{prompt}. Responda em português, texto puro, sem qualquer markdown ou asteriscos."
            
            raw_result = await self.ai_model.process_content(
                session["bytes"], 
                session["mime"], 
                full_prompt,
                session["history"]
            )
            
            clean_result = self._clean_text_for_accessibility(raw_result)
            
            # Atualiza o histórico para manter o contexto da conversa
            session["history"].append({"role": "user", "parts": [prompt]})
            session["history"].append({"role": "model", "parts": [clean_result]})
            
            return clean_result

        except Exception as e:
            logger.error(f"Erro na sessão {chat_id}: {e}")
            raise e

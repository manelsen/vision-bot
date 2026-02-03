import re
import logging
from ports.interfaces import AIModelPort
from core.exceptions import VisionBotError, transientAPIError, PermanentAPIError

# Configuração básica de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Silenciar logs excessivos de bibliotecas externas
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

logger = logging.getLogger("VisionService")

class VisionService:
    def __init__(self, ai_model: AIModelPort):
        self.ai_model = ai_model

    def _clean_text_for_accessibility(self, text: str) -> str:
        text = text.replace("*", "")
        text = text.replace("#", "")
        text = text.replace("_", " ")
        text = text.replace("`", "")
        text = re.sub(r' +', ' ', text)
        return text.strip()

    async def process_file_request(self, content_bytes: bytes, mime_type: str) -> str:
        try:
            logger.info(f"Processando arquivo do tipo: {mime_type}")
            raw_result = await self.ai_model.process_content(content_bytes, mime_type)
            clean_result = self._clean_text_for_accessibility(raw_result)
            
            if mime_type.startswith("image/"):
                prefix = "Audiodescrição de imagem"
            elif mime_type.startswith("video/"):
                prefix = "Audiodescrição de vídeo"
            elif mime_type == "application/pdf":
                prefix = "Análise de PDF"
            else:
                prefix = "Análise de Documento"
                
            return f"{prefix}: {clean_result}"

        except transientAPIError as e:
            logger.warning(f"Erro temporário detectado: {e}")
            return "O sistema está um pouco instável no momento. Tentei processar três vezes, mas o servidor do Google não respondeu. Por favor, tente novamente em alguns instantes."
        
        except PermanentAPIError as e:
            logger.error(f"Erro permanente detectado: {e}")
            return "Desculpe, ocorreu um problema técnico na minha configuração que me impede de responder agora. Meu administrador já foi notificado."
        
        except Exception as e:
            logger.critical(f"Erro inesperado: {e}", exc_info=True)
            return "Ocorreu um erro inesperado ao processar seu arquivo. Por favor, tente novamente mais tarde."

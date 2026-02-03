from google import genai
from google.genai import types
from ports.interfaces import AIModelPort
from core.exceptions import transientAPIError, PermanentAPIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class GeminiAdapter(AIModelPort):
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash-lite"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(transientAPIError),
        reraise=True
    )
    async def process_content(self, content_bytes: bytes, mime_type: str, prompt: str, history: list = None) -> str:
        try:
            # Prepara o arquivo como Part
            content_part = types.Part.from_bytes(data=content_bytes, mime_type=mime_type)
            
            # Monta a lista de conteúdos: Arquivo + Prompt
            # O Gemini 2.0+ processa melhor quando o arquivo vem antes do prompt
            current_contents = [content_part, prompt]
            
            # Se houver histórico, poderíamos usar start_chat, mas enviar o arquivo 
            # recorrentemente com o histórico no contents é mais robusto para sessões curtas
            # sem precisar gerenciar 'file_ids' persistentes no Google Cloud.
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=current_contents,
                config=types.GenerateContentConfig(
                    system_instruction="Você é um assistente de audiodescrição e análise para pessoas cegas. Responda sempre em português, sem formatação markdown."
                )
            )
            return response.text
        except Exception as e:
            err_str = str(e).lower()
            if "quota" in err_str or "rate limit" in err_str:
                raise transientAPIError(f"Erro de cota: {e}")
            raise PermanentAPIError(f"Erro na API Gemini: {e}")

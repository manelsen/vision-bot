import io
import asyncio
from google import genai
from google.genai import types
from ports.interfaces import AIModelPort
from core.exceptions import transientAPIError, PermanentAPIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class GeminiAdapter(AIModelPort):
    """
    Adaptador para os modelos Google Gemini utilizando o SDK google-genai.
    
    Gerencia o ciclo de vida de arquivos na File API e a geração de conteúdo
    multimodal (imagem, vídeo, áudio e documentos).
    """

    def __init__(self, api_key: str):
        """
        Inicializa o cliente do Google Gemini.

        Args:
            api_key (str): Chave de API válida do Google AI Studio.
        """
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash-lite"

    async def upload_file(self, content_bytes: bytes, mime_type: str) -> str:
        """
        Faz upload do conteúdo para a File API do Google e aguarda o processamento.

        Args:
            content_bytes (bytes): Arquivo bruto.
            mime_type (str): Tipo MIME do arquivo.

        Returns:
            str: URI do arquivo no servidor do Google.

        Raises:
            PermanentAPIError: Se o upload ou o processamento remoto falharem.
        """
        try:
            file_io = io.BytesIO(content_bytes)
            
            # Upload usando cliente assíncrono
            file_metadata = await self.client.aio.files.upload(file=file_io, config={"mime_type": mime_type})
            
            # Aguarda o arquivo ficar 'ACTIVE' (Polling)
            while True:
                f = await self.client.aio.files.get(name=file_metadata.name)
                if f.state.name == "ACTIVE":
                    break
                elif f.state.name == "FAILED":
                    raise PermanentAPIError("O processamento do arquivo falhou no Google.")
                await asyncio.sleep(2)
            
            return file_metadata.uri
        except Exception as e:
            raise PermanentAPIError(f"Erro no upload para a File API: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(transientAPIError),
        reraise=True
    )
    async def ask_about_file(self, file_uri: str, mime_type: str, prompt: str, history: list = None) -> str:
        """
        Solicita ao Gemini uma análise sobre um arquivo referenciado por URI.

        Inclui histórico de chat e instruções de sistema para acessibilidade.
        A função utiliza retentativas automáticas para erros de rede ou cota.

        Args:
            file_uri (str): URI do arquivo (gs:// ou https://).
            mime_type (str): Tipo MIME para contexto do modelo.
            prompt (str): Pergunta ou instrução do usuário.
            history (list, optional): Histórico de turnos da conversa.

        Returns:
            str: Resposta textual da IA em português.

        Raises:
            transientAPIError: Erros de rede ou limite de cota (429).
            PermanentAPIError: Erros de autenticação ou configuração (404/401).
        """
        try:
            file_part = types.Part.from_uri(file_uri=file_uri, mime_type=mime_type)
            
            messages = []
            if history:
                for entry in history:
                    messages.append(types.Content(
                        role=entry["role"], 
                        parts=[types.Part.from_text(text=p) for p in entry["parts"]]
                    ))

            # Adiciona o arquivo apenas no último turno junto com o prompt atual
            messages.append(types.Content(
                role="user", 
                parts=[file_part, types.Part.from_text(text=prompt)]
            ))
            
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=messages,
                config=types.GenerateContentConfig(
                    system_instruction="Seu nome é Amélie. Você é uma assistente de audiodescrição e análise rigorosa para pessoas cegas. Responda sempre em português, texto puro, sem markdown ou asteriscos. Foque nos detalhes visuais do arquivo enviado."
                )
            )
            return response.text
        except Exception as e:
            err_str = str(e).lower()
            if "quota" in err_str or "rate limit" in err_str:
                raise transientAPIError(f"Erro de cota na API: {e}")
            raise PermanentAPIError(f"Erro na geração de conteúdo: {e}")

    async def delete_file(self, file_uri: str):
        """
        Remove o arquivo da infraestrutura do Google.

        Args:
            file_uri (str): URI completa do arquivo.
        """
        try:
            file_id = file_uri.split('/')[-1]
            await self.client.aio.files.delete(name=file_id)
        except:
            pass

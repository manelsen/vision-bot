from abc import ABC, abstractmethod

class MessagingPort(ABC):
    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    async def send_message(self, chat_id: str, text: str):
        pass

class AIModelPort(ABC):
    @abstractmethod
    async def process_content(self, content_bytes: bytes, mime_type: str, prompt: str, history: list = None) -> str:
        pass

from cryptography.fernet import Fernet
from ports.interfaces import SecurityPort

class FernetSecurityAdapter(SecurityPort):
    """
    Adaptador de segurança que utiliza criptografia simétrica AES-256 (Fernet).
    
    Garante que os dados salvos no banco de dados sejam ilegíveis para humanos
    ou outros processos, descriptografando-os apenas em tempo de execução.
    """

    def __init__(self, key: str):
        """
        Inicializa o motor de criptografia.

        Args:
            key (str): Chave Fernet (Base64) gerada previamente.
        """
        self.fernet = Fernet(key.encode())

    def encrypt(self, plain_text: str) -> str:
        """
        Criptografa uma string.

        Args:
            plain_text (str): Texto original.

        Returns:
            str: Token criptografado em formato string.
        """
        if not plain_text: return ""
        return self.fernet.encrypt(plain_text.encode()).decode()

    def decrypt(self, cipher_text: str) -> str:
        """
        Descriptografa um token Fernet.

        Args:
            cipher_text (str): Token criptografado.

        Returns:
            str: Texto original descriptografado.
        """
        if not cipher_text: return ""
        return self.fernet.decrypt(cipher_text.encode()).decode()

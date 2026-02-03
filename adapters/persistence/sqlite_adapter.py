import aiosqlite
import json
from typing import Optional, Dict, Any
from ports.interfaces import PersistencePort

class SQLitePersistenceAdapter(PersistencePort):
    """
    Adaptador de persistência que utiliza o banco de dados SQLite assíncrono.
    
    Responsável por armazenar dados de sessão e preferências de usuário de forma persistente.
    """

    def __init__(self, db_path: str):
        """
        Inicializa o caminho do arquivo de banco de dados.

        Args:
            db_path (str): Caminho para o arquivo .db.
        """
        self.db_path = db_path

    async def _init_db(self):
        """Cria as tabelas necessárias se não existirem."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    chat_id TEXT PRIMARY KEY,
                    data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS preferences (
                    chat_id TEXT,
                    key TEXT,
                    value TEXT,
                    PRIMARY KEY (chat_id, key)
                )
            ''')
            await db.commit()

    async def save_session(self, chat_id: str, data: Dict[str, Any]):
        """Salva a sessão em formato JSON na tabela 'sessions'."""
        await self._init_db()
        json_data = json.dumps(data)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT OR REPLACE INTO sessions (chat_id, data, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)',
                (chat_id, json_data)
            )
            await db.commit()

    async def get_session(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Recupera a sessão de um chat específico."""
        await self._init_db()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT data FROM sessions WHERE chat_id = ?', (chat_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return json.loads(row[0])
        return None

    async def clear_session(self, chat_id: str):
        """Remove a sessão de um chat."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('DELETE FROM sessions WHERE chat_id = ?', (chat_id,))
            await db.commit()

    async def save_preference(self, chat_id: str, key: str, value: str):
        """Salva uma preferência (ex: style=curto) do usuário."""
        await self._init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT OR REPLACE INTO preferences (chat_id, key, value) VALUES (?, ?, ?)',
                (chat_id, key, value)
            )
            await db.commit()

    async def get_preference(self, chat_id: str, key: str) -> Optional[str]:
        """Recupera o valor de uma preferência salva."""
        await self._init_db()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT value FROM preferences WHERE chat_id = ? AND key = ?', (chat_id, key)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
        return None

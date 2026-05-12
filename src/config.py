"""Configurações centralizadas do agente de marketing Mindsight."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT_DIR / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system_prompt.md"

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")

# Modelos
CLAUDE_MODEL    = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")

# Postgres / pgvector
DATABASE_URL   = os.getenv("DATABASE_URL")   # postgresql://user:pass@host:5432/db
TABLE_NAME     = os.getenv("TABLE_NAME", "documentos")

# Google Drive
GOOGLE_DRIVE_FOLDER_ID    = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")  # JSON como string

# Retrieval por categoria
RETRIEVAL_PLAN = {
    "brand":     2,   # tom de voz / brand book
    "modulos":   3,   # descrições de produto
    "conteudos": 2,   # exemplos e conteúdos aprovados
    "personas":  1,   # ICPs
    "geral":     2,   # contexto geral (fallback)
}
TOP_K_TOTAL    = sum(RETRIEVAL_PLAN.values())   # 10
MIN_SIMILARITY = 0.30

# Chunking
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 150

# Geração
MAX_TOKENS = 4096

# Sync do Drive
SYNC_ON_STARTUP = os.getenv("SYNC_ON_STARTUP", "false").lower() == "true"


def validate_config():
    missing = []
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if not DATABASE_URL:
        missing.append("DATABASE_URL")
    if missing:
        raise ValueError(
            f"Configure as seguintes variáveis de ambiente: {', '.join(missing)}"
        )
    return True

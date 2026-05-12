"""
Camada de retrieval: conecta no Postgres pgvector, gera embeddings via OpenAI,
indexa documentos e busca chunks por categoria para retrieval híbrido.
"""

import json
import psycopg2
import psycopg2.extras
from openai import OpenAI

from src import config


class EmbeddingClient:
    def __init__(self):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.EMBEDDING_MODEL

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        batch_size = 100
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.client.embeddings.create(input=batch, model=self.model)
            all_embeddings.extend([d.embedding for d in response.data])
        return all_embeddings


class KnowledgeBase:
    def __init__(self):
        self.embedder = EmbeddingClient()
        self.conn = psycopg2.connect(config.DATABASE_URL)
        self.conn.autocommit = True
        self._ensure_table()

    def _ensure_table(self):
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {config.TABLE_NAME} (
                    id BIGSERIAL PRIMARY KEY,
                    conteudo TEXT NOT NULL,
                    metadata JSONB,
                    embedding VECTOR(1536)
                );
            """)
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS {config.TABLE_NAME}_embedding_idx
                ON {config.TABLE_NAME} USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """)

    def count(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {config.TABLE_NAME};")
            return cur.fetchone()[0]

    def existing_sources(self) -> set[str]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT DISTINCT metadata->>'source' FROM {config.TABLE_NAME};"
            )
            return {row[0] for row in cur.fetchall() if row[0]}

    def existing_hashes(self) -> set[str]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT DISTINCT metadata->>'content_hash' FROM {config.TABLE_NAME};"
            )
            return {row[0] for row in cur.fetchall() if row[0]}

    def remove_by_source(self, source: str):
        with self.conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {config.TABLE_NAME} WHERE metadata->>'source' = %s;",
                (source,)
            )

    def add_chunks(self, chunks: list[str], metadatas: list[dict], _ids=None):
        if not chunks:
            return
        embeddings = self.embedder.embed(chunks)
        with self.conn.cursor() as cur:
            for chunk, meta, emb in zip(chunks, metadatas, embeddings):
                cur.execute(
                    f"INSERT INTO {config.TABLE_NAME} (conteudo, metadata, embedding) "
                    f"VALUES (%s, %s, %s)",
                    (chunk, json.dumps(meta), emb)
                )

    def search(self, query: str, top_k: int = None) -> list[dict]:
        """
        Retrieval híbrido por categoria:
        busca K chunks por categoria conforme RETRIEVAL_PLAN,
        garantindo diversidade de fontes na resposta.
        """
        top_k = top_k or config.TOP_K_TOTAL
        query_emb = self.embedder.embed([query])[0]
        emb_str = "[" + ",".join(str(x) for x in query_emb) + "]"

        all_hits = []
        seen_ids = set()

        for category, k in config.RETRIEVAL_PLAN.items():
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT id, conteudo, metadata,
                           1 - (embedding <=> %s::vector) AS similarity
                    FROM {config.TABLE_NAME}
                    WHERE metadata->>'category' = %s
                      AND 1 - (embedding <=> %s::vector) >= %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                """, (emb_str, category, emb_str, config.MIN_SIMILARITY, emb_str, k))

                rows = cur.fetchall()
                for row in rows:
                    if row["id"] not in seen_ids:
                        seen_ids.add(row["id"])
                        all_hits.append({
                            "text": row["conteudo"],
                            "metadata": row["metadata"],
                            "similarity": float(row["similarity"]),
                        })

        # Se alguma categoria não teve hits suficientes, complementa com busca geral
        if len(all_hits) < top_k:
            deficit = top_k - len(all_hits)
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT id, conteudo, metadata,
                           1 - (embedding <=> %s::vector) AS similarity
                    FROM {config.TABLE_NAME}
                    WHERE 1 - (embedding <=> %s::vector) >= %s
                      AND id != ALL(%s)
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                """, (emb_str, emb_str, config.MIN_SIMILARITY,
                      list(seen_ids) or [0], emb_str, deficit))
                for row in cur.fetchall():
                    if row["id"] not in seen_ids:
                        seen_ids.add(row["id"])
                        all_hits.append({
                            "text": row["conteudo"],
                            "metadata": row["metadata"],
                            "similarity": float(row["similarity"]),
                        })

        # Ordena por similaridade
        all_hits.sort(key=lambda x: x["similarity"], reverse=True)
        return all_hits


def format_context(hits: list[dict]) -> str:
    if not hits:
        return (
            "<materiais_mindsight>\n"
            "Nenhum material relevante encontrado na base de conhecimento.\n"
            "</materiais_mindsight>"
        )
    parts = ["<materiais_mindsight>"]
    for i, hit in enumerate(hits, 1):
        meta = hit["metadata"]
        source   = meta.get("source", "desconhecido")
        category = meta.get("category", "geral")
        sim      = hit["similarity"]
        parts.append(
            f"\n[trecho {i} | fonte: {source} | categoria: {category} | sim: {sim:.2f}]\n"
            f"{hit['text']}"
        )
    parts.append("\n</materiais_mindsight>")
    return "\n".join(parts)

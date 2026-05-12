"""
Orquestração do agente: carrega o system prompt, faz retrieval
híbrido por categoria a cada turno, injeta o contexto e chama o Claude.
"""

from anthropic import Anthropic

from src import config
from src.retrieval import KnowledgeBase, format_context


class MarketingAgent:
    def __init__(self):
        self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.kb = KnowledgeBase()
        self.system_prompt = config.SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

    def _build_retrieval_query(self, messages: list[dict]) -> str:
        user_messages = [m for m in messages if m["role"] == "user"]
        if not user_messages:
            return ""
        last_messages = user_messages[-2:]
        return " ".join(m["content"] for m in last_messages)

    def chat(self, messages: list[dict]) -> tuple[str, list[dict]]:
        query = self._build_retrieval_query(messages)
        hits  = self.kb.search(query) if query else []
        context_block = format_context(hits)

        messages_with_context = messages.copy()
        if messages_with_context and messages_with_context[-1]["role"] == "user":
            last = messages_with_context[-1]
            messages_with_context[-1] = {
                "role": "user",
                "content": (
                    f"{context_block}\n\n"
                    f"<pedido_do_usuario>\n{last['content']}\n</pedido_do_usuario>"
                ),
            }

        response = self.client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=config.MAX_TOKENS,
            system=self.system_prompt,
            messages=messages_with_context,
        )

        answer = response.content[0].text
        return answer, hits

    def kb_count(self) -> int:
        return self.kb.count()

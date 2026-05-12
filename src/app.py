"""
Interface Streamlit do Agente de Marketing Mindsight.
Rode com: streamlit run src/app.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from src import config
from src.agent import MarketingAgent

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agente Marketing Mindsight",
    page_icon="🎯",
    layout="wide",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

:root {
  --bg: #f7f5f0;
  --surface: #ffffff;
  --border: #e2ddd6;
  --accent: #c8502a;
  --accent-light: #f5ede9;
  --text: #1c1917;
  --muted: #78716c;
  --success: #16a34a;
  --tag-bg: #fef3c7;
  --tag-color: #92400e;
}

html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg) !important;
  font-family: 'DM Sans', sans-serif !important;
  color: var(--text) !important;
}

[data-testid="stHeader"] { display: none !important; }

.main .block-container {
  padding: 2rem 2.5rem !important;
  max-width: 1100px;
}

/* Sidebar */
[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { font-family: 'DM Sans', sans-serif !important; }

/* Chat messages */
[data-testid="stChatMessage"] {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  margin-bottom: 0.75rem !important;
  padding: 1rem 1.25rem !important;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
}

/* Chat input */
[data-testid="stChatInput"] textarea {
  background: var(--surface) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: 10px !important;
  font-family: 'DM Sans', sans-serif !important;
  color: var(--text) !important;
}
[data-testid="stChatInput"] textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(200,80,42,0.1) !important;
}

/* Buttons */
.stButton > button {
  background: var(--accent) !important;
  color: white !important;
  border: none !important;
  border-radius: 8px !important;
  font-family: 'DM Sans', sans-serif !important;
  font-weight: 500 !important;
}
.stButton > button:hover {
  background: #a8401e !important;
}

/* Metric */
[data-testid="stMetric"] {
  background: var(--accent-light) !important;
  border-radius: 8px !important;
  padding: 0.75rem 1rem !important;
  border: 1px solid #f0d0c5 !important;
}

/* Tags */
.tag {
  display: inline-block;
  background: var(--tag-bg);
  color: var(--tag-color);
  font-family: 'DM Mono', monospace;
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 20px;
  margin: 2px;
}

/* Source card */
.source-card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.6rem 0.9rem;
  margin-bottom: 0.4rem;
  font-size: 0.85rem;
}
</style>
""", unsafe_allow_html=True)


# ── Agent init ────────────────────────────────────────────────────────────────
@st.cache_resource
def load_agent():
    config.validate_config()
    return MarketingAgent()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎯 Agente Marketing\n**Mindsight**")
    st.caption("RAG + Claude para peças consistentes com a marca")
    st.divider()

    try:
        agent = load_agent()
        kb_size = agent.kb_count()
        st.metric("Chunks indexados", kb_size)
        if kb_size == 0:
            st.warning("Base de conhecimento vazia. Rode a sincronização com o Drive.")
    except ValueError as e:
        st.error(str(e))
        st.stop()

    st.divider()

    # Sincronização com Drive
    if config.GOOGLE_DRIVE_FOLDER_ID and config.GOOGLE_SERVICE_ACCOUNT_JSON:
        if st.button("🔄 Sincronizar Drive", use_container_width=True):
            from src.ingestion import get_drive_service, iter_documents_from_drive
            from src.ingestion import chunk_text

            with st.spinner("Lendo arquivos do Drive..."):
                try:
                    service = get_drive_service()
                    existing_hashes = agent.kb.existing_hashes()
                    stats = {"files": 0, "chunks": 0, "skipped": 0}

                    for doc in iter_documents_from_drive(service):
                        stats["files"] += 1
                        content_hash = doc["metadata"].get("content_hash")
                        if content_hash in existing_hashes:
                            stats["skipped"] += 1
                            continue
                        agent.kb.remove_by_source(doc["metadata"]["source"])
                        chunks = chunk_text(doc["text"])
                        if not chunks:
                            continue
                        metadatas = [{**doc["metadata"], "chunk_index": i} for i in range(len(chunks))]
                        agent.kb.add_chunks(chunks, metadatas)
                        stats["chunks"] += len(chunks)

                    st.success(
                        f"✅ {stats['files']} arquivos · "
                        f"{stats['chunks']} novos chunks · "
                        f"{stats['skipped']} sem alteração"
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro na sincronização: {e}")
    else:
        st.caption("Configure GOOGLE_DRIVE_FOLDER_ID e GOOGLE_SERVICE_ACCOUNT_JSON para habilitar sync.")

    st.divider()

    if st.button("🗑️ Limpar conversa", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()

    with st.expander("Como usar"):
        st.markdown("""
**Fluxo típico:**
1. Diga o tema ou cole uma frase-semente
2. O agente pergunta: canal, fase, módulo, estratégia
3. Confirme e ele gera a peça

**Atalho:** mande tudo de uma vez.
*"Post LinkedIn, fase comparação, módulo AVD, estratégia humana, sobre avaliação 360"*
        """)

    with st.expander("Parâmetros"):
        st.markdown("""
**Estratégia:** GEO | Humano
**Canal:** Blog · Instagram · TikTok · LinkedIn · YouTube
**Fase:** Descoberta · Comparação · Decisão · Validação
**Módulo:** Mindmatch · ATS · Clima · AVD · Talent · People Hub · Branding
        """)


# ── Chat ──────────────────────────────────────────────────────────────────────
st.markdown("## 🎯 Agente de Marketing Mindsight")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Renderiza histórico
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("hits"):
            with st.expander(f"📚 {len(msg['hits'])} materiais consultados"):
                for i, hit in enumerate(msg["hits"], 1):
                    meta = hit["metadata"]
                    cat  = meta.get("category", "geral")
                    sim  = hit["similarity"]
                    st.markdown(
                        f'<div class="source-card">'
                        f'<span class="tag">{cat}</span> '
                        f'<strong>{meta.get("source", "?")}</strong> '
                        f'<span style="color:var(--muted);font-size:0.8rem">sim: {sim:.2f}</span>'
                        f'<br><span style="color:var(--muted);font-size:0.82rem">'
                        f'{hit["text"][:250]}{"..." if len(hit["text"]) > 250 else ""}'
                        f'</span></div>',
                        unsafe_allow_html=True
                    )

# Input
if prompt := st.chat_input("Descreva a peça que quer gerar..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Consultando materiais e gerando..."):
            clean_messages = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ]
            answer, hits = agent.chat(clean_messages)

        st.markdown(answer)

        if hits:
            with st.expander(f"📚 {len(hits)} materiais consultados"):
                for i, hit in enumerate(hits, 1):
                    meta = hit["metadata"]
                    cat  = meta.get("category", "geral")
                    sim  = hit["similarity"]
                    st.markdown(
                        f'<div class="source-card">'
                        f'<span class="tag">{cat}</span> '
                        f'<strong>{meta.get("source", "?")}</strong> '
                        f'<span style="color:var(--muted);font-size:0.8rem">sim: {sim:.2f}</span>'
                        f'<br><span style="color:var(--muted);font-size:0.82rem">'
                        f'{hit["text"][:250]}{"..." if len(hit["text"]) > 250 else ""}'
                        f'</span></div>',
                        unsafe_allow_html=True
                    )

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "hits": hits,
    })

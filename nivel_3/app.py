"""
Interface conversacional para análise de clientes sinalizados (Nível 3, Trilha C).

O analista conversa com um agente que tem acesso às ferramentas de consulta.
A memória da conversa é mantida no session_state do Streamlit, já que o script
é reexecutado a cada interação.
"""

import os

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

import ferramentas
from contexto import (
    CAMINHO_ENV,
    aplicar_regras,
    carregar_e_tratar,
    montar_ranking,
    resumo_para_prompt,
)
from ferramentas import (
    comparar_clientes,
    historico_cliente,
    operacoes_do_dia,
    perfil_canal,
)

MODELO = 'gemini-3.1-flash-lite'

load_dotenv(CAMINHO_ENV)

st.set_page_config(page_title="Mesa de Triagem — PLD", page_icon="⬛", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@600&display=swap');

:root {
  --papel: #F7F6F3;
  --tinta: #1B2430;
  --ardosia: #4A5766;
  --linha: #D8D5CE;
  --alto: #B8452F;
  --medio: #A67C1F;
  --baixo: #4F6B57;
}

/* Cores explícitas em toda parte: o app não deve depender do tema do Streamlit */
.stApp, [data-testid="stAppViewContainer"] { background: var(--papel) !important; }
[data-testid="stHeader"] { background: transparent !important; }

body,
[data-testid="stAppViewContainer"] p,
[data-testid="stAppViewContainer"] div,
[data-testid="stAppViewContainer"] span,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] span {
  font-family: 'IBM Plex Sans', sans-serif;
  color: var(--tinta);
}

[data-testid="stSidebar"] {
  background: #EFEDE8 !important;
  border-right: 1px solid var(--linha);
}
[data-testid="stSidebar"] .block-container { padding-top: 2rem; }

/* Cabeçalho */
.cabecalho { border-bottom: 2px solid var(--tinta); padding-bottom: .75rem; margin-bottom: .5rem; }
.cabecalho h1 {
  font-family: 'IBM Plex Serif', serif !important; font-size: 1.9rem; font-weight: 600;
  margin: 0; letter-spacing: -.01em; color: var(--tinta) !important;
}
.cabecalho .sub {
  font-family: 'IBM Plex Mono', monospace !important; font-size: .7rem; text-transform: uppercase;
  letter-spacing: .14em; color: var(--ardosia) !important; margin-top: .3rem;
}

/* Rótulo de seção */
.rotulo {
  font-family: 'IBM Plex Mono', monospace !important; font-size: .68rem; text-transform: uppercase;
  letter-spacing: .16em; color: var(--ardosia) !important;
  border-bottom: 1px solid var(--linha); padding-bottom: .4rem; margin-bottom: .9rem;
}

/* Ficha do caso */
.ficha {
  background: #FFFFFF; border: 1px solid var(--linha); border-left: 3px solid var(--ardosia);
  padding: .6rem .7rem; margin-bottom: .5rem;
}
.ficha.alto  { border-left-color: var(--alto); }
.ficha.medio { border-left-color: var(--medio); }
.ficha.baixo { border-left-color: var(--baixo); }
.ficha .id {
  font-family: 'IBM Plex Mono', monospace !important; font-size: .85rem; font-weight: 600;
  letter-spacing: .02em; color: var(--tinta) !important;
}
.ficha .valor {
  font-family: 'IBM Plex Mono', monospace !important; font-size: .72rem;
  color: var(--ardosia) !important; margin-top: .1rem;
}
.ficha .marcas { margin-top: .4rem; display: flex; gap: .3rem; flex-wrap: wrap; }
.marca {
  font-family: 'IBM Plex Mono', monospace !important; font-size: .6rem; text-transform: uppercase;
  letter-spacing: .1em; padding: .12rem .35rem; border: 1px solid var(--linha);
  color: var(--ardosia) !important; background: var(--papel);
}

/* Carimbo de veredito */
.carimbo {
  display: inline-block; font-family: 'IBM Plex Mono', monospace !important; font-size: .58rem;
  font-weight: 600; text-transform: uppercase; letter-spacing: .18em;
  padding: .18rem .45rem; border: 1.5px solid currentColor; float: right;
}
.carimbo.alto  { color: var(--alto) !important; }
.carimbo.medio { color: var(--medio) !important; }
.carimbo.baixo { color: var(--baixo) !important; }

/* Rodapé de ferramentas consultadas */
.trilha {
  font-family: 'IBM Plex Mono', monospace !important; font-size: .65rem;
  color: var(--ardosia) !important; text-transform: uppercase; letter-spacing: .1em;
  border-top: 1px solid var(--linha); padding-top: .4rem; margin-top: .7rem;
}

/* Medidor de sessão */
.medidor {
  font-family: 'IBM Plex Mono', monospace !important; font-size: .68rem;
  color: var(--ardosia) !important; display: flex; justify-content: space-between;
  border-top: 1px solid var(--linha); padding-top: .5rem; margin-top: 1rem;
}

/* Sugestões de abertura */
.sugestoes {
  font-family: 'IBM Plex Mono', monospace !important; font-size: .78rem;
  color: var(--ardosia) !important; line-height: 1.9;
}

/* Mensagens do chat — cor aplicada só ao texto, para não quebrar os ícones */
[data-testid="stChatMessage"] {
  background: transparent !important;
  border-bottom: 1px solid var(--linha);
  border-radius: 0;
  padding: 1rem .25rem;
}
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li,
[data-testid="stChatMessage"] h1,
[data-testid="stChatMessage"] h2,
[data-testid="stChatMessage"] h3,
[data-testid="stChatMessage"] strong,
[data-testid="stChatMessage"] em {
  color: var(--tinta) !important;
}
[data-testid="stChatMessage"] code {
  background: #FFFFFF !important;
  color: var(--alto) !important;
  border: 1px solid var(--linha);
  font-family: 'IBM Plex Mono', monospace !important;
  padding: .05rem .3rem;
}
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
  background: var(--ardosia) !important;
}

/* Barra de entrada */
[data-testid="stBottomBlockContainer"] {
  background: var(--papel) !important;
  padding-bottom: 1.5rem;
}
[data-testid="stBottom"] > div { background: var(--papel) !important; }
[data-testid="stChatInput"] {
  background: #FFFFFF !important;
  border: 1px solid var(--linha) !important;
  border-radius: 0 !important;
  box-shadow: none !important;
}
[data-testid="stChatInput"] > div,
[data-testid="stChatInput"] > div > div {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
[data-testid="stChatInput"] textarea {
  background: transparent !important;
  color: var(--tinta) !important;
  border: none !important;
  box-shadow: none !important;
  font-family: 'IBM Plex Sans', sans-serif !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: var(--ardosia) !important; }
[data-testid="stChatInput"] button {
  background: transparent !important;
  color: var(--ardosia) !important;
  border: none !important;
}
[data-testid="stChatInput"] button:hover { color: var(--tinta) !important; }

/* Botão da barra lateral */
[data-testid="stSidebar"] button {
  background: #FFFFFF !important;
  border: 1px solid var(--linha) !important;
  color: var(--ardosia) !important;
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: .68rem !important; text-transform: uppercase; letter-spacing: .12em;
  border-radius: 0 !important;
}
[data-testid="stSidebar"] button:hover {
  border-color: var(--tinta) !important;
  color: var(--tinta) !important;
}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def carregar_contexto():
    """Carrega dados e regras uma vez só, reaproveitando entre reexecuções."""
    df, _ = carregar_e_tratar()
    df, agrupado = aplicar_regras(df)
    ranking = montar_ranking(df, agrupado)
    return ranking, resumo_para_prompt(ranking, agrupado)


def risco_pelas_regras(eventos_frac, eventos_atipico):
    """Mesmo critério do confronto.py: traduz as flags para a escala de risco."""
    if eventos_frac > 0:
        return 'alto'
    if eventos_atipico >= 2:
        return 'medio'
    return 'baixo'


ranking, resumo = carregar_contexto()

INSTRUCAO_SISTEMA = f"""Você é um assistente de análise para uma mesa de triagem de
prevenção à lavagem de dinheiro (PLD). Conversa com um analista humano sobre clientes
que foram sinalizados por regras determinísticas.

{resumo}

Você tem ferramentas para consultar a base de operações. Use apenas as necessárias
para responder ao que foi perguntado — o resumo acima já cobre quem está sinalizado
e por quê, então não precisa consultar ferramentas só para repetir essa informação.

Orientações sobre os dados:
- Valores com sufixo "_brl" já estão em reais.
- O campo "moeda_original" indica apenas a moeda de registro antes da conversão.
  Nunca combine o número de um campo "_brl" com esse rótulo.
- Os cálculos já foram feitos pelas ferramentas. Interprete os números, não recalcule.

Responda em português, de forma direta e objetiva. Quando o analista pedir um parecer
formal, estruture a resposta com nível de risco, tipologia suspeita, red flags e
justificativa. Nas demais conversas, responda naturalmente."""


def obter_client():
    """Mantém o client vivo no session_state.

    Se o client for local à função, ele é coletado como lixo depois que
    criar_chat() retorna, e a sessão de chat guardada aponta para uma
    conexão já fechada.
    """
    if 'client' not in st.session_state:
        st.session_state.client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))
    return st.session_state.client


def criar_chat():
    return obter_client().chats.create(
        model=MODELO,
        config=types.GenerateContentConfig(
            system_instruction=INSTRUCAO_SISTEMA,
            tools=[historico_cliente, operacoes_do_dia, perfil_canal, comparar_clientes],
        ),
    )


# --- Estado da sessão: mantém a memória da conversa entre reexecuções ---
if 'chat' not in st.session_state:
    st.session_state.chat = criar_chat()
if 'mensagens' not in st.session_state:
    st.session_state.mensagens = []
if 'tokens_acumulados' not in st.session_state:
    st.session_state.tokens_acumulados = 0
if 'consultas' not in st.session_state:
    st.session_state.consultas = 0

# --- Painel lateral: o que a regra determinística apurou ---
with st.sidebar:
    st.markdown('<div class="rotulo">Casos em triagem</div>', unsafe_allow_html=True)

    for cliente_id, linha in ranking.iterrows():
        frac = int(linha['eventos_fracionamento'])
        atip = int(linha['eventos_valor_atipico'])
        risco = risco_pelas_regras(frac, atip)

        marcas = []
        if frac:
            marcas.append(f'<span class="marca">Fracionamento ×{frac}</span>')
        if atip:
            marcas.append(f'<span class="marca">Valor atípico ×{atip}</span>')

        st.markdown(f"""
        <div class="ficha {risco}">
          <span class="carimbo {risco}">{risco}</span>
          <div class="id">{cliente_id}</div>
          <div class="valor">R$ {linha['volume_total']:,.2f}</div>
          <div class="marcas">{''.join(marcas)}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="medidor"><span>{MODELO}</span></div>
    <div class="medidor" style="border:0;padding-top:.2rem;margin-top:0;">
      <span>{st.session_state.consultas} consultas</span>
      <span>{st.session_state.tokens_acumulados:,} tokens</span>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Encerrar e recomeçar", use_container_width=True):
        st.session_state.chat = criar_chat()
        st.session_state.mensagens = []
        st.session_state.tokens_acumulados = 0
        st.session_state.consultas = 0
        st.rerun()

# --- Área de análise ---
st.markdown("""
<div class="cabecalho">
  <h1>Mesa de Triagem</h1>
  <div class="sub">Prevenção à lavagem de dinheiro · dados fictícios</div>
</div>
""", unsafe_allow_html=True)

if not st.session_state.mensagens:
    st.markdown("""
    <div class="rotulo" style="margin-top:1.5rem;">Abrir análise</div>
    <div class="sugestoes">
      explique o caso do CLI-029<br>
      compare CLI-014 e CLI-023<br>
      gere um parecer para o CLI-017
    </div>
    """, unsafe_allow_html=True)

for msg in st.session_state.mensagens:
    with st.chat_message(msg['papel'], avatar="🧑‍💼" if msg['papel'] == 'user' else "⚙️"):
        st.markdown(msg['texto'])
        if msg.get('ferramentas'):
            st.markdown(
                f'<div class="trilha">Consultou: {" · ".join(msg["ferramentas"])}</div>',
                unsafe_allow_html=True,
            )

pergunta = st.chat_input("Pergunte sobre um caso em triagem...")

if pergunta:
    st.session_state.mensagens.append({'papel': 'user', 'texto': pergunta})
    with st.chat_message('user', avatar="🧑‍💼"):
        st.markdown(pergunta)

    with st.chat_message('assistant', avatar="⚙️"):
        with st.spinner("Consultando a base..."):
            ferramentas.limpar_log_chamadas()
            try:
                resposta = st.session_state.chat.send_message(pergunta)
                texto = resposta.text
                chamadas = [c['ferramenta'] for c in ferramentas.obter_log_chamadas()]
                st.session_state.tokens_acumulados += resposta.usage_metadata.total_token_count
                st.session_state.consultas += 1
            except Exception as e:
                if any(c in str(e) for c in ['429', 'RESOURCE_EXHAUSTED']):
                    texto = "A cota diária da API foi atingida. A análise recomeça amanhã."
                elif any(c in str(e) for c in ['503', 'UNAVAILABLE']):
                    texto = "A API está sobrecarregada. Repita a pergunta em alguns instantes."
                else:
                    texto = f"A consulta falhou. `{type(e).__name__}: {e}`"
                chamadas = []

        st.markdown(texto)
        if chamadas:
            st.markdown(
                f'<div class="trilha">Consultou: {" · ".join(chamadas)}</div>',
                unsafe_allow_html=True,
            )

    st.session_state.mensagens.append(
        {'papel': 'assistant', 'texto': texto, 'ferramentas': chamadas}
    )
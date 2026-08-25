import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
import pandas as pd

import tools
from tools import historico_cliente, operacoes_do_dia, perfil_canal
from dados import carregar_e_tratar

load_dotenv('.env')
client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

# Carrega e trata os dados (limpeza centralizada em dados.py)
df, taxa_cambio = carregar_e_tratar()

print(f"Taxa de câmbio USD/BRL: {taxa_cambio}")
print(f"Total de registros após tratamento: {len(df)}")
print(f"Registros com data ausente: {df['data_ausente'].sum()}")
print(f"Registros convertidos de USD: {(df['moeda'] == 'USD').sum()}")

# --- Regra 1: Fracionamento ---
agrupado = df.groupby(['cliente_id', 'data']).agg(
    qtd_operacoes=('valor_brl', 'count'),
    soma_valor=('valor_brl', 'sum'),
    maior_operacao=('valor_brl', 'max')
).reset_index()

agrupado['fracionamento'] = (
    (agrupado['qtd_operacoes'] >= 3) &
    (agrupado['soma_valor'] > 50000) &
    (agrupado['maior_operacao'] < 20000)
)

clientes_fracionamento = agrupado[agrupado['fracionamento']]['cliente_id'].unique()
df['flag_fracionamento'] = df['cliente_id'].isin(clientes_fracionamento)

print(f"\nClientes sinalizados por fracionamento: {len(clientes_fracionamento)}")
print(clientes_fracionamento)

# --- Regra 2: Valor atípico ---
estatisticas_cliente = df.groupby('cliente_id')['valor_brl'].agg(
    mediana_cliente='median',
    qtd_operacoes_cliente='count'
).reset_index()

df = df.merge(estatisticas_cliente, on='cliente_id', how='left')

df['flag_valor_atipico'] = (
    (df['qtd_operacoes_cliente'] >= 4) &
    (df['valor_brl'] > 5 * df['mediana_cliente'])
)

print(f"\nOperações sinalizadas por valor atípico: {df['flag_valor_atipico'].sum()}")

# --- Top 10 clientes mais sinalizados ---
# Critério: cada disparo de regra conta como 1 evento de alerta.
# - Fracionamento: 1 evento por DIA que caracterizou o padrão
#   (as múltiplas operações daquele dia formam um único padrão suspeito, não vários)
# - Valor atípico: 1 evento por OPERAÇÃO sinalizada
# Desempate: volume total transacionado pelo cliente (conforme enunciado)

# Eventos de fracionamento: conta dias sinalizados por cliente
eventos_frac = (
    agrupado[agrupado['fracionamento']]
    .groupby('cliente_id')
    .size()
    .rename('eventos_fracionamento')
)

# Eventos de valor atípico: conta operações sinalizadas por cliente
eventos_atipico = (
    df[df['flag_valor_atipico']]
    .groupby('cliente_id')
    .size()
    .rename('eventos_valor_atipico')
)

# Volume total por cliente (critério de desempate)
volume_cliente = df.groupby('cliente_id')['valor_brl'].sum().rename('volume_total')

# Consolida tudo em um único DataFrame
ranking = pd.concat([eventos_frac, eventos_atipico, volume_cliente], axis=1).fillna(0)
ranking['total_sinalizacoes'] = (
    ranking['eventos_fracionamento'] + ranking['eventos_valor_atipico']
)

# Mantém apenas clientes com ao menos uma sinalização, ordena e pega o top 10
top10 = (
    ranking[ranking['total_sinalizacoes'] > 0]
    .sort_values(['total_sinalizacoes', 'volume_total'], ascending=[False, False])
    .head(10)
)

print("\n--- Top 10 clientes mais sinalizados ---")
print(top10)

# --- Agente com ferramentas ---

INSTRUCAO_SISTEMA = """Você é um analista de prevenção à lavagem de dinheiro (PLD).

Sua tarefa é emitir um parecer sobre clientes sinalizados por regras determinísticas.
Você tem ferramentas disponíveis para consultar a base de operações. Use apenas as
ferramentas necessárias para fundamentar o parecer daquele caso específico —
não é preciso consultar tudo sempre.

Orientações sobre os dados:
- Todos os valores retornados pelas ferramentas com sufixo "_brl" já estão em reais.
- O campo "moeda_original" indica apenas a moeda em que a operação foi registrada
  antes da conversão. Nunca combine o número de um campo "_brl" com esse rótulo.
- Os cálculos já foram feitos. Sua função é interpretar os números, não recalculá-los.

Ao final, responda APENAS com um JSON válido, sem texto ou marcação adicional:
{
  "nivel_risco": "baixo" | "medio" | "alto",
  "tipologia_suspeita": "string",
  "red_flags": ["lista", "de", "strings"],
  "justificativa": "string"
}"""


def montar_contexto_caso(cliente_id, linha_ranking):
    """Monta a descrição do caso a partir do que as regras determinísticas apontaram."""
    partes = [f"Cliente sob análise: {cliente_id}"]

    if linha_ranking['eventos_fracionamento'] > 0:
        dias = agrupado[
            (agrupado['cliente_id'] == cliente_id) & agrupado['fracionamento']
        ]['data'].tolist()
        partes.append(
            f"Sinalizado pela Regra 1 (fracionamento) em {int(linha_ranking['eventos_fracionamento'])} "
            f"dia(s): {', '.join(dias)}. A regra identifica 3 ou mais operações no mesmo dia "
            f"somando mais de R$ 50.000, sem que nenhuma isolada atinja R$ 20.000."
        )

    if linha_ranking['eventos_valor_atipico'] > 0:
        partes.append(
            f"Sinalizado pela Regra 2 (valor atípico) em "
            f"{int(linha_ranking['eventos_valor_atipico'])} operação(ões). A regra identifica "
            f"operações acima de 5x a mediana do próprio cliente."
        )

    partes.append("Investigue o caso com as ferramentas que julgar necessárias e emita o parecer.")
    return "\n".join(partes)

def chamar_com_retry(funcao, max_tentativas=4, espera_inicial=5):
    """Executa uma chamada à API com retry exponencial.

    A API do Gemini retorna 503 (sobrecarga) e 429 (rate limit) de forma
    intermitente no free tier. Sem retry, uma falha transitória derruba
    o processamento inteiro do lote.
    """
    for tentativa in range(max_tentativas):
        try:
            return funcao()
        except Exception as e:
            eh_transitorio = any(
                codigo in str(e) for codigo in ['503', '429', 'UNAVAILABLE', 'RESOURCE_EXHAUSTED']
            )
            if eh_transitorio and tentativa < max_tentativas - 1:
                espera = espera_inicial * (2 ** tentativa)
                print(f"  [retry] Falha transitória ({type(e).__name__}). "
                      f"Tentativa {tentativa + 1}/{max_tentativas}. Aguardando {espera}s...")
                time.sleep(espera)
            else:
                raise

def analisar_cliente(cliente_id, linha_ranking):
    """Executa o agente sobre um cliente e devolve o parecer com metadados."""
    tools.limpar_log_chamadas()

    contexto = montar_contexto_caso(cliente_id, linha_ranking)

    chat = client.chats.create(
        model='gemini-3.6-flash',
        config=types.GenerateContentConfig(
            system_instruction=INSTRUCAO_SISTEMA,
            tools=[historico_cliente, operacoes_do_dia, perfil_canal],
        ),
    )

    inicio = time.time()
    resposta = chamar_com_retry(lambda: chat.send_message(contexto))
    latencia = time.time() - inicio

    uso = resposta.usage_metadata

    return {
        'cliente_id': cliente_id,
        'resposta_bruta': resposta.text,
        'ferramentas_chamadas': tools.obter_log_chamadas(),
        'latencia_s': round(latencia, 2),
        'tokens_entrada': uso.prompt_token_count,
        'tokens_saida': uso.candidates_token_count,
        'tokens_total': uso.total_token_count,
    }


# Teste com um único cliente antes de rodar o lote
if __name__ == '__main__':
    cliente_teste = top10.index[0]
    resultado = analisar_cliente(cliente_teste, top10.loc[cliente_teste])

    print(f"\n--- Agente: {cliente_teste} ---")
    print(f"Ferramentas chamadas: {resultado['ferramentas_chamadas']}")
    print(f"Latência: {resultado['latencia_s']}s | Tokens: {resultado['tokens_total']}")
    print(f"\nParecer:\n{resultado['resposta_bruta']}")
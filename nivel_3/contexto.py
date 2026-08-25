"""
Prepara o contexto de clientes sinalizados para a interface conversacional.

Reimplementa as regras do Nível 2 de forma isolada: o Nível 3 não importa
nivel_2/agente.py para evitar seus efeitos colaterais de módulo (execução de
lote, prints) e para que mudanças aqui não afetem o que já foi validado.
"""

import json

import pandas as pd

from pathlib import Path

# Caminho absoluto derivado da localização deste arquivo, não do diretório
# de execução — assim funciona tanto rodando da raiz quanto de dentro de nivel_3/
RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_DADOS = RAIZ / 'dados' / 'dados_nivel_2.json'
CAMINHO_ENV = RAIZ / '.env'

def carregar_e_tratar(caminho=CAMINHO_DADOS):
    """Carrega o JSON e aplica o mesmo tratamento validado nos níveis anteriores."""
    with open(caminho, 'r', encoding='utf-8') as f:
        dados_brutos = json.load(f)

    taxa_cambio = dados_brutos['taxa_cambio_usd_brl']
    df = pd.DataFrame(dados_brutos['operacoes'])

    df = df.drop_duplicates().reset_index(drop=True)
    df['data_ausente'] = df['data'].isnull()
    df['valor_brl'] = df.apply(
        lambda row: row['valor'] * taxa_cambio if row['moeda'] == 'USD' else row['valor'],
        axis=1
    )

    return df, taxa_cambio


def aplicar_regras(df):
    """Aplica as duas regras determinísticas e devolve o df anotado e o agrupamento diário."""
    # Regra 1 — Fracionamento
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

    clientes_frac = agrupado[agrupado['fracionamento']]['cliente_id'].unique()
    df['flag_fracionamento'] = df['cliente_id'].isin(clientes_frac)

    # Regra 2 — Valor atípico
    estatisticas = df.groupby('cliente_id')['valor_brl'].agg(
        mediana_cliente='median',
        qtd_operacoes_cliente='count'
    ).reset_index()

    df = df.merge(estatisticas, on='cliente_id', how='left')
    df['flag_valor_atipico'] = (
        (df['qtd_operacoes_cliente'] >= 4) &
        (df['valor_brl'] > 5 * df['mediana_cliente'])
    )

    return df, agrupado


def montar_ranking(df, agrupado, top_n=10):
    """Ranking de clientes por eventos de alerta, com volume como desempate."""
    eventos_frac = (
        agrupado[agrupado['fracionamento']]
        .groupby('cliente_id').size().rename('eventos_fracionamento')
    )
    eventos_atipico = (
        df[df['flag_valor_atipico']]
        .groupby('cliente_id').size().rename('eventos_valor_atipico')
    )
    volume = df.groupby('cliente_id')['valor_brl'].sum().rename('volume_total')

    ranking = pd.concat([eventos_frac, eventos_atipico, volume], axis=1).fillna(0)
    ranking['total_sinalizacoes'] = (
        ranking['eventos_fracionamento'] + ranking['eventos_valor_atipico']
    )

    return (
        ranking[ranking['total_sinalizacoes'] > 0]
        .sort_values(['total_sinalizacoes', 'volume_total'], ascending=[False, False])
        .head(top_n)
    )


def resumo_para_prompt(ranking, agrupado):
    """Texto compacto com os clientes sinalizados, injetado no início da conversa.

    Pré-carregar esse resumo evita que o modelo precise chamar ferramentas
    apenas para saber quem está na lista — economiza requisições.
    """
    linhas = ["Clientes sinalizados pelas regras determinísticas:"]

    for cliente_id, linha in ranking.iterrows():
        partes = [f"- {cliente_id}: volume total R$ {linha['volume_total']:,.2f}"]

        if linha['eventos_fracionamento'] > 0:
            dias = agrupado[
                (agrupado['cliente_id'] == cliente_id) & agrupado['fracionamento']
            ]['data'].tolist()
            partes.append(f"fracionamento em {', '.join(dias)}")

        if linha['eventos_valor_atipico'] > 0:
            partes.append(
                f"{int(linha['eventos_valor_atipico'])} operação(ões) de valor atípico"
            )

        linhas.append("; ".join(partes))

    return "\n".join(linhas)


if __name__ == '__main__':
    df, taxa = carregar_e_tratar()
    df, agrupado = aplicar_regras(df)
    ranking = montar_ranking(df, agrupado)

    print(f"Registros tratados: {len(df)} | Taxa USD/BRL: {taxa}\n")
    print(ranking.to_string())
    print("\n--- Resumo para o prompt ---")
    print(resumo_para_prompt(ranking, agrupado))
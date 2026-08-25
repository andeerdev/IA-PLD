import pandas as pd

from dados import carregar_e_tratar

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
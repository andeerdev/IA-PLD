import pandas as pd
import json

# Carrega o dataset do Nível 2 (base maior: ~320 operações, 30 clientes)
with open('dados/dados_nivel_2.json', 'r', encoding='utf-8') as f:
    dados_brutos = json.load(f)

taxa_cambio = dados_brutos['taxa_cambio_usd_brl']
df = pd.DataFrame(dados_brutos['operacoes'])

print(f"Taxa de câmbio USD/BRL: {taxa_cambio}")
print(f"Total de registros carregados: {len(df)}")

# --- Inspeção inicial (mesmos comandos do Nível 1) ---
print(df.info())
print("\nValores nulos por coluna:")
print(df.isnull().sum())
print(f"\nLinhas duplicadas: {df.duplicated().sum()}")
print(f"\nMoedas únicas: {df['moeda'].unique()}")
print(f"Canais únicos: {df['canal'].unique()}")
print(f"Tipos únicos: {df['tipo'].unique()}")

# --- Tratamento de dados (mesma lógica validada no Nível 1) ---

# Remove linhas totalmente duplicadas
print(f"\nLinhas antes de remover duplicatas: {len(df)}")
df = df.drop_duplicates().reset_index(drop=True)
print(f"Linhas depois: {len(df)}")

# Sinaliza data ausente sem remover ou inferir
df['data_ausente'] = df['data'].isnull()
print(f"Registros com data ausente: {df['data_ausente'].sum()}")

# Converte valores para BRL usando a taxa de câmbio fornecida
df['valor_brl'] = df.apply(
    lambda row: row['valor'] * taxa_cambio if row['moeda'] == 'USD' else row['valor'],
    axis=1
)
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

print(f"Clientes sinalizados por fracionamento: {len(clientes_fracionamento)}")
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
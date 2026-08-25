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
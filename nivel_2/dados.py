"""
Carregamento e tratamento dos dados de operações.

Centraliza a limpeza validada no Nível 1 para que agente.py, tools.py e
confronto.py trabalhem sempre sobre a mesma base tratada, sem duplicar lógica.
"""

import json
import pandas as pd

CAMINHO_DADOS = 'dados/dados_nivel_2.json'


def carregar_e_tratar(caminho=CAMINHO_DADOS):
    """Carrega o JSON de operações e aplica o tratamento de qualidade.

    Retorna:
        df (DataFrame): operações tratadas, com as colunas adicionais
            'data_ausente' (bool) e 'valor_brl' (float).
        taxa_cambio (float): taxa USD/BRL fornecida no próprio arquivo.
    """
    with open(caminho, 'r', encoding='utf-8') as f:
        dados_brutos = json.load(f)

    taxa_cambio = dados_brutos['taxa_cambio_usd_brl']
    df = pd.DataFrame(dados_brutos['operacoes'])

    # Remove linhas totalmente duplicadas (duplicação de importação do legado)
    df = df.drop_duplicates().reset_index(drop=True)

    # Sinaliza data ausente sem remover nem inferir o valor
    df['data_ausente'] = df['data'].isnull()

    # Normaliza valores para BRL usando a taxa do próprio arquivo
    df['valor_brl'] = df.apply(
        lambda row: row['valor'] * taxa_cambio if row['moeda'] == 'USD' else row['valor'],
        axis=1
    )

    return df, taxa_cambio
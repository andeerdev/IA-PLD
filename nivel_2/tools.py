"""
Ferramentas de consulta à base de operações.

Cada função recebe parâmetros simples e devolve um dicionário serializável,
formato que o agente consegue interpretar e repassar ao modelo de linguagem.
Todo cálculo (soma, média, mediana, contagem) acontece aqui, em pandas —
o modelo apenas interpreta os números já apurados.
"""

from dados import carregar_e_tratar

# Carrega a base tratada uma única vez, no import do módulo
_df, _taxa_cambio = carregar_e_tratar()


def historico_cliente(cliente_id):
    """Resumo agregado de todas as operações de um cliente.

    Args:
        cliente_id (str): identificador do cliente, ex. 'CLI-014'.

    Returns:
        dict: métricas agregadas do cliente, ou mensagem de erro se não existir.
    """
    operacoes = _df[_df['cliente_id'] == cliente_id]

    if operacoes.empty:
        return {'erro': f'Cliente {cliente_id} não encontrado na base.'}

    valores = operacoes['valor_brl']

    return {
        'cliente_id': cliente_id,
        'qtd_operacoes': int(len(operacoes)),
        'volume_total_brl': round(float(valores.sum()), 2),
        'valor_medio_brl': round(float(valores.mean()), 2),
        'valor_mediano_brl': round(float(valores.median()), 2),
        'maior_operacao_brl': round(float(valores.max()), 2),
        'menor_operacao_brl': round(float(valores.min()), 2),
        'primeira_data': operacoes['data'].min(),
        'ultima_data': operacoes['data'].max(),
        'qtd_operacoes_moeda_estrangeira': int((operacoes['moeda'] != 'BRL').sum()),
        'qtd_operacoes_sem_data': int(operacoes['data_ausente'].sum()),
        'tipos_operacao': operacoes['tipo'].value_counts().to_dict(),
        'contrapartes_distintas': int(operacoes['contraparte'].nunique()),
    }
    
def operacoes_do_dia(cliente_id, data):
    """Recorte das operações de um cliente em uma data específica.

    Útil para investigar padrões de fracionamento, em que várias operações
    de um mesmo dia formam o comportamento suspeito.

    Args:
        cliente_id (str): identificador do cliente, ex. 'CLI-029'.
        data (str): data no formato 'AAAA-MM-DD', ex. '2026-05-26'.

    Returns:
        dict: operações daquele dia com métricas agregadas do próprio dia.
    """
    operacoes = _df[(_df['cliente_id'] == cliente_id) & (_df['data'] == data)]

    if operacoes.empty:
        return {
            'cliente_id': cliente_id,
            'data': data,
            'qtd_operacoes': 0,
            'mensagem': f'Nenhuma operação encontrada para {cliente_id} em {data}.'
        }

    valores = operacoes['valor_brl']

    return {
        'cliente_id': cliente_id,
        'data': data,
        'qtd_operacoes': int(len(operacoes)),
        'soma_do_dia_brl': round(float(valores.sum()), 2),
        'maior_operacao_brl': round(float(valores.max()), 2),
        'menor_operacao_brl': round(float(valores.min()), 2),
        'operacoes': [
            {
                'id': row['id'],
                'valor_brl': round(float(row['valor_brl']), 2),
                'moeda_original': row['moeda'],
                'canal': row['canal'],
                'tipo': row['tipo'],
                'contraparte': row['contraparte'],
            }
            for _, row in operacoes.iterrows()
        ]
    }
    
def perfil_canal(cliente_id):
    """Distribuição de uso de canais por um cliente.

    Útil para identificar concentração incomum em canais de maior risco
    (espécie, por exemplo) ou mudanças de padrão de canal.

    Args:
        cliente_id (str): identificador do cliente, ex. 'CLI-014'.

    Returns:
        dict: contagem e volume por canal, com o canal predominante.
    """
    operacoes = _df[_df['cliente_id'] == cliente_id]

    if operacoes.empty:
        return {'erro': f'Cliente {cliente_id} não encontrado na base.'}

    total_operacoes = len(operacoes)

    # Agrega contagem e volume por canal
    por_canal = operacoes.groupby('canal')['valor_brl'].agg(['count', 'sum'])

    distribuicao = {
        canal: {
            'qtd_operacoes': int(linha['count']),
            'percentual_operacoes': round(float(linha['count'] / total_operacoes * 100), 1),
            'volume_brl': round(float(linha['sum']), 2),
        }
        for canal, linha in por_canal.iterrows()
    }

    canal_predominante = por_canal['count'].idxmax()

    return {
        'cliente_id': cliente_id,
        'qtd_operacoes': int(total_operacoes),
        'canais_utilizados': int(len(distribuicao)),
        'canal_predominante': canal_predominante,
        'distribuicao_por_canal': distribuicao,
    }
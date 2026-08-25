"""
Ferramentas de consulta expostas ao agente conversacional.

Mesma responsabilidade do tools.py do Nível 2, isolado aqui para que o Nível 3
não dependa de módulos que executam código na importação.
Todo cálculo acontece em pandas; o modelo apenas interpreta os números.
"""

from contexto import carregar_e_tratar, aplicar_regras

_df, _taxa_cambio = carregar_e_tratar()
_df, _agrupado = aplicar_regras(_df)

_log_chamadas = []


def registrar_chamada(nome, argumentos):
    _log_chamadas.append({'ferramenta': nome, 'argumentos': argumentos})


def obter_log_chamadas():
    return list(_log_chamadas)


def limpar_log_chamadas():
    _log_chamadas.clear()


def historico_cliente(cliente_id: str) -> dict:
    """Resumo agregado de todas as operações de um cliente.

    Args:
        cliente_id: identificador do cliente, ex. 'CLI-014'.
    """
    registrar_chamada('historico_cliente', {'cliente_id': cliente_id})
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


def operacoes_do_dia(cliente_id: str, data: str) -> dict:
    """Recorte das operações de um cliente em uma data específica.

    Args:
        cliente_id: identificador do cliente, ex. 'CLI-029'.
        data: data no formato 'AAAA-MM-DD', ex. '2026-05-26'.
    """
    registrar_chamada('operacoes_do_dia', {'cliente_id': cliente_id, 'data': data})
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


def perfil_canal(cliente_id: str) -> dict:
    """Distribuição de uso de canais por um cliente.

    Args:
        cliente_id: identificador do cliente, ex. 'CLI-014'.
    """
    registrar_chamada('perfil_canal', {'cliente_id': cliente_id})
    operacoes = _df[_df['cliente_id'] == cliente_id]

    if operacoes.empty:
        return {'erro': f'Cliente {cliente_id} não encontrado na base.'}

    total = len(operacoes)
    por_canal = operacoes.groupby('canal')['valor_brl'].agg(['count', 'sum'])

    distribuicao = {
        canal: {
            'qtd_operacoes': int(linha['count']),
            'percentual_operacoes': round(float(linha['count'] / total * 100), 1),
            'volume_brl': round(float(linha['sum']), 2),
        }
        for canal, linha in por_canal.iterrows()
    }

    return {
        'cliente_id': cliente_id,
        'qtd_operacoes': int(total),
        'canais_utilizados': int(len(distribuicao)),
        'canal_predominante': por_canal['count'].idxmax(),
        'distribuicao_por_canal': distribuicao,
    }


def comparar_clientes(cliente_id_a: str, cliente_id_b: str) -> dict:
    """Compara o perfil transacional de dois clientes lado a lado.

    Args:
        cliente_id_a: primeiro cliente, ex. 'CLI-014'.
        cliente_id_b: segundo cliente, ex. 'CLI-029'.
    """
    registrar_chamada('comparar_clientes',
                      {'cliente_id_a': cliente_id_a, 'cliente_id_b': cliente_id_b})

    resumo_a = historico_cliente(cliente_id_a)
    resumo_b = historico_cliente(cliente_id_b)

    if 'erro' in resumo_a or 'erro' in resumo_b:
        return {'erro': 'Um dos clientes não foi encontrado na base.'}

    return {
        'cliente_a': resumo_a,
        'cliente_b': resumo_b,
        'diferencas': {
            'volume_total_brl': round(
                resumo_a['volume_total_brl'] - resumo_b['volume_total_brl'], 2),
            'qtd_operacoes': resumo_a['qtd_operacoes'] - resumo_b['qtd_operacoes'],
            'valor_mediano_brl': round(
                resumo_a['valor_mediano_brl'] - resumo_b['valor_mediano_brl'], 2),
        }
    }
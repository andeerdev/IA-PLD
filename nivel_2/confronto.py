"""
Confronto entre as regras determinísticas e o parecer do agente.

Compara o nível de risco que as regras implicariam com o que o agente atribuiu,
reporta a taxa de concordância e detalha as divergências.
"""

import json
import os

import pandas as pd

CAMINHO_PARECERES = 'outputs/pareceres_nivel_2.json'
CAMINHO_SAIDA = 'outputs/confronto_nivel_2.csv'

# Ordem usada para medir a distância entre os níveis
ESCALA_RISCO = {'baixo': 0, 'medio': 1, 'alto': 2}


def risco_esperado_pelas_regras(eventos_fracionamento, eventos_valor_atipico):
    """Traduz o que as regras apontaram para a escala de risco do parecer.

    Critério adotado:
    - Fracionamento é tipologia de intenção deliberada (estruturação para evitar
      controles). Raramente tem explicação inocente, então implica risco alto.
    - Valor atípico é ambíguo isoladamente (pode ser venda de bem, herança, bônus).
      A gravidade escala com a recorrência: um evento é pontual, vários viram padrão.
    """
    if eventos_fracionamento > 0 and eventos_valor_atipico > 0:
        return 'alto'
    if eventos_fracionamento > 0:
        return 'alto'
    if eventos_valor_atipico >= 2:
        return 'medio'
    return 'baixo'


def carregar_pareceres(caminho=CAMINHO_PARECERES):
    with open(caminho, 'r', encoding='utf-8') as f:
        return json.load(f)


def montar_confronto(pareceres):
    """Monta o DataFrame de comparação entre regra e agente."""
    linhas = []

    for registro in pareceres:
        if 'erro' in registro:
            continue

        parecer = registro['parecer']
        risco_agente = parecer.get('nivel_risco', 'erro')
        risco_regra = risco_esperado_pelas_regras(
            registro['eventos_fracionamento'],
            registro['eventos_valor_atipico'],
        )

        # Distância positiva = agente foi mais brando que a regra
        distancia = ESCALA_RISCO.get(risco_regra, 0) - ESCALA_RISCO.get(risco_agente, 0)

        linhas.append({
            'cliente_id': registro['cliente_id'],
            'eventos_fracionamento': registro['eventos_fracionamento'],
            'eventos_valor_atipico': registro['eventos_valor_atipico'],
            'volume_total_brl': registro['volume_total_brl'],
            'risco_regra': risco_regra,
            'risco_agente': risco_agente,
            'concorda': risco_regra == risco_agente,
            'distancia': distancia,
            'tipologia_agente': parecer.get('tipologia_suspeita', ''),
            'justificativa_agente': parecer.get('justificativa', ''),
        })

    return pd.DataFrame(linhas)


if __name__ == '__main__':
    pareceres = carregar_pareceres()
    confronto = montar_confronto(pareceres)

    os.makedirs('outputs', exist_ok=True)
    confronto.to_csv(CAMINHO_SAIDA, index=False)

    print("--- Confronto: regra determinística vs. agente ---")
    print(confronto[[
        'cliente_id', 'eventos_fracionamento', 'eventos_valor_atipico',
        'risco_regra', 'risco_agente', 'concorda'
    ]].to_string(index=False))

    total = len(confronto)
    concordantes = int(confronto['concorda'].sum())
    print(f"\nTaxa de concordância: {concordantes}/{total} ({concordantes / total * 100:.0f}%)")

    print("\n--- Matriz de confusão (regra x agente) ---")
    print(pd.crosstab(confronto['risco_regra'], confronto['risco_agente']).to_string())

    divergencias = confronto[~confronto['concorda']]
    if not divergencias.empty:
        print(f"\n--- Divergências ({len(divergencias)}) ---")
        for _, linha in divergencias.iterrows():
            direcao = 'mais brando que' if linha['distancia'] > 0 else 'mais severo que'
            print(f"\n{linha['cliente_id']}: regra={linha['risco_regra']} | "
                  f"agente={linha['risco_agente']} (agente {direcao} a regra)")
            print(f"  Tipologia: {linha['tipologia_agente']}")
            print(f"  Justificativa: {linha['justificativa_agente']}")

    print(f"\nResultado salvo em {CAMINHO_SAIDA}")
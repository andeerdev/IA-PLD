# IA-PLD — Triagem de operações financeiras com regras e LLM

Desafio técnico. O cenário: uma mesa de triagem de Prevenção à Lavagem de Dinheiro (PLD) recebe operações financeiras e precisa identificar quais clientes merecem análise humana.

A solução combina **regras determinísticas** (cálculo, em pandas) com **um modelo de linguagem** (interpretação e redação). A separação é deliberada: soma, mediana, contagem e comparação com limite acontecem inteiramente em pandas; a LLM recebe números já apurados e apenas os interpreta.

> Todos os dados são fictícios e foram gerados para fins de avaliação.

## Estrutura

```
.
├── dados/                      # datasets de entrada (JSON)
├── nivel_1/
│   └── nivel_1.ipynb           # notebook com as saídas executadas
├── nivel_2/
│   ├── dados.py                # carregamento e tratamento (compartilhado)
│   ├── tools.py                # ferramentas de consulta à base
│   ├── agente.py               # regras em escala + agente + execução em lote
│   └── confronto.py            # comparação entre regra e parecer do agente
├── outputs/                    # resultados das execuções
└── docs/
    ├── DECISOES.md             # trade-offs, limitações e o que faria diferente
    └── USO_DE_IA.md
```

## Como rodar

**Pré-requisitos:** Python 3.10+ e uma chave da API do Gemini ([Google AI Studio](https://aistudio.google.com)).

```bash
pip install -r requirements.txt
```

Crie um arquivo `.env` na raiz, seguindo o modelo de `.env.example`:

```
GOOGLE_API_KEY=sua_chave_aqui
```

> **Execute sempre a partir da raiz do repositório.** Os caminhos de arquivo (`dados/`, `outputs/`, `.env`) são relativos à raiz.

**Nível 1** — abra `nivel_1/nivel_1.ipynb` no Jupyter. O notebook já está commitado com as saídas executadas; para reproduzir, use "Restart Kernel and Run All".

**Nível 2:**

```bash
python nivel_2/agente.py      # roda as regras, o ranking e o lote de 10 clientes
python nivel_2/confronto.py   # compara regra vs. agente (lê os pareceres salvos)
```

O `agente.py` mantém um cache em `outputs/cache_pareceres.json`. Execuções repetidas reaproveitam os pareceres já gerados, sem consumir quota da API. Para forçar reprocessamento, apague o arquivo de cache.

## Saídas geradas

| Arquivo | Conteúdo |
|---|---|
| `outputs/pareceres_nivel_2.json` | Um registro por cliente: flags das regras, ferramentas chamadas, custo, latência e o parecer estruturado |
| `outputs/metricas_nivel_2.csv` | Métricas de custo e latência por cliente |
| `outputs/confronto_nivel_2.csv` | Comparação entre o risco implicado pelas regras e o atribuído pelo agente |

## O que foi implementado

**Nível 1 — dados e primeira análise.** Limpeza de três problemas de qualidade (registro duplicado, data ausente, moeda mista), normalização para BRL, agregações por cliente e por canal, as duas regras determinísticas com validação explícita, e análise com LLM em saída estruturada validada, com duas versões de prompt comparadas.

**Nível 2 — escala, ferramentas e confronto.** As mesmas regras sobre 317 operações e 30 clientes, ranking dos 10 clientes mais sinalizados, três ferramentas de consulta, um agente com function calling que decide quais ferramentas usar, execução em lote com registro de custo e latência, e o confronto entre regra e modelo.

**Nível 3** — não implementado. O plano está em `docs/DECISOES.md`.

## Principais conclusões

**O agente decidiu a estratégia de investigação conforme o caso.** O log de chamadas mostra três padrões distintos entre os 10 clientes. Nos casos de valor atípico, ele consultou `historico_cliente` e depois `perfil_canal`. Nos casos de fracionamento, **inverteu a ordem** — foi direto ao dia sinalizado (`operacoes_do_dia`) antes de buscar o contexto geral. Um cliente foi resolvido com uma única ferramenta.

**As regras geram falsos positivos previsíveis.** A Regra 2 compara cada operação com a mediana do cliente, e a mediana é sensível quando há muitas operações pequenas. Em dois casos (CLI-028 e CLI-013), o agente classificou como risco baixo o que a regra apontaria como médio, argumentando que os valores eram consistentes com a faixa de movimentação geral do cliente. A regra compara com um estimador estatístico; o agente comparou com o perfil inteiro.

**O agente tem viés de calibragem para baixo.** Em 10 casos, ele nunca atribuiu risco alto — apenas "medio" (7) e "baixo" (3). Todas as 4 divergências com as regras apontam na mesma direção: agente mais brando. Em dois casos de fracionamento, o parecer chega a reconhecer "tentativa intencional de evitar controles" e ainda assim classifica como risco médio — o raciocínio e o veredito não se sustentam mutuamente.

**Taxa de concordância entre regra e agente: 60%** (6 de 10). A análise das divergências está em `docs/DECISOES.md`.

## Observações técnicas

- **Function calling multiplica requisições.** Cada cliente consome uma requisição por ida e volta com o modelo, não uma no total. Isso esgotou a quota diária do `gemini-3.6-flash` (20 req/dia no free tier) antes de metade do lote.
- **Modelos usados:** `gemini-3.6-flash` no Nível 1 e `gemini-3.5-flash-lite` no Nível 2. A troca foi forçada pelo limite de quota; os pareceres dos dois níveis não são diretamente comparáveis por isso.
- **Custo do lote:** 15.325 tokens para 10 clientes, latência total de 80,77s (média de 8,08s por cliente).
# Decisões técnicas

Este documento reúne os trade-offs, limitações e decisões tomadas ao longo do desafio — não repete o que já está no código, mas explica o raciocínio por trás dele.

## Nível 1 — Limpeza de dados

### Registro duplicado
`OP-0007` (CLI-A-3) aparecia duas vezes no dataset, com todos os campos idênticos. Tratei como duplicação de importação do sistema legado e removi a cópia com `drop_duplicates()`, mantendo a primeira ocorrência. Não considerei necessário investigar mais a fundo porque o próprio `id` já indicava se tratar do mesmo registro, não de duas operações distintas com coincidência de valores.

### Data ausente
`OP-0017` (CLI-A-5) veio com `data: null`, com uma observação do próprio sistema legado ("data não capturada pelo sistema"). Decidi **não remover nem inferir** essa data.

**Justificativa:** em contexto de PLD, descartar um registro incompleto pode significar perder justamente o tipo de anomalia que merece investigação — não há como saber, sem mais contexto, se a ausência da data é falha técnica genuína ou um sinal de inconsistência proposital. Em vez de remover, criei uma coluna booleana `data_ausente` para sinalizar o registro explicitamente, preservando o dado original.

Na prática, isso significa que o registro participa normalmente das agregações e da Regra 2 (que não depende de data), mas naturalmente não entra em nenhum agrupamento da Regra 1 (que depende de `groupby('data')`; o pandas já exclui `NaN` do agrupamento por padrão, sem necessidade de tratamento adicional).

**Limitação / o que faria com mais tempo:** um sistema mais maduro provavelmente deveria gerar um alerta manual específico para "operação com metadado ausente", já que a própria ausência do dado pode ser, em si, um sinal de risco a ser investigado.

### Moeda mista
A maioria dos valores está em BRL, mas `OP-0013` (CLI-A-4) veio em USD. Converti para BRL usando a taxa fornecida no próprio arquivo (`taxa_cambio_usd_brl`), criando a coluna `valor_brl`, usada em todas as agregações e regras a partir dali.

**Impacto de não tratar:** sem essa conversão, o volume do CLI-A-4 apareceria menor do que o real, e a Regra 2 não identificaria a operação internacional como o outlier que de fato é dentro do padrão dele.

## Nível 1 — Análise com LLM

### Modelo descontinuado durante o desenvolvimento
Iniciei o desenvolvimento com `gemini-2.0-flash`, que foi descontinuado pela Google durante o processo (a API retornou erro 404 indicando o modelo como não mais disponível, sugerindo `gemini-3.6-flash` como substituto). Migrei para `gemini-3.6-flash`, modelo estável disponível no free tier no momento da entrega.

Também migrei do SDK `google-generativeai` (descontinuado, emitindo `FutureWarning`) para o `google-genai`, que é o SDK unificado atual. A sintaxe muda: `genai.configure()` + `GenerativeModel()` foram substituídos por um único `genai.Client()`.

**Observação:** isso reforça que trabalhar com APIs de LLM externas envolve lidar com ciclo de vida de modelos e SDKs em produção; um sistema real precisaria de alguma estratégia de monitoramento de deprecação, não apenas um nome de modelo fixo no código.

### A LLM confundiu valor convertido com moeda original
Em três chamadas distintas do prompt v1, a Gemini produziu a expressão "USD 64.800,00" ao se referir à operação `OP-0013`. O valor real era **USD 12.000**, que convertidos pela taxa resultam em **R$ 64.800**. A LLM misturou o valor já convertido (`valor_brl`, que aparecia no resumo tabular enviado no prompt) com o rótulo de moeda original (`moeda`), produzindo uma cifra em dólar que nunca existiu.

**Hipótese sobre a causa:** no resumo tabular enviado no prompt, as colunas `valor_brl` e `moeda` apareciam lado a lado na mesma linha. O modelo provavelmente leu as duas como "valor + moeda desse valor", em vez de entender que `valor_brl` já é resultado de uma conversão e `moeda` é um dado histórico da operação.

**Por que isso importa:** é um exemplo concreto e reproduzível de por que cálculo e leitura numérica precisa devem ficar em pandas. Mesmo pedindo apenas interpretação, sem pedir que a LLM calculasse nada, o modelo errou a leitura dos próprios números fornecidos.

### Comparação entre prompt v1 e v2
O prompt v2 testou a hipótese acima: adicionei instruções explícitas sobre o significado de cada coluna e uma proibição direta de combinar `valor_brl` com o rótulo de `moeda`.

**Resultado:** o erro não se repetiu. A resposta do v2 referenciou corretamente "R$ 64.800,00 BRL", tratando a moeda original como contexto separado.

**Efeitos colaterais medidos:**
- O `nivel_risco` mudou de "alto" (v1) para "medio" (v2) — mesmo cliente, mesmos dados. O fraseado do prompt influenciou não só a precisão factual, mas o próprio julgamento de risco. Isso é relevante em produção: a calibragem de risco de um sistema de PLD não deveria variar conforme detalhes de redação do prompt.
- Tokens totais subiram de 2.025 para 2.943 (+45%) e a latência de 10,06s para 32,24s. Prompt mais detalhado custa mais e demora mais.

### Tokens de "thinking" não somavam no total
Ao registrar tokens consumidos, `prompt_token_count + candidates_token_count` não batia com `total_token_count` (diferença de ~1.300 tokens). Investigando, descobri que modelos Gemini recentes usam tokens de raciocínio interno, reportados separadamente em `thoughts_token_count`. Esses tokens não aparecem no texto de saída nem em `candidates_token_count`, mas entram no total e, em produção, são cobrados.

Com o campo incluído, a conta fechou: 370 (entrada) + 1.297 (raciocínio) + 358 (saída) = 2.025 (total).

## Nível 2 — Regras em escala

### Arquivo `dados.py` fora da estrutura obrigatória
A estrutura exigida lista `tools.py`, `agente.py` e `confronto.py`. Criei um `dados.py` adicional para centralizar o carregamento e o tratamento dos dados.

**Motivo:** os três arquivos precisam operar sobre a mesma base tratada. As alternativas seriam duplicar a lógica de limpeza em cada um (propenso a divergência) ou colocar o ETL dentro de `tools.py` (um módulo chamado "tools" fazendo carregamento de dados não descreve o que faz). Um módulo dedicado resolve os dois problemas sem remover nem mover nada do que foi pedido; os três arquivos obrigatórios continuam onde o avaliador espera encontrá-los.

**O que faria diferente desde o começo:** teria estruturado o Nível 1 já com essa separação, para que o notebook importasse as funções de tratamento em vez de tê-las inline. Isso teria eliminado completamente a etapa de "reaproveitar" o tratamento no Nível 2 — seria apenas trocar o caminho do arquivo de entrada.

### Nenhum problema de qualidade novo no dataset maior
Rodei a mesma inspeção do Nível 1 (`.info()`, `.isnull().sum()`, `.duplicated().sum()`, `.unique()`) sobre a base de 322 registros. Os mesmos três problemas apareceram, em maior quantidade: 5 duplicatas, 7 registros com data nula, 7 operações em USD. Nenhuma moeda ou canal novo.

**Observação sobre sobreposição de problemas:** havia 7 registros com data nula antes da deduplicação e 6 depois, ou seja, uma das linhas duplicadas também tinha data ausente. Os problemas de qualidade não são necessariamente independentes entre si, e a ordem das operações de limpeza afeta as contagens intermediárias.

O campo `tipo` trouxe uma categoria que não existia no Nível 1 (`saque`), mas nenhuma das regras depende desse campo, então não houve impacto.

### Critério do ranking: eventos de alerta
O enunciado pede os "10 clientes mais sinalizados, ordenados pelo número de sinalizações". A ambiguidade é que as duas regras têm granularidades diferentes: a Regra 1 sinaliza o **cliente** (um padrão de comportamento num dia), a Regra 2 sinaliza a **operação**.

Considerei três critérios:
1. **Contar operações flagradas** — o cliente de fracionamento levaria as 4 operações daquele dia. Trata tudo na mesma unidade, mas infla o fracionamento: as 4 operações são um único padrão suspeito, não quatro suspeitas independentes.
2. **Contar eventos de alerta** — fracionamento conta 1 por dia sinalizado, valor atípico conta 1 por operação. Foi o que adotei.
3. **Peso por gravidade** — dar peso maior ao fracionamento por ser tipologia mais intencional. Descartado porque qualquer peso escolhido seria arbitrário e não derivaria dos dados.

**Justificativa da escolha:** contar eventos mantém coerência conceitual, cada "disparo de regra" é uma vez que o sistema levantou suspeita sobre aquele cliente. Um dia de fracionamento é um evento, independentemente de envolver 3 ou 10 operações.

**Consequência assumida:** dos 4 clientes sinalizados por fracionamento, apenas 2 (CLI-029 e CLI-017) entraram no top 10 — CLI-002 e CLI-003 ficaram de fora por terem 1 evento e volume menor que os empatados. Ou seja, o critério faz com que a tipologia mais intencional das duas possa perder posição para clientes com múltiplas operações atípicas.

## Nível 2 — Agente

### Automatic Function Calling via `client.chats`
O SDK oferece Automatic Function Calling (AFC): passando as funções Python diretamente em `tools=[...]`, ele gera o schema por introspecção de tipos e executa as chamadas automaticamente.

Duas correções foram necessárias durante a implementação:
- **Type hints obrigatórios.** Sem anotações (`cliente_id: str`), o SDK falha ao gerar o schema (`PydanticInvalidForJsonSchema`). O AFC depende inteiramente da introspecção da assinatura.
- **`client.chats.create()` em vez de `client.models.generate_content()`.** O próprio SDK emite aviso de que AFC direto em `generate_content` não é recomendado, a API de chat gerencia melhor o histórico multi-turno, que é exatamente o que acontece quando o modelo encadeia chamadas de ferramenta.

### Instrumentação das ferramentas
Com AFC, o SDK executa as ferramentas internamente e a resposta não expõe quais foram chamadas. Como o enunciado exige demonstrar que o agente **decide** (e não chama tudo sempre), adicionei um registro simples em `tools.py` (`registrar_chamada`, `obter_log_chamadas`, `limpar_log_chamadas`) que captura cada invocação e seus argumentos.

**Evidência de decisão genuína:** no caso do CLI-014, o agente chamou `historico_cliente`, depois `perfil_canal`, e então `operacoes_do_dia` com a data `2026-05-26`, data que ele extraiu do campo `ultima_data` retornado pela primeira ferramenta. Ele usou o resultado de uma ferramenta para decidir os argumentos da próxima, o que não seria possível num script com chamadas fixas.

### Retry com backoff exponencial
A API retornou `503 UNAVAILABLE` ("high demand") de forma intermitente, tanto no Nível 1 quanto no Nível 2, inclusive derrubando uma execução completa. O SDK já tem retry interno (via `tenacity`), mas não foi suficiente.

Implementei `chamar_com_retry` com até 4 tentativas e espera dobrando a cada falha (5s, 10s, 20s). O retry só dispara em erros transitórios identificáveis (503, 429, `UNAVAILABLE`, `RESOURCE_EXHAUSTED`); erros de código são relançados imediatamente, sem desperdiçar tentativas.

**Efeito colateral na métrica de latência:** com o retry ativo, o tempo medido inclui as esperas entre tentativas. Isso distorce a latência "pura" do modelo, mas representa fielmente a latência percebida pelo sistema. Optei por manter a medição assim, já que em produção é o tempo total que importa para dimensionar throughput.

## Nível 2 — Modelo e limites do free tier

### Troca forçada de modelo por quota diária
O lote esbarrou em `429 RESOURCE_EXHAUSTED` com o detalhe `GenerateRequestsPerDayPerProjectPerModel-FreeTier, quotaValue: 20`. O `gemini-3.6-flash`, usado no Nível 1, tem apenas **20 requisições por dia** no free tier.

O agravante é de design: com function calling, **cada cliente consome várias requisições**, não uma. Cada ida e volta (modelo pede ferramenta → recebe resultado → pede outra → gera parecer) conta separadamente. Com 2 a 4 ferramentas por cliente, 10 clientes consomem entre 30 e 50 requisições, mais que o dobro do teto.

Tentei migrar para `gemini-2.5-flash`, que retornou `404: no longer available to new users`. O modelo aparece em `client.models.list()`, mas não está liberado para contas novas, disponibilidade por conta é diferente de existência do modelo, algo que a listagem não distingue.

Acabei em **`gemini-3.5-flash-lite`**, validado com uma chamada mínima antes de rodar o lote. Flash-Lite tem quota diária na casa dos milhares.

**Trade-off assumido:** Flash-Lite é um modelo mais leve que o Flash. Aceitei perda potencial de qualidade nos pareceres em troca de conseguir rodar o lote completo. Na prática o resultado foi melhor do que eu esperava: nenhum erro de leitura numérica, nenhuma confusão de moeda, e nenhuma resposta malformada em 10 execuções. Registro que o Nível 1 usou `gemini-3.6-flash` e o Nível 2 usou `gemini-3.5-flash-lite`, os pareceres dos dois níveis não são diretamente comparáveis por isso.

### Cache de pareceres
Depois de esgotar a quota, implementei cache em disco (`outputs/cache_pareceres.json`) gravado a cada cliente processado, não apenas ao final do lote. Se a execução for interrompida no cliente 6, os 5 anteriores ficam salvos e a próxima execução só processa os restantes.

Isso também protege a Parte D: o `confronto.py` lê os pareceres do JSON salvo em vez de re-executar o agente, então ajustar a análise de divergências não consome quota.

## Nível 2 — Execução em lote

### Evidência de decisão do agente
O enunciado exige que o agente decida quais ferramentas chamar. O log de chamadas mostra três padrões distintos entre os 10 clientes:

- **CLI-014**: apenas `historico_cliente` (1 ferramenta). O histórico bastou para fundamentar o parecer.
- **Casos de valor atípico** (CLI-023, 028, 013, 005, 026): `historico_cliente` → `perfil_canal`. Para avaliar se um valor alto é anômalo, buscou o padrão do cliente e a distribuição de canais.
- **Casos de fracionamento** (CLI-029, CLI-017): `operacoes_do_dia` → `historico_cliente`. **Inverteu a ordem**, indo direto ao dia sinalizado antes de buscar contexto geral.

A inversão de ordem é a evidência mais forte: um script executaria sempre a mesma sequência. O agente adaptou a estratégia de investigação ao tipo de alerta. Distribuição final: 1 cliente com 1 ferramenta, 7 com 2, e 2 com 3.

### Chamada redundante observada
Numa execução de teste com `gemini-3.6-flash`, o agente chamou `historico_cliente` duas vezes para o mesmo cliente, dados que já tinha. O AFC não impede repetição de consultas, e cada repetição custa tokens e latência (4.108 tokens contra 2.984 numa execução sem repetição).

**O que faria com mais tempo:** memorizar as chamadas de ferramenta dentro de uma mesma sessão, o `_log_chamadas` já registra ferramenta e argumentos, então bastaria consultá-lo antes de executar e devolver o resultado guardado quando a chamada fosse idêntica. Validaria comparando a contagem de chamadas antes e depois em casos onde a repetição foi observada.

### Custo e latência
15.325 tokens totais para 10 clientes (média de 1.532 por cliente). Latência total de 80,77s, média de 8,08s, com dispersão grande: mínimo 2,41s e máximo 39,47s.

Os dois outliers de latência (CLI-013 com 17,9s e CLI-017 com 39,47s) não refletem complexidade do caso, ambos chamaram 2 ferramentas, como a maioria. O CLI-017 inclui 5s de espera do retry após um erro transitório. A variância vem da instabilidade da API no free tier, não do trabalho do agente.

## Nível 2 — Confronto entre regra e modelo

### Critério de correspondência adotado

| Situação segundo as regras | Risco esperado |
|---|---|
| Sinalizado pelas duas regras | alto |
| Sinalizado por fracionamento | alto |
| 2+ operações de valor atípico | medio |
| 1 operação de valor atípico | baixo |

**Justificativa:** fracionamento é tipologia de intenção deliberada, estruturar operações abaixo de um limite raramente tem explicação inocente, então implica risco alto por si só. Valor atípico é ambíguo isoladamente (venda de um bem, herança, bônus), então a gravidade escala com a recorrência: um evento é pontual, vários configuram padrão.

### Resultado: 60% de concordância (6 de 10)

Mais relevante que a taxa: **todas as 4 divergências apontam na mesma direção**; o agente foi sempre mais brando que a regra, nunca mais severo. Isso é viés sistemático, não ruído aleatório.

As divergências se dividem em dois grupos de naturezas opostas.

### Divergências onde o agente parece certo (CLI-028, CLI-013)
Regra dizia médio, agente disse baixo.

O argumento do agente no CLI-028: as operações sinalizadas (maior: R$ 27.715) são consistentes com a faixa de movimentação geral do cliente, em canais tradicionais, sem concentração em espécie.

Isso expõe uma limitação estrutural da Regra 2: a mediana é sensível quando o cliente tem muitas operações pequenas. Basta ter várias de R$ 4 mil para que qualquer operação de R$ 25 mil ultrapasse 5x a mediana — mesmo sendo movimentação normal para quem transaciona R$ 88 mil no período. A regra compara a operação com um único estimador estatístico; o agente comparou com o perfil inteiro.

**Conclusão:** falsos positivos da regra. O agente agregou contexto que a regra não tem como capturar.

### Divergências onde a regra parece certa (CLI-029, CLI-017)
Regra dizia alto, agente disse médio.

Aqui há **contradição interna no parecer do agente**. No CLI-017 ele escreve que a dinâmica "sugere uma tentativa intencional de evitar controles automáticos" e classifica a tipologia como "Smurfing", e ainda assim atribui risco médio. No CLI-029, o mesmo: reconhece que "o padrão é característico de evitação de controles" e classifica como médio.

Se o próprio agente identifica estruturação intencional, a conclusão deveria escalar para alto. O raciocínio e o veredito não se sustentam mutuamente.

### Observação de calibragem
O agente **não usou "alto" em nenhum dos 10 casos**, apenas "medio" (7) e "baixo" (3). Combinado com o fato de todas as divergências serem na direção branda, isso sugere ancoragem em "médio" como default seguro.

Duas hipóteses: (a) a instrução de sistema não definiu o que caracterizaria risco alto, deixando o modelo sem referência de escala; (b) o Flash-Lite é conservador por natureza em julgamentos de risco.

**O que faria com mais tempo:** a hipótese (a) é testável e barata, bastaria adicionar critérios explícitos de escalação na instrução de sistema ("classifique como alto quando houver indício de intenção deliberada de evitar controles") e reexecutar o lote, comparando a distribuição de risco antes e depois. Se a distribuição mudasse, o problema era de prompt; se não, seria característica do modelo, e valeria testar um modelo mais capaz.

Isso importa em produção: um sistema de PLD que nunca escala para risco alto é operacionalmente inútil, porque não diferencia o que precisa de ação imediata do que precisa apenas de monitoramento.

## Nível 3 — Trilha C: interface conversacional

### Escolha da trilha
Escolhi a Trilha C (interface conversacional em Streamlit) sobre as trilhas A (multiagente) e B (servidor MCP).

**Justificativa:** já tenho experiência prática com Streamlit, de faculdade e trabalho, enquanto minha exposição a LangGraph/LangChain foi apenas em curso. Num prazo de 24h, preferi entregar algo funcional com uma ferramenta que domino a arriscar uma que ainda não uso com fluência. O enunciado é explícito que prefere "dois níveis sólidos e bem documentados a três pela metade", e a mesma lógica se aplica à escolha de trilha.

### Duplicação deliberada de código
O Nível 3 tem seus próprios `contexto.py` e `ferramentas.py`, que repetem boa parte da lógica de `nivel_2/dados.py` e `nivel_2/tools.py`.

**Motivo:** `nivel_2/agente.py` executa código no nível do módulo (carrega dados, aplica regras, imprime resultados). Importá-lo a partir do app dispararia tudo isso a cada reexecução do Streamlit. As alternativas eram refatorar o Nível 2, arriscando regressão no que já estava validado e entregue, ou isolar o Nível 3. Escolhi isolar.

**O que faria diferente desde o começo:** extrair um pacote compartilhado (`comum/`) com carregamento, tratamento, regras e ferramentas, consumido pelos três níveis. A duplicação aqui é dívida técnica assumida conscientemente sob restrição de prazo, não descuido.

Como efeito colateral positivo, o Nível 3 ganhou uma quarta ferramenta que não existe no Nível 2: `comparar_clientes`, que atende ao caso de uso "comparar dois clientes" citado pelo enunciado. Sem ela, o modelo precisaria chamar `historico_cliente` duas vezes e fazer a subtração, cálculo que deve ficar em pandas.

### Memória da conversa
O Streamlit reexecuta o script inteiro a cada interação, então o objeto de chat precisa viver no `st.session_state` para o histórico persistir. Um detalhe que causou erro em tempo de execução: o `client` do SDK também precisa ficar no `session_state`. Criado como variável local dentro da função que monta o chat, ele era coletado como lixo ao fim da função, e a sessão guardada apontava para uma conexão fechada (`RuntimeError: Cannot send a request, as the client has been closed`).

### Economia de requisições
Com quota diária apertada, o app injeta o ranking e o resumo dos clientes sinalizados diretamente na instrução de sistema. Assim o modelo não precisa gastar chamadas de ferramenta apenas para saber quem está na lista.

O efeito é observável: ao pedir explicação do CLI-029, o agente chamou apenas `operacoes_do_dia`, já sabendo pelo resumo que o alerta era de fracionamento naquela data. E na pergunta de acompanhamento ("qual dos dois é mais preocupante?"), não chamou ferramenta nenhuma, respondeu a partir do que já estava no contexto da conversa.

### A interface encena o confronto da Parte D
A barra lateral carimba, em cada caso, o nível de risco que as **regras** implicam — usando o mesmo critério do `confronto.py`. A área principal traz o julgamento do **agente**. O confronto que a Parte D produz em CSV fica visível lado a lado na tela: a regra carimbou "alto" no CLI-029, e o analista pode perguntar ao agente e ver onde ele discorda.

### Granularidade da instrumentação
A trilha de auditoria mostrou `comparar_clientes · historico_cliente · historico_cliente` numa única resposta. São três execuções registradas, mas **uma** decisão do modelo, a `comparar_clientes` invoca `historico_cliente` internamente duas vezes, e todas as funções estão instrumentadas.

O log registra corretamente o que foi executado, mas superestima quantas decisões o agente tomou. Com mais tempo, separaria uma versão interna sem registro para as chamadas em cascata.

### Observações sobre o comportamento do modelo

**O viés de calibragem se repetiu com outro modelo.** Ao gerar o parecer do CLI-017 (caso de fracionamento), o Nível 3 classificou como "Médio-Alto" — assim como o Nível 2 classificou os casos de fracionamento como "medio", apesar de identificar smurfing e recomendar bloqueio cautelar.

Isso é informativo: são modelos diferentes (`gemini-3.5-flash-lite` no Nível 2, `gemini-3.1-flash-lite` no Nível 3) com o mesmo comportamento. Enfraquece a hipótese de que seja característica do modelo e reforça a de que falta um critério explícito de escalação na instrução de sistema, nenhuma das duas define o que caracterizaria risco alto.

**O modelo inventou uma categoria fora da escala.** "Médio-Alto" não é um dos três valores pedidos (baixo/medio/alto). Num pipeline com parsing estruturado, isso quebraria a validação; no Nível 2 o `parse_parecer` captaria, mas o app conversacional não valida a saída, já que a resposta é texto livre para leitura humana.

**O modelo preencheu uma lacuna com invenção.** No mesmo parecer, afirmou que 08/03/2026 seria "a data da abertura da conta ou primeira movimentação registrada". Nenhuma ferramenta retorna data de abertura de conta, esse campo não existe na base. O modelo inferiu e apresentou como fato, com ressalva fraca ("ou").

Mesmo com instruções explícitas para interpretar apenas o que as ferramentas retornam, o modelo completou uma informação ausente. Num contexto real de PLD, um parecer que afirma algo sobre abertura de conta sem base documental é um problema sério, o tipo de erro que exige revisão humana obrigatória antes de qualquer decisão.

**O que faria com mais tempo:** uma etapa de verificação que confronta afirmações factuais do parecer contra os campos realmente disponíveis na base, sinalizando menções a dados que nenhuma ferramenta poderia ter fornecido.
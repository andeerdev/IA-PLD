# Uso de IA

## Ferramentas utilizadas

- Claude (Anthropic) — usado como par de desenvolvimento ao longo dos três níveis. Boa parte do código foi escrita com auxílio da ferramenta, num formato de construção guiada: eu definia o que precisava, discutíamos a abordagem e os trade-offs, e cada bloco era revisado e explicado antes de eu integrá-lo e executá-lo. As decisões de arquitetura e de critério foram minhas; a execução, os testes e a depuração dos erros também.

## Para que usei

- Entender a lógica das regras determinísticas (fracionamento e valor atípico) antes de implementar, incluindo discutir casos de borda e como validá-las.
- Revisão de código linha a linha: entender comandos específicos do pandas e do Python que eu não dominava totalmente.
- Debugar erros reais que apareceram durante o desenvolvimento.
- Discutir trade-offs de decisões sem resposta única: como tratar a data ausente, qual critério usar no ranking de clientes sinalizados, se valia adotar um framework de agentes ou o SDK nativo.
- Estruturar a documentação (`DECISOES.md`, `ENTREGA.yaml`, `README.md`).

## Onde a IA me levou por um caminho que eu tive que corrigir ou questionar

- A IA sugeriu inicialmente usar o modelo `gemini-2.0-flash`, que foi descontinuado pela própria Google durante o desenvolvimento (retornou erro 404). Precisei buscar qual era o modelo atual disponível (`gemini-3.6-flash`) para seguir.
- Ao montar o primeiro prompt para a análise de risco, percebi que a LLM estava confundindo o valor já convertido para BRL com a moeda original (USD) na justificativa. Identifiquei essa inconsistência ao revisar os resultados e trouxe isso para discussão, o que levou ao ajuste do prompt na versão 2 para corrigir o problema.
- No Nível 2, a IA chegou a sugerir criar um notebook para a Parte A. Percebi, relendo a estrutura obrigatória do enunciado e o exemplo do `ENTREGA.yaml`, que o Nível 2 é composto apenas por arquivos `.py` — o notebook teria ficado fora do padrão pedido.
- Ao esgotar a quota diária do free tier, a IA recomendou migrar para `gemini-2.5-flash`, que retornou erro 404 por não estar disponível para contas novas. Foi necessário testar os modelos candidatos com chamadas mínimas antes de escolher, em vez de confiar na listagem de modelos disponíveis — `client.models.list()` retorna modelos que a chave não necessariamente pode usar.
- No Nível 3, a primeira versão da interface veio com problemas de contraste (texto invisível sobre o fundo claro, por herdar cores do tema escuro do Streamlit) e com o campo de entrada visualmente quebrado. Apontei os dois casos e foram corrigidos em iterações seguintes.
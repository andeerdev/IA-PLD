# Uso de IA

## Ferramentas utilizadas

- Claude (Anthropic) — usado como par de desenvolvimento ao longo do Nível 1, em formato de revisão guiada: discutíamos a lógica, os erros e as decisões de cada etapa antes de eu seguir para a próxima. O código final foi escrito e executado por mim, célula por célula, na minha própria máquina.

## Para que usei

- Entender a lógica das regras determinísticas (fracionamento e valor atípico) antes de implementar, incluindo discutir casos de borda e como validá-las.
- Revisão de código linha a linha: entender comandos específicos do pandas e do Python que eu não dominava totalmente.
- Debugar erros reais que apareceram durante o desenvolvimento.
- Estruturar a documentação (`DECISOES.md`, `ENTREGA.yaml`).

## Onde a IA me levou por um caminho que eu tive que corrigir ou questionar

- A IA sugeriu inicialmente usar o modelo `gemini-2.0-flash`, que foi descontinuado pela própria Google durante o desenvolvimento (retornou erro 404). Precisei buscar qual era o modelo atual disponível (`gemini-3.6-flash`) para seguir.
- Ao montar o primeiro prompt para a análise de risco, percebi que a LLM estava confundindo o valor já convertido para BRL com a moeda original (USD) na justificativa. Identifiquei essa inconsistência ao revisar os resultados e trouxe isso para discussão, o que levou ao ajuste do prompt na versão 2 para corrigir o problema.
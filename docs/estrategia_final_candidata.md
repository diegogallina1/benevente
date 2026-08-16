# Estratégia candidata final para teste prospectivo

## Decisão

Congelar, para acompanhamento em carteira-sombra, a regra **Momentum Anual
Diversificado Ajustado por Volatilidade**. Esta é a melhor hipótese de
pesquisa obtida na bateria livre, mas não é uma promessa de retorno nem está
aprovada para ordens reais.

## Regra congelada

Na primeira sessão de negociação de cada janeiro:

1. Formar o universo de todos os instrumentos do painel B3 que tenham 252
   sessões anteriores de índice de retorno total observável.
2. Calcular o retorno total dos últimos 12 meses de cada instrumento.
3. Converter esses retornos em ranking percentual transversal.
4. Atribuir a cada instrumento peso proporcional a
   `ranking_de_momento² / volatilidade_dos_12_meses`.
5. Normalizar os pesos para 100%. Nenhum ativo elegível é excluído pela regra.
6. Manter a carteira até a primeira sessão de janeiro seguinte e descontar
   0,15% por unidade de giro anual como cenário-base de custo.

Não há filtro fundamental, de qualidade, setor, emissor, limite de peso ou
número máximo de ativos. A única condição é haver histórico suficiente para
calcular o sinal sem acessar o futuro.

## Evidência disponível

| Janela | Estratégia | CDI | Diferença |
| --- | ---: | ---: | ---: |
| 2015–2020 | 20,84% a.a. | 8,60% a.a. | +12,24 p.p. a.a. |
| 2021–2025 | 13,44% a.a. | 10,87% a.a. | +2,56 p.p. a.a. |
| 2015–2025 | 17,75% a.a. | 9,63% a.a. | +8,12 p.p. a.a. |
| 2024–2025 | 9,72% a.a. | 12,48% a.a. | -2,76 p.p. a.a. |

O giro médio foi aproximadamente 105% ao ano. O pior retorno anual da
amostra completa foi -8,32%. Esses números usam retorno total ajustado de
fonte pública e precisam ser reconciliados com uma fonte licenciada antes de
qualquer uso institucional.

## Interpretação responsável

A estratégia venceu o CDI nos dois blocos principais, mas perdeu no corte
mais recente. Como seus parâmetros vieram de uma busca de múltiplas regras,
o resultado histórico pode conter viés de seleção. A estratégia é congelada
agora justamente para que seu próximo resultado seja independente da escolha.

## Critério para promoção ou rejeição

Após 12 e 24 meses de carteira-sombra, comparar retorno líquido, giro, custos
reais, queda máxima e retorno relativo ao CDI. Se o desempenho não for
compatível com a evidência histórica após custos observados, a candidata é
rejeitada, sem alterar seus parâmetros retrospectivamente.

# Experimento de MVO robusto — 13/08/2026

## Objetivo

Testar se ajustes de estimação do MVO podem superar, sem uso de informação futura,
o MVO-base e o CDI no painel público de retornos totais ajustados (Yahoo Finance)
utilizado pelo projeto.

## Protocolo reproduzível

- Decisão: primeiro pregão de cada janeiro, de 2015 a 2025.
- Dados usados na decisão: apenas os 252 pregões anteriores.
- Custos: 0,10% de corretagem mais 0,05% de deslizamento por giro.
- Universo: instrumentos com histórico completo na janela de estimação, sem teto por
  emissor, por posição ou por número de ativos.
- Grade pré-definida: 48 combinações de aversão ao risco (`2,5`, `5`, `10`, `20`),
  redução de ruído na matriz de covariância (`0%`, `25%`, `50%`, `75%`) e prior de
  momentum (`0`, `10%`, `25%`).
- Escolha de parâmetros: 2015–2020. Validação bloqueada: 2021–2025.

## Resultado principal

A variante que venceu no treino foi `gamma=2,5`, sem redução de ruído e sem prior
de momentum. Ela obteve CAGR de 77,0% no treino, mas **-22,3% a.a.** na validação.
Isso reprova a variante: é um exemplo de ajuste excessivo, não uma candidata para
uso ou para destaque no site.

Entre as 48 variações, 12 superaram simultaneamente CDI e MVO-base no bloco de
validação. A melhor nesse critério foi `gamma=20`, sem redução de ruído e com prior
de momentum de 25%:

| Janela | MVO robusto | CDI | MVO-base |
|---|---:|---:|---:|
| 2021–2025 (CAGR) | 14,6% | 10,9% | 8,1% |
| 2015–2020 (CAGR) | 35,1% | 8,6% | 48,3% |

Ela venceu ambos os referenciais em somente 3 dos 11 anos individuais. Logo, ela
é uma observação de robustez para pesquisa, não uma regra que possa prometer vitória
anual nem substituir o MVO-base.

## Conclusão honesta

Nenhuma das 48 variantes pré-definidas superou CDI e MVO-base em todos os anos.
O experimento reforça que procurar parâmetros até encontrar uma curva vencedora é
insuficiente: a seleção precisa ocorrer antes do bloco de validação e ser confirmada
em novas janelas. Os arquivos anuais e a conclusão estão em
`artifacts/enhanced_mvo_20260813/` e o código em `research_enhanced_mvo.py`.

## Limitações

O painel utiliza preços ajustados públicos e pode conter viés de sobrevivência,
cobertura incompleta de eventos corporativos e lacunas de liquidez. Ele é adequado
para pesquisa exploratória; não substitui reconciliação com fonte institucional nem
é recomendação de investimento.

# Validação retrospectiva da política de risco por perfil

A seleção anual e o tamanho do risco foram separados. O motor anual continua escolhendo os ativos com informação disponível na decisão. A política de perfil define o máximo em ações, a meta de volatilidade, o teto por ativo e o mínimo de cinco emissores. Uma camada intranual fixa observa apenas o Ibovespa até o fechamento anterior e pode deslocar parte da exposição para CDI. Ela não troca ativos durante o ano e não usa notícias ou LLM.

## Resultado de 2015 a 2025

| Perfil | CAGR sem proteção | CAGR protegido | CDI | Queda sem proteção | Queda protegida |
|---|---:|---:|---:|---:|---:|
| Conservador | 11,73% | 11,20% | 9,61% | -18,89% | -9,86% |
| Equilibrado | 12,99% | 12,31% | 9,61% | -28,11% | -17,89% |
| Arrojado | 14,14% | 13,63% | 9,61% | -37,60% | -29,29% |

Os valores incluem dez pontos-base por unidade de mudança da exposição. O imposto intranual ainda não foi modelado. A proteção reduziu a queda máxima em todos os perfis e também reduziu o CAGR. Esse é o compromisso observado: menor perda extrema em troca de parte do retorno. Nenhum perfil superou o MVO independente calculado nesta experiência.

Uma simulação de blocos circulares reordenou pares de retornos diários em blocos de 21 pregões, com 5.000 trajetórias e sementes registradas. A probabilidade de o CAGR protegido superar o CDI pareado foi de 82,5% no conservador, 80,5% no equilibrado e 79,7% no arrojado. O percentil de 2,5% da queda máxima foi, respectivamente, -14,2%, -27,7% e -49,1%. A simulação preserva dependência serial curta, mas apenas reorganiza regimes já observados. Ela mede sensibilidade e não cria evidência futura.

A política anual baseada somente em volatilidade observada em janeiro não reduziu a queda de 2020. Essa hipótese foi rejeitada porque janeiro não continha o estresse que apareceu depois. A camada intranual reage com atraso de uma sessão. Ela não antecipou a Covid-19 e não deve ser descrita como previsão.

## Estado da evidência

O teste é retrospectivo porque a política foi desenhada depois das crises presentes na amostra. O arquivo `data/benevente_profile_risk_v1_registration.json` congela regras, entradas e hashes em 20/08/2026. O restante de 2026 é piloto operacional. A amostra confirmatória começa no primeiro pregão de 2027 e exige pelo menos três decisões anuais completas antes de qualquer afirmação de desempenho prospectivo.

Arquivos de reprodução:

- `portfolio_risk.py`;
- `profile_intrayear_risk.py`;
- `validate_risk_system.py`;
- `artifacts/risk_system_validation_20260820/summary.json`;
- `artifacts/risk_system_validation_20260820/annual_profile_comparison.csv`.

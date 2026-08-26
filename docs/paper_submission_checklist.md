# Pacote final de artigos do Benevente

Este documento separa o que está fechado no repositório do que depende de ação dos autores ou das plataformas de submissão.

## Fonte única de evidência

- `artifacts/paper_release/paper_evidence.json` é a fonte comum dos números usados nos dois manuscritos.
- `artifacts/paper_release/paper_release_manifest.json` registra o SHA-256 do pacote e de suas entradas.
- A estratégia canônica é o Benevente 1. O Benevente 2 permanece extensão experimental de controle de risco.
- A janela de 2015 a 2025 é evidência retrospectiva de desenvolvimento. Não é validação prospectiva.

## BTech 2026

- **Fontes atualizadas em 25/08/2026** com o resultado posterior (Seção 4.1.1 no BTech; abstract e seção de escolha de regra no CiFer). Os arquivos finais em outputs/ (.docx/.pdf/.tex e o suplemento anônimo) foram regenerados em 26/08/2026 a partir das fontes atualizadas (tools/build_article_documents.py + tools/build_ieee_anonymous_supplement.py; PDF IEEE compilado com Tectonic 0.17.0, PDF BTech exportado do .docx via LibreOffice) e conferidos por extração de texto: Seção 4.1.1, 256 candidatos, DSR 0,777 e a frase de contrato presentes em ambos.

- Manuscrito identificado em português, conforme o template oficial.
- Entre 6.000 e 8.000 palavras, incluindo referências.
- Times New Roman 12, espaçamento 1,5, margens superior e esquerda de 3 cm, inferior e direita de 2 cm.
- Referências em APA 7.
- Negrito restrito aos títulos das seções e aos cabeçalhos das tabelas; o corpo do texto permanece uniforme.
- Tabelas e demais ilustrações em preto e branco, com identificação, fonte e nota quando necessárias.
- Objetivo, motivação, método, resultado e contribuição aparecem na introdução.
- Produto tecnológico B2B, utilidade, inovação e hipótese de monetização são tratados de forma explícita.

Antes de enviar, os autores devem confirmar no sistema do congresso:

1. nomes, afiliações e ordem definitiva dos autores;
2. eixo temático escolhido;
3. declaração exigida sobre uso de inteligência artificial, se houver campo próprio;
4. nomes, afiliações e metadados do PDF consistentes com a autoria informada;
5. arquivo editável solicitado pela plataforma.
6. endereços públicos do sistema e do repositório presentes no manuscrito.

## Terceiro manuscrito — Declared Beats Searched (rascunho novo)

- Fonte em `paper/declared_over_searched_2026.md`, em inglês, alvo IEEE CiFer 2027.
- Tese: a seleção aninhada tem um limite de capacidade no número de candidatos;
  36 → 256 candidatos, com insumos idênticos, custou 2,63 p.p. ao ano e derrubou
  o Sharpe deflacionado de 0,957 para 0,777. A resposta é declarar e congelar.
- Todos os números são verificados por máquina: `tools/verify_published_numbers.py`
  compara cada afirmação do manuscrito e do site com os artefatos versionados e
  sai com erro se qualquer uma divergir.
- Pendências dos autores: metadados, conversão a `IEEEtran`, ajuste de extensão.
- Os dois manuscritos originais descrevem a regra da busca aninhada, que foi
  substituída; antes de qualquer submissão deles, decidir entre atualizá-los ou
  acrescentar um parágrafo reconhecendo o resultado posterior.

## IEEE CiFer 2027

Destino de submissão: IEEE Symposium on Computational Intelligence for
Financial Engineering and Economics (IEEE CiFer), realizado dentro do evento
guarda-chuva IEEE SSCI 2027. No sistema, selecionar o simpósio CiFer, e não uma
área genérica do SSCI.

- Arquivo de avaliação anônimo em inglês.
- Classe `IEEEtran`, conferência, corpo em 10 pontos e duas colunas.
- Meta editorial provisória para short paper: até 4 páginas de conteúdo mais 1 página de referências, sem alteração artificial de fonte ou espaçamento. O limite deve ser reconfirmado no edital do SSCI 2027 quando ele for publicado.
- Ênfase tipográfica restrita à hierarquia produzida pelo IEEEtran; não há frases em negrito no corpo do artigo.
- Quatro braços empíricos: nomeado, anonimizado, determinístico e monolítico.
- Declaração de compartilhamento de dados/código na introdução.
- Declaração transparente de assistência generativa no manuscrito.

Antes de enviar, os autores devem confirmar no sistema da IEEE:

1. nomes, afiliações, correios e ORCID definitivos;
2. conflitos de interesse;
3. simpósio IEEE CiFer — Computational Intelligence for Financial Engineering
   and Economics — dentro do SSCI;
4. arquivo suplementar anônimo;
5. conformidade do PDF no IEEE PDF eXpress, quando o código da conferência estiver disponível;
6. substituição do arquivo anônimo por versão de câmera com autoria apenas após o aceite.

## O que não deve ser prometido

- retorno futuro ou superação garantida de CDI, Ibovespa ou MVO;
- validação prospectiva inexistente;
- cobertura institucional de eventos societários ainda não reconciliada;
- alfa adicional do modelo de linguagem;
- superioridade do Benevente 2 em retorno.

# Governança da proposta de carteira em produção

O Benevente Wealth System produz uma **proposta de pesquisa para revisão humana**. Não se conecta a uma corretora, não envia ordens e não garante retorno. A decisão e a execução são sempre do investidor, dentro de seu perfil e de orientação profissional quando aplicável.

## Portões obrigatórios

1. Preencher a política de produção com valor, horizonte, limites e confirmação explícita de ciência.
2. Gerar fundamentos TTM a partir de ITR oficial da CVM e DFP anterior, usando o mapa contábil específico para companhias não financeiras ou instituições financeiras, e verificar a data contábil (`as_of_date`) e a data de divulgação (`available_date`).
3. Arquivar o snapshot de mercado e o histórico de preços atribuídos; para não financeiras, anexar métricas verificadas de dívida/EBITDA e cobertura de juros.
4. Revisar a tela fundamental, pesos propostos, concentração, liquidez, quantidade/lote e custo estimado.
5. Aprovar cada ordem de modo independente e lançá-la manualmente na plataforma da corretora.
6. Guardar as notas de corretagem e reconciliar preço, quantidade e taxas realizadas contra a proposta.

## Dados e custos

- DFP anual da CVM: <https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp>.
- ITR trimestral da CVM: <https://dados.cvm.gov.br/dados/cia_aberta/doc/itr/DADOS/>. A proposta usa o ITR mais recente cuja `DT_RECEB` seja anterior ou igual à data de decisão, com ponte TTM contra DFP anual.
- A página de custos da Clear informa corretagem zero para os produtos elegíveis e detalha as tarifas de negociação: <https://corretora.clear.com.br/custos/>.
- O modelo inicial usa 0,0300% por lado para tarifas B3 de operação regular, antes de slippage. A nota de corretagem é a fonte final para a taxa efetivamente cobrada.

## Limites regulatórios

A recomendação individualizada de valores mobiliários é atividade regulada. A CVM explica o escopo do consultor de valores mobiliários e ressalta que algoritmos não afastam suas responsabilidades: <https://www.gov.br/investidor/pt-br/investir/como-investir/profissionais-do-mercado/consultor-de-valores-mobiliarios>. Para oferta a terceiros, revisar a Resolução CVM 19 e obter a estrutura jurídica e regulatória adequada: <https://conteudo.cvm.gov.br/legislacao/resolucoes/resol019.html>.

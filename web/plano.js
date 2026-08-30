// Gerado por tools/build_mapa_prototype.py. Não edite à mão.
// Separado do documento porque a CSP do site é script-src 'self'.

/* Trava de conveniência, não de segurança. A comparação roda no navegador e o
   conteúdo é sintético: quem abrir o código passa. Ela existe para o visitante
   casual não cair numa tela inacabada. Nada real pode ser protegido assim, se um dia esta página mostrar carteira de cliente, a trava tem de sair e dar
   lugar a autenticação de verdade no servidor.
   A senha não aparece em texto claro aqui só para não vazar por leitura casual
   do fonte; o hash não a torna secreta. */
(function () {
  const ESPERADO = "4c073be62dd2eeca3d94f45932aef78e01d815664e90d0144b7ed10978f8b801";
  const trava = document.getElementById("trava");
  const app = document.getElementById("app");
  const erro = document.getElementById("trava-erro");

  function liberar() {
    trava.style.display = "none";
    app.classList.remove("hidden");
  }
  try { if (sessionStorage.getItem("benevente-app") === "1") liberar(); } catch (e) {}

  async function conferir() {
    const valor = document.getElementById("senha").value;
    let digest;
    try {
      const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(valor));
      digest = [...new Uint8Array(bytes)].map(b => b.toString(16).padStart(2, "0")).join("");
    } catch (e) {
      erro.textContent = "Este navegador não permite conferir a senha nesta página.";
      return;
    }
    if (digest !== ESPERADO) {
      erro.className = "ajuda ruim";
      erro.textContent = "Senha incorreta.";
      return;
    }
    try { sessionStorage.setItem("benevente-app", "1"); } catch (e) {}
    liberar();
  }

  document.getElementById("entrar").onclick = conferir;
  document.getElementById("senha").onkeydown = e => { if (e.key === "Enter") conferir(); };
})();

const DADOS = {"questionnaire":{"method":"A restrição mais apertada define o perfil. Não há pontuação: cada resposta impõe um teto e vale o menor deles.","worst_measured_drawdown":{"ultraconservador":-0.0081,"conservador":-0.0917,"equilibrado":-0.1788,"arrojado":-0.2895},"questions":[{"key":"horizonte","prompt":"Quando você vai precisar desse dinheiro?","help":"É a única resposta que nenhuma estratégia contorna: quem precisa sacar em um ano não pode esperar uma queda se recuperar, por melhor que seja a carteira.","kind":"escolha","options":[{"value":"ate_2","label":"Em até dois anos","brief":"até 2 anos","caps_profile":"conservador","note":"com prazo curto, uma queda não tem tempo de se recuperar"},{"value":"2_a_5","label":"Entre dois e cinco anos","brief":"2 a 5 anos","caps_profile":"equilibrado","note":"cinco anos cobrem a maior parte das quedas medidas, mas não todas"},{"value":"5_mais","label":"Em cinco anos ou mais","brief":"5+ anos","caps_profile":null,"note":""}]},{"key":"queda","prompt":"Qual a maior queda que você aguentaria sem vender?","help":"Na janela medida, o ultraconservador caiu 0,8%, o conservador 9,2%, o equilibrado 17,9% e o arrojado 28,9% no pior momento. Vender no fundo é o que transforma queda em prejuízo.","kind":"escolha","options":[{"value":"ate_2","label":"Até 2% — quero quase não sentir","brief":"queda até 2%","caps_profile":"ultraconservador","note":"só o ultraconservador ficou dentro desse limite na janela medida"},{"value":"ate_10","label":"Até 10% — abaixo disso eu não durmo","brief":"queda até 10%","caps_profile":"conservador","note":"só o conservador ficou dentro desse limite na janela medida"},{"value":"ate_20","label":"Até 20% — incomoda, mas eu seguro","brief":"queda até 20%","caps_profile":"equilibrado","note":"o arrojado passou de 28% na pior queda, além do que foi declarado"},{"value":"acima_20","label":"Mais de 20% — eu entendo que faz parte","brief":"queda acima de 20%","caps_profile":null,"note":""}]},{"key":"reserva","prompt":"Você já tem reserva de emergência separada desse dinheiro?","help":"Sem reserva, o primeiro imprevisto vira uma venda forçada — e venda forçada acontece justamente quando o mercado está ruim.","kind":"escolha","options":[{"value":"sim","label":"Sim, está separada","brief":"com reserva","caps_profile":null,"note":""},{"value":"nao","label":"Ainda não","brief":"sem reserva","caps_profile":"conservador","note":"sem reserva, este dinheiro é a reserva na prática"}]},{"key":"retirada","prompt":"Você vai retirar deste dinheiro todo mês?","help":"Retirada mensal muda o problema: obriga a manter liquidez e a vender em momento ruim se a liquidez acabar.","kind":"escolha","options":[{"value":"nao","label":"Não, é para deixar rendendo","brief":"sem retirada","caps_profile":null,"note":""},{"value":"sim","label":"Sim, retiro um valor por mês","brief":"com retirada","caps_profile":"equilibrado","note":"retirada recorrente exige caixa e reduz o que pode oscilar"}]},{"key":"prejuizo","prompt":"Você tem prejuízo acumulado a compensar em ações?","help":"Prejuízo passado abate o imposto das vendas de agora, dentro do mesmo tipo de investimento. Se existir e não for informado, o custo da mudança sai maior do que é de verdade.","kind":"valor","options":[]},{"key":"travar","prompt":"Alguma posição que você não quer ou não pode vender?","help":"Carência, ação de família, participação com significado próprio. O mapa respeita e registra — o que ele não faz é fingir que a restrição não existe.","kind":"texto","options":[]}]},"profiles":{"ultraconservador":{"adequar":{"path":"adequar","path_label":"Adequar a carteira ao perfil","track_record_applies":true,"carried_loss_brl":0.0,"locked_tickers":[],"total_brl":700000,"alignment":0.6192,"turnover_brl":145528.0,"transition_cost_brl":291.05,"transition_tax_brl":0.0,"transition_total_brl":291.05,"transition_cost_pct":0.00042,"exempt_month_assumed":false,"tax_is_complete":false,"positions_without_cost_basis":[{"ticker":"WEGE3","sale_brl":180000.0,"sale_fraction":1.0,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"unpriced_sale_brl":180000.0,"pending_resolution":{"positions":[{"ticker":"WEGE3","sale_brl":180000.0,"sale_fraction":1.0,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"buckets":{"renda_variavel":{"other_gain_brl":-147703.15,"rate":0.15,"exempt_month":false,"carried_loss_brl":0.0}},"fixed_brl":291.05},"tax_by_bucket":{"fora_do_escopo":{"realised_gain_brl":-9000.0,"tax_brl":0.0},"renda_variavel":{"realised_gain_brl":-147703.15,"tax_brl":0.0}},"fgc_breaches":{"Beta":310000.0},"fgc_exposure":{"Beta":310000.0},"sources":["Open Finance (compartilhamento de investimentos)","extrato da Área do Investidor da B3","lançamento manual"],"moves":[{"ticker":"WEGE3","action":"vender","from_brl":180000,"to_brl":0.0,"delta_brl":-180000.0,"reason":"não faz parte da carteira do perfil","trade_cost_brl":180.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":["imposto ainda não calculado: falta informar quanto você pagou"]},{"ticker":"MGLU3","action":"vender","from_brl":25000,"to_brl":0.0,"delta_brl":-25000.0,"reason":"não faz parte da carteira do perfil","trade_cost_brl":25.0,"realised_gain_brl":-167000.0,"tax_brl":0.0,"notes":["prejuízo realizado: abate o ganho das outras vendas do mesmo tipo"]},{"ticker":"Cripto","action":"vender","from_brl":21000,"to_brl":0.0,"delta_brl":-21000.0,"reason":"fora do que a política escolhe","trade_cost_brl":21.0,"realised_gain_brl":-9000.0,"tax_brl":0.0,"notes":["regime tributário próprio: o imposto desta venda não é apurado aqui"]},{"ticker":"CURY3","action":"reduzir","from_brl":44000,"to_brl":3472.0,"delta_brl":-40528.0,"reason":"acima do peso declarado","trade_cost_brl":40.53,"realised_gain_brl":19296.85,"tax_brl":0.0,"notes":[]},{"ticker":"IVVB11","action":"comprar","from_brl":0.0,"to_brl":5600.0,"delta_brl":5600.0,"reason":"fatia em bolsa dos EUA, declarada pela política","trade_cost_brl":5.6,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"CMIN3","action":"comprar","from_brl":0.0,"to_brl":3472.0,"delta_brl":3472.0,"reason":"entra pela seleção do perfil","trade_cost_brl":3.47,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"VIVA3","action":"comprar","from_brl":0.0,"to_brl":3472.0,"delta_brl":3472.0,"reason":"entra pela seleção do perfil","trade_cost_brl":3.47,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"BBSE3","action":"comprar","from_brl":0.0,"to_brl":3113.6,"delta_brl":3113.6,"reason":"entra pela seleção do perfil","trade_cost_brl":3.11,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"LEVE3","action":"comprar","from_brl":0.0,"to_brl":1794.8,"delta_brl":1794.8,"reason":"entra pela seleção do perfil","trade_cost_brl":1.79,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"PLPL3","action":"comprar","from_brl":0.0,"to_brl":1350.3,"delta_brl":1350.3,"reason":"entra pela seleção do perfil","trade_cost_brl":1.35,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"COGN3","action":"comprar","from_brl":0.0,"to_brl":1225.7,"delta_brl":1225.7,"reason":"entra pela seleção do perfil","trade_cost_brl":1.23,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"TEND3","action":"comprar","from_brl":0.0,"to_brl":1107.4,"delta_brl":1107.4,"reason":"entra pela seleção do perfil","trade_cost_brl":1.11,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"TFCO4","action":"comprar","from_brl":0.0,"to_brl":1020.6,"delta_brl":1020.6,"reason":"entra pela seleção do perfil","trade_cost_brl":1.02,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"ECOR3","action":"comprar","from_brl":0.0,"to_brl":821.1,"delta_brl":821.1,"reason":"entra pela seleção do perfil","trade_cost_brl":0.82,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"RDOR3","action":"comprar","from_brl":0.0,"to_brl":819.0,"delta_brl":819.0,"reason":"entra pela seleção do perfil","trade_cost_brl":0.82,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"B3SA3","action":"comprar","from_brl":0.0,"to_brl":731.5,"delta_brl":731.5,"reason":"entra pela seleção do perfil","trade_cost_brl":0.73,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]}],"honesty":"O custo inclui o imposto que a venda realiza, que é o número que costuma faltar. E não dizemos em quanto tempo a mudança se paga: isso exigiria prever retorno, e projeções assim erram a favor de quem as faz."},"adaptar":{"path":"adaptar","path_label":"Manter a carteira e aplicar a proteção","track_record_applies":false,"carried_loss_brl":0.0,"locked_tickers":[],"total_brl":700000,"alignment":1.0,"equity_before":0.3557,"equity_budget":0.04,"equity_after":0.04,"equity_below_budget":false,"issuer_cap":0.2371,"issuer_cap_rule":"dobro do peso médio dos emissores que o cliente já tem; limite escolhido para este caminho, não medido no histórico","unrealised_loss_kept_brl":0,"tax_left_on_table_brl":0.0,"out_of_scope_brl":21000,"turnover_brl":110500.0,"transition_cost_brl":221.0,"transition_tax_brl":0.0,"transition_total_brl":221.0,"transition_cost_pct":0.00032,"exempt_month_assumed":false,"tax_is_complete":false,"positions_without_cost_basis":[{"ticker":"WEGE3","sale_brl":159759.04,"sale_fraction":0.88755,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"unpriced_sale_brl":159759.04,"pending_resolution":{"positions":[{"ticker":"WEGE3","sale_brl":159759.04,"sale_fraction":0.88755,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"buckets":{"renda_variavel":{"other_gain_brl":-129626.71,"rate":0.15,"exempt_month":false,"carried_loss_brl":0.0}},"fixed_brl":221.0},"tax_by_bucket":{"renda_variavel":{"realised_gain_brl":-129626.71,"tax_brl":0.0}},"fgc_breaches":{"Beta":310000.0},"fgc_exposure":{"Beta":310000.0},"sources":["Open Finance (compartilhamento de investimentos)","extrato da Área do Investidor da B3","lançamento manual"],"moves":[{"ticker":"WEGE3","action":"reduzir","from_brl":180000,"to_brl":20240.96,"delta_brl":-159759.04,"reason":"orçamento de ações do perfil","trade_cost_brl":159.76,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":["imposto ainda não calculado: falta informar quanto você pagou"]},{"ticker":"CURY3","action":"reduzir","from_brl":44000,"to_brl":4947.79,"delta_brl":-39052.21,"reason":"orçamento de ações do perfil","trade_cost_brl":39.05,"realised_gain_brl":18594.18,"tax_brl":0.0,"notes":[]},{"ticker":"MGLU3","action":"reduzir","from_brl":25000,"to_brl":2811.24,"delta_brl":-22188.76,"reason":"orçamento de ações do perfil","trade_cost_brl":22.19,"realised_gain_brl":-148220.88,"tax_brl":0.0,"notes":["prejuízo realizado: abate o ganho das outras vendas do mesmo tipo"]},{"ticker":"CDB Banco Beta","action":"manter","from_brl":310000,"to_brl":310000,"delta_brl":0,"reason":"renda fixa mantida","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"Cripto","action":"manter","from_brl":21000,"to_brl":21000,"delta_brl":0,"reason":"fora do que a política escolhe","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":["a camada de proteção não observa nem cobre esta posição"]},{"ticker":"Tesouro Selic","action":"manter","from_brl":120000,"to_brl":120000,"delta_brl":0,"reason":"renda fixa mantida","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]}],"honesty":"Aqui os seus ativos ficam e ganham a proteção nas quedas. O retorno que a Benevente publica foi medido escolhendo os ativos e protegendo, junto, então ele não descreve esta carteira. Dá para dizer o que a proteção faz — reduzir a exposição quando o mercado cai —, não quanto ela renderia aqui."}},"conservador":{"adequar":{"path":"adequar","path_label":"Adequar a carteira ao perfil","track_record_applies":true,"carried_loss_brl":0.0,"locked_tickers":[],"total_brl":700000,"alignment":0.6577,"turnover_brl":227119.3,"transition_cost_brl":454.22,"transition_tax_brl":0.0,"transition_total_brl":454.22,"transition_cost_pct":0.00065,"exempt_month_assumed":false,"tax_is_complete":false,"positions_without_cost_basis":[{"ticker":"WEGE3","sale_brl":180000.0,"sale_fraction":1.0,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"unpriced_sale_brl":180000.0,"pending_resolution":{"positions":[{"ticker":"WEGE3","sale_brl":180000.0,"sale_fraction":1.0,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"buckets":{"renda_variavel":{"other_gain_brl":-160515.02,"rate":0.15,"exempt_month":false,"carried_loss_brl":0.0}},"fixed_brl":454.22},"tax_by_bucket":{"fora_do_escopo":{"realised_gain_brl":-9000.0,"tax_brl":0.0},"renda_variavel":{"realised_gain_brl":-160515.02,"tax_brl":0.0}},"fgc_breaches":{"Beta":310000.0},"fgc_exposure":{"Beta":310000.0},"sources":["Open Finance (compartilhamento de investimentos)","extrato da Área do Investidor da B3","lançamento manual"],"moves":[{"ticker":"WEGE3","action":"vender","from_brl":180000,"to_brl":0.0,"delta_brl":-180000.0,"reason":"não faz parte da carteira do perfil","trade_cost_brl":180.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":["imposto ainda não calculado: falta informar quanto você pagou"]},{"ticker":"MGLU3","action":"vender","from_brl":25000,"to_brl":0.0,"delta_brl":-25000.0,"reason":"não faz parte da carteira do perfil","trade_cost_brl":25.0,"realised_gain_brl":-167000.0,"tax_brl":0.0,"notes":["prejuízo realizado: abate o ganho das outras vendas do mesmo tipo"]},{"ticker":"Cripto","action":"vender","from_brl":21000,"to_brl":0.0,"delta_brl":-21000.0,"reason":"fora do que a política escolhe","trade_cost_brl":21.0,"realised_gain_brl":-9000.0,"tax_brl":0.0,"notes":["regime tributário próprio: o imposto desta venda não é apurado aqui"]},{"ticker":"IVVB11","action":"comprar","from_brl":0.0,"to_brl":49000.0,"delta_brl":49000.0,"reason":"fatia em bolsa dos EUA, declarada pela política","trade_cost_brl":49.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"CMIN3","action":"comprar","from_brl":0.0,"to_brl":30380.0,"delta_brl":30380.0,"reason":"entra pela seleção do perfil","trade_cost_brl":30.38,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"VIVA3","action":"comprar","from_brl":0.0,"to_brl":30380.0,"delta_brl":30380.0,"reason":"entra pela seleção do perfil","trade_cost_brl":30.38,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"BBSE3","action":"comprar","from_brl":0.0,"to_brl":27244.0,"delta_brl":27244.0,"reason":"entra pela seleção do perfil","trade_cost_brl":27.24,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"LEVE3","action":"comprar","from_brl":0.0,"to_brl":15702.4,"delta_brl":15702.4,"reason":"entra pela seleção do perfil","trade_cost_brl":15.7,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"CURY3","action":"reduzir","from_brl":44000,"to_brl":30380.0,"delta_brl":-13620.0,"reason":"acima do peso declarado","trade_cost_brl":13.62,"realised_gain_brl":6484.98,"tax_brl":0.0,"notes":[]},{"ticker":"PLPL3","action":"comprar","from_brl":0.0,"to_brl":11813.9,"delta_brl":11813.9,"reason":"entra pela seleção do perfil","trade_cost_brl":11.81,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"COGN3","action":"comprar","from_brl":0.0,"to_brl":10723.3,"delta_brl":10723.3,"reason":"entra pela seleção do perfil","trade_cost_brl":10.72,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"TEND3","action":"comprar","from_brl":0.0,"to_brl":9689.4,"delta_brl":9689.4,"reason":"entra pela seleção do perfil","trade_cost_brl":9.69,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"TFCO4","action":"comprar","from_brl":0.0,"to_brl":8932.0,"delta_brl":8932.0,"reason":"entra pela seleção do perfil","trade_cost_brl":8.93,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"ECOR3","action":"comprar","from_brl":0.0,"to_brl":7184.1,"delta_brl":7184.1,"reason":"entra pela seleção do perfil","trade_cost_brl":7.18,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"RDOR3","action":"comprar","from_brl":0.0,"to_brl":7168.0,"delta_brl":7168.0,"reason":"entra pela seleção do perfil","trade_cost_brl":7.17,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"B3SA3","action":"comprar","from_brl":0.0,"to_brl":6401.5,"delta_brl":6401.5,"reason":"entra pela seleção do perfil","trade_cost_brl":6.4,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]}],"honesty":"O custo inclui o imposto que a venda realiza, que é o número que costuma faltar. E não dizemos em quanto tempo a mudança se paga: isso exigiria prever retorno, e projeções assim erram a favor de quem as faz."},"adaptar":{"path":"adaptar","path_label":"Manter a carteira e aplicar a proteção","track_record_applies":false,"carried_loss_brl":0.0,"locked_tickers":[],"total_brl":700000,"alignment":1.0,"equity_before":0.3557,"equity_budget":0.35,"equity_after":0.3341,"equity_below_budget":false,"issuer_cap":0.2371,"issuer_cap_rule":"dobro do peso médio dos emissores que o cliente já tem; limite escolhido para este caminho, não medido no histórico","unrealised_loss_kept_brl":0,"tax_left_on_table_brl":0.0,"out_of_scope_brl":21000,"turnover_brl":7554.41,"transition_cost_brl":15.11,"transition_tax_brl":0.0,"transition_total_brl":15.11,"transition_cost_pct":2e-05,"exempt_month_assumed":true,"tax_is_complete":false,"positions_without_cost_basis":[{"ticker":"WEGE3","sale_brl":14000.0,"sale_fraction":0.077778,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"unpriced_sale_brl":14000.0,"pending_resolution":{"positions":[{"ticker":"WEGE3","sale_brl":14000.0,"sale_fraction":0.077778,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"buckets":{"renda_variavel":{"other_gain_brl":-2347.01,"rate":0.15,"exempt_month":true,"carried_loss_brl":0.0}},"fixed_brl":15.11},"tax_by_bucket":{"renda_variavel":{"realised_gain_brl":-2347.01,"tax_brl":0.0}},"fgc_breaches":{"Beta":310000.0},"fgc_exposure":{"Beta":310000.0},"sources":["Open Finance (compartilhamento de investimentos)","extrato da Área do Investidor da B3","lançamento manual"],"moves":[{"ticker":"WEGE3","action":"reduzir","from_brl":180000,"to_brl":166000.0,"delta_brl":-14000.0,"reason":"teto de concentração por emissor","trade_cost_brl":14.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":["imposto ainda não calculado: falta informar quanto você pagou"]},{"ticker":"CURY3","action":"reduzir","from_brl":44000,"to_brl":43292.93,"delta_brl":-707.07,"reason":"orçamento de ações do perfil","trade_cost_brl":0.71,"realised_gain_brl":336.66,"tax_brl":0.0,"notes":[]},{"ticker":"MGLU3","action":"reduzir","from_brl":25000,"to_brl":24598.25,"delta_brl":-401.75,"reason":"orçamento de ações do perfil","trade_cost_brl":0.4,"realised_gain_brl":-2683.67,"tax_brl":0.0,"notes":["prejuízo realizado: abate o ganho das outras vendas do mesmo tipo"]},{"ticker":"CDB Banco Beta","action":"manter","from_brl":310000,"to_brl":310000,"delta_brl":0,"reason":"renda fixa mantida","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"Cripto","action":"manter","from_brl":21000,"to_brl":21000,"delta_brl":0,"reason":"fora do que a política escolhe","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":["a camada de proteção não observa nem cobre esta posição"]},{"ticker":"Tesouro Selic","action":"manter","from_brl":120000,"to_brl":120000,"delta_brl":0,"reason":"renda fixa mantida","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]}],"honesty":"Aqui os seus ativos ficam e ganham a proteção nas quedas. O retorno que a Benevente publica foi medido escolhendo os ativos e protegendo, junto, então ele não descreve esta carteira. Dá para dizer o que a proteção faz — reduzir a exposição quando o mercado cai —, não quanto ela renderia aqui."}},"equilibrado":{"adequar":{"path":"adequar","path_label":"Adequar a carteira ao perfil","track_record_applies":true,"carried_loss_brl":0.0,"locked_tickers":[],"total_brl":700000,"alignment":0.6771,"turnover_brl":283500.0,"transition_cost_brl":567.0,"transition_tax_brl":0.0,"transition_total_brl":567.0,"transition_cost_pct":0.00081,"exempt_month_assumed":false,"tax_is_complete":false,"positions_without_cost_basis":[{"ticker":"WEGE3","sale_brl":180000.0,"sale_fraction":1.0,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"unpriced_sale_brl":180000.0,"pending_resolution":{"positions":[{"ticker":"WEGE3","sale_brl":180000.0,"sale_fraction":1.0,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"buckets":{"renda_variavel":{"other_gain_brl":-167000.0,"rate":0.15,"exempt_month":false,"carried_loss_brl":0.0}},"fixed_brl":567.0},"tax_by_bucket":{"fora_do_escopo":{"realised_gain_brl":-9000.0,"tax_brl":0.0},"renda_variavel":{"realised_gain_brl":-167000.0,"tax_brl":0.0}},"fgc_breaches":{"Beta":310000.0},"fgc_exposure":{"Beta":310000.0},"sources":["Open Finance (compartilhamento de investimentos)","extrato da Área do Investidor da B3","lançamento manual"],"moves":[{"ticker":"WEGE3","action":"vender","from_brl":180000,"to_brl":0.0,"delta_brl":-180000.0,"reason":"não faz parte da carteira do perfil","trade_cost_brl":180.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":["imposto ainda não calculado: falta informar quanto você pagou"]},{"ticker":"MGLU3","action":"vender","from_brl":25000,"to_brl":0.0,"delta_brl":-25000.0,"reason":"não faz parte da carteira do perfil","trade_cost_brl":25.0,"realised_gain_brl":-167000.0,"tax_brl":0.0,"notes":["prejuízo realizado: abate o ganho das outras vendas do mesmo tipo"]},{"ticker":"Cripto","action":"vender","from_brl":21000,"to_brl":0.0,"delta_brl":-21000.0,"reason":"fora do que a política escolhe","trade_cost_brl":21.0,"realised_gain_brl":-9000.0,"tax_brl":0.0,"notes":["regime tributário próprio: o imposto desta venda não é apurado aqui"]},{"ticker":"IVVB11","action":"comprar","from_brl":0.0,"to_brl":77000.0,"delta_brl":77000.0,"reason":"fatia em bolsa dos EUA, declarada pela política","trade_cost_brl":77.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"CMIN3","action":"comprar","from_brl":0.0,"to_brl":68530.0,"delta_brl":68530.0,"reason":"entra pela seleção do perfil","trade_cost_brl":68.53,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"VIVA3","action":"comprar","from_brl":0.0,"to_brl":68530.0,"delta_brl":68530.0,"reason":"entra pela seleção do perfil","trade_cost_brl":68.53,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"BBSE3","action":"comprar","from_brl":0.0,"to_brl":41770.4,"delta_brl":41770.4,"reason":"entra pela seleção do perfil","trade_cost_brl":41.77,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"CURY3","action":"comprar","from_brl":44000,"to_brl":68530.0,"delta_brl":24530.0,"reason":"abaixo do peso declarado","trade_cost_brl":24.53,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"LEVE3","action":"comprar","from_brl":0.0,"to_brl":21646.8,"delta_brl":21646.8,"reason":"entra pela seleção do perfil","trade_cost_brl":21.65,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"PLPL3","action":"comprar","from_brl":0.0,"to_brl":14866.6,"delta_brl":14866.6,"reason":"entra pela seleção do perfil","trade_cost_brl":14.87,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"COGN3","action":"comprar","from_brl":0.0,"to_brl":12964.0,"delta_brl":12964.0,"reason":"entra pela seleção do perfil","trade_cost_brl":12.96,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"TEND3","action":"comprar","from_brl":0.0,"to_brl":11162.2,"delta_brl":11162.2,"reason":"entra pela seleção do perfil","trade_cost_brl":11.16,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]}],"honesty":"O custo inclui o imposto que a venda realiza, que é o número que costuma faltar. E não dizemos em quanto tempo a mudança se paga: isso exigiria prever retorno, e projeções assim erram a favor de quem as faz."},"adaptar":{"path":"adaptar","path_label":"Manter a carteira e aplicar a proteção","track_record_applies":false,"carried_loss_brl":0.0,"locked_tickers":[],"total_brl":700000,"alignment":1.0,"equity_before":0.3557,"equity_budget":0.55,"equity_after":0.3357,"equity_below_budget":true,"issuer_cap":0.2371,"issuer_cap_rule":"dobro do peso médio dos emissores que o cliente já tem; limite escolhido para este caminho, não medido no histórico","unrealised_loss_kept_brl":167000,"tax_left_on_table_brl":0.0,"out_of_scope_brl":21000,"turnover_brl":7000.0,"transition_cost_brl":14.0,"transition_tax_brl":0,"transition_total_brl":14.0,"transition_cost_pct":2e-05,"exempt_month_assumed":true,"tax_is_complete":false,"positions_without_cost_basis":[{"ticker":"WEGE3","sale_brl":14000.0,"sale_fraction":0.077778,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"unpriced_sale_brl":14000.0,"pending_resolution":{"positions":[{"ticker":"WEGE3","sale_brl":14000.0,"sale_fraction":0.077778,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"buckets":{"renda_variavel":{"other_gain_brl":0.0,"rate":0.15,"exempt_month":true,"carried_loss_brl":0.0}},"fixed_brl":14.0},"tax_by_bucket":{},"fgc_breaches":{"Beta":310000.0},"fgc_exposure":{"Beta":310000.0},"sources":["Open Finance (compartilhamento de investimentos)","extrato da Área do Investidor da B3","lançamento manual"],"moves":[{"ticker":"WEGE3","action":"reduzir","from_brl":180000,"to_brl":166000.0,"delta_brl":-14000.0,"reason":"teto de concentração por emissor","trade_cost_brl":14.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":["imposto ainda não calculado: falta informar quanto você pagou"]},{"ticker":"CDB Banco Beta","action":"manter","from_brl":310000,"to_brl":310000,"delta_brl":0,"reason":"renda fixa mantida","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"CURY3","action":"manter","from_brl":44000,"to_brl":44000,"delta_brl":0,"reason":"dentro dos limites do perfil","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"Cripto","action":"manter","from_brl":21000,"to_brl":21000,"delta_brl":0,"reason":"fora do que a política escolhe","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":["a camada de proteção não observa nem cobre esta posição"]},{"ticker":"MGLU3","action":"manter","from_brl":25000,"to_brl":25000,"delta_brl":0,"reason":"dentro dos limites do perfil","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"Tesouro Selic","action":"manter","from_brl":120000,"to_brl":120000,"delta_brl":0,"reason":"renda fixa mantida","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]}],"honesty":"Aqui os seus ativos ficam e ganham a proteção nas quedas. O retorno que a Benevente publica foi medido escolhendo os ativos e protegendo, junto, então ele não descreve esta carteira. Dá para dizer o que a proteção faz — reduzir a exposição quando o mercado cai —, não quanto ela renderia aqui."}},"arrojado":{"adequar":{"path":"adequar","path_label":"Adequar a carteira ao perfil","track_record_applies":true,"carried_loss_brl":0.0,"locked_tickers":[],"total_brl":700000,"alignment":0.6771,"turnover_brl":353500.0,"transition_cost_brl":706.99,"transition_tax_brl":0.0,"transition_total_brl":706.99,"transition_cost_pct":0.00101,"exempt_month_assumed":false,"tax_is_complete":false,"positions_without_cost_basis":[{"ticker":"WEGE3","sale_brl":180000.0,"sale_fraction":1.0,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"unpriced_sale_brl":180000.0,"pending_resolution":{"positions":[{"ticker":"WEGE3","sale_brl":180000.0,"sale_fraction":1.0,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"buckets":{"renda_variavel":{"other_gain_brl":-167000.0,"rate":0.15,"exempt_month":false,"carried_loss_brl":0.0}},"fixed_brl":706.99},"tax_by_bucket":{"fora_do_escopo":{"realised_gain_brl":-9000.0,"tax_brl":0.0},"renda_variavel":{"realised_gain_brl":-167000.0,"tax_brl":0.0}},"fgc_breaches":{"Beta":310000.0},"fgc_exposure":{"Beta":310000.0},"sources":["Open Finance (compartilhamento de investimentos)","extrato da Área do Investidor da B3","lançamento manual"],"moves":[{"ticker":"WEGE3","action":"vender","from_brl":180000,"to_brl":0.0,"delta_brl":-180000.0,"reason":"não faz parte da carteira do perfil","trade_cost_brl":180.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":["imposto ainda não calculado: falta informar quanto você pagou"]},{"ticker":"MGLU3","action":"vender","from_brl":25000,"to_brl":0.0,"delta_brl":-25000.0,"reason":"não faz parte da carteira do perfil","trade_cost_brl":25.0,"realised_gain_brl":-167000.0,"tax_brl":0.0,"notes":["prejuízo realizado: abate o ganho das outras vendas do mesmo tipo"]},{"ticker":"Cripto","action":"vender","from_brl":21000,"to_brl":0.0,"delta_brl":-21000.0,"reason":"fora do que a política escolhe","trade_cost_brl":21.0,"realised_gain_brl":-9000.0,"tax_brl":0.0,"notes":["regime tributário próprio: o imposto desta venda não é apurado aqui"]},{"ticker":"VIVA3","action":"comprar","from_brl":0.0,"to_brl":142800.0,"delta_brl":142800.0,"reason":"entra pela seleção do perfil","trade_cost_brl":142.8,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"IVVB11","action":"comprar","from_brl":0.0,"to_brl":105000.0,"delta_brl":105000.0,"reason":"fatia em bolsa dos EUA, declarada pela política","trade_cost_brl":105.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"CMIN3","action":"comprar","from_brl":0.0,"to_brl":90470.8,"delta_brl":90470.8,"reason":"entra pela seleção do perfil","trade_cost_brl":90.47,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"CURY3","action":"comprar","from_brl":44000,"to_brl":121275.0,"delta_brl":77275.0,"reason":"abaixo do peso declarado","trade_cost_brl":77.27,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"BBSE3","action":"comprar","from_brl":0.0,"to_brl":48242.6,"delta_brl":48242.6,"reason":"entra pela seleção do perfil","trade_cost_brl":48.24,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"LEVE3","action":"comprar","from_brl":0.0,"to_brl":17211.6,"delta_brl":17211.6,"reason":"entra pela seleção do perfil","trade_cost_brl":17.21,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]}],"honesty":"O custo inclui o imposto que a venda realiza, que é o número que costuma faltar. E não dizemos em quanto tempo a mudança se paga: isso exigiria prever retorno, e projeções assim erram a favor de quem as faz."},"adaptar":{"path":"adaptar","path_label":"Manter a carteira e aplicar a proteção","track_record_applies":false,"carried_loss_brl":0.0,"locked_tickers":[],"total_brl":700000,"alignment":1.0,"equity_before":0.3557,"equity_budget":0.75,"equity_after":0.3357,"equity_below_budget":true,"issuer_cap":0.2371,"issuer_cap_rule":"dobro do peso médio dos emissores que o cliente já tem; limite escolhido para este caminho, não medido no histórico","unrealised_loss_kept_brl":167000,"tax_left_on_table_brl":0.0,"out_of_scope_brl":21000,"turnover_brl":7000.0,"transition_cost_brl":14.0,"transition_tax_brl":0,"transition_total_brl":14.0,"transition_cost_pct":2e-05,"exempt_month_assumed":true,"tax_is_complete":false,"positions_without_cost_basis":[{"ticker":"WEGE3","sale_brl":14000.0,"sale_fraction":0.077778,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"unpriced_sale_brl":14000.0,"pending_resolution":{"positions":[{"ticker":"WEGE3","sale_brl":14000.0,"sale_fraction":0.077778,"bucket":"renda_variavel","cost_quality":"reconstruído só em parte: há posição anterior a 01/11/2019"}],"buckets":{"renda_variavel":{"other_gain_brl":0.0,"rate":0.15,"exempt_month":true,"carried_loss_brl":0.0}},"fixed_brl":14.0},"tax_by_bucket":{},"fgc_breaches":{"Beta":310000.0},"fgc_exposure":{"Beta":310000.0},"sources":["Open Finance (compartilhamento de investimentos)","extrato da Área do Investidor da B3","lançamento manual"],"moves":[{"ticker":"WEGE3","action":"reduzir","from_brl":180000,"to_brl":166000.0,"delta_brl":-14000.0,"reason":"teto de concentração por emissor","trade_cost_brl":14.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":["imposto ainda não calculado: falta informar quanto você pagou"]},{"ticker":"CDB Banco Beta","action":"manter","from_brl":310000,"to_brl":310000,"delta_brl":0,"reason":"renda fixa mantida","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"CURY3","action":"manter","from_brl":44000,"to_brl":44000,"delta_brl":0,"reason":"dentro dos limites do perfil","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"Cripto","action":"manter","from_brl":21000,"to_brl":21000,"delta_brl":0,"reason":"fora do que a política escolhe","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":["a camada de proteção não observa nem cobre esta posição"]},{"ticker":"MGLU3","action":"manter","from_brl":25000,"to_brl":25000,"delta_brl":0,"reason":"dentro dos limites do perfil","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]},{"ticker":"Tesouro Selic","action":"manter","from_brl":120000,"to_brl":120000,"delta_brl":0,"reason":"renda fixa mantida","trade_cost_brl":0.0,"realised_gain_brl":0.0,"tax_brl":0.0,"notes":[]}],"honesty":"Aqui os seus ativos ficam e ganham a proteção nas quedas. O retorno que a Benevente publica foi medido escolhendo os ativos e protegendo, junto, então ele não descreve esta carteira. Dá para dizer o que a proteção faz — reduzir a exposição quando o mercado cai —, não quanto ela renderia aqui."}}},"b3":{"base_starts":"2019-11-01","coverage":{"entrega":["Ações, ETFs, BDRs e fundos imobiliários que você tem na B3","Tesouro Direto","Suas compras e vendas desde 01/11/2019"],"entrega_pela_metade":["CDB, LCI, LCA e afins: quantidade e vencimento, sem valor e sem preço de compra"],"nao_entrega":["Por quanto você comprou: a B3 não guarda esse dado","Qualquer coisa anterior a 01/11/2019","O que está fora da B3: previdência, cripto, conta no exterior","Imóveis e participação em empresa"],"condicoes":["A leitura depende de contrato com a B3; o ambiente de testes é livre, o de produção não","Você autoriza dentro do site da B3 e desliga lá, sem passar por nós","Os dados são do dia anterior, publicados a partir das 8h, uma vez por dia","A B3 garante 97% de disponibilidade no mês: a carteira pode não chegar num dia"]},"freshness":{"reference":"D-1, publicado a partir das 8h","sla_monthly":0.97,"why_it_matters":"Com 97% de disponibilidade ao mês, a carteira deixa de chegar por volta de uma vez por mês. Uma tela que trata 'sem movimentação' e 'não atualizou' do mesmo jeito mostra a posição de anteontem como se fosse a de ontem, sem avisar.","states":{"atual":"atualizado com o fechamento de ontem","sem_movimento":"sem movimentação: a posição de ontem continua valendo","nao_atualizou":"não atualizou hoje: o dado exibido é de antes","cedo":"ainda antes das 8h: o dado de ontem só é publicado depois"},"example":{"state":"sem_movimento","explicacao":"sem movimentação: a posição de ontem continua valendo","data_referencia":"2026-08-26","utilizavel":true}},"consent":{"escopo":["Posição","Movimentação","Negociação de Ativos","Eventos Provisionados"],"revogavel_em":"investidor.b3.com.br, em Minha Conta, Segurança, Aplicativos e Sites","credencial_armazenada":false},"cost_basis":{"CURY3":{"valor_brl":23050.0,"qualidade":"reconstruído das negociações na B3","cobertura":1.0,"observacao":"2 compra(s) desde 12/03/2021"},"MGLU3":{"valor_brl":192000.0,"qualidade":"reconstruído das negociações na B3","cobertura":1.0,"observacao":"2 compra(s) desde 01/06/2021"},"WEGE3":{"valor_brl":38000.0,"qualidade":"reconstruído só em parte: há posição anterior a 01/11/2019","cobertura":0.3333,"observacao":"2000 de 3000 unidades sem compra na base (anteriores a 01/11/2019 ou transferidas de outra corretora)"}},"gaps":{"total_posicoes":3,"com_custo_defensavel":2,"pendentes":{"WEGE3":{"qualidade":"reconstruído só em parte: há posição anterior a 01/11/2019","observacao":"2000 de 3000 unidades sem compra na base (anteriores a 01/11/2019 ou transferidas de outra corretora)","cobertura":0.3333}},"consequencia":"Enquanto houver posição sem custo defensável, o imposto do plano é parcial. O mapa mostra o que consegue apurar e nomeia o que ficou de fora, em vez de estimar a diferença — um imposto estimado tem a mesma aparência de um imposto medido e leva à mesma decisão de vender."},"posicoes":[{"nome":"CURY3","tipo":"ação","origem":"veio da B3","valor_brl":44000.0,"quantidade":4000,"vencimento":null,"emissor":null,"completa":true,"falta":""},{"nome":"MGLU3","tipo":"ação","origem":"veio da B3","valor_brl":25000.0,"quantidade":10000,"vencimento":null,"emissor":null,"completa":true,"falta":""},{"nome":"WEGE3","tipo":"ação","origem":"veio da B3","valor_brl":180000.0,"quantidade":3000,"vencimento":null,"emissor":null,"completa":true,"falta":""},{"nome":"LCA Banco Beta 2028","tipo":"LCA","origem":"veio da B3 pela metade","valor_brl":null,"quantidade":1,"vencimento":"2028-03-15","emissor":"Banco Beta","completa":false,"falta":"falta o valor: a B3 manda quantidade e vencimento, o valor fica com o emissor"},{"nome":"CDB Banco Beta 2027","tipo":"CDB","origem":"veio da B3 pela metade","valor_brl":null,"quantidade":1,"vencimento":"2027-11-20","emissor":"Banco Beta","completa":false,"falta":"falta o valor: a B3 manda quantidade e vencimento, o valor fica com o emissor"},{"nome":"LCI Banco Gama 2029","tipo":"LCI","origem":"veio da B3 pela metade","valor_brl":null,"quantidade":1,"vencimento":"2029-06-01","emissor":"Banco Gama","completa":false,"falta":"falta o valor: a B3 manda quantidade e vencimento, o valor fica com o emissor"}],"consolidado":{"total_conhecido_brl":249000.0,"posicoes":6,"sem_valor":3,"sem_valor_nomes":["LCA Banco Beta 2028","CDB Banco Beta 2027","LCI Banco Gama 2029"],"por_origem":{"veio da B3":249000.0,"veio da B3 pela metade":0,"informado por você":0},"completo":false}},"mudancas":{"ano":2026,"perfis":{"ultraconservador":{"changes":[{"date":"2026-05-14","observed_on":"2026-05-13","from_state":0,"to_state":1,"from_equity":0.032,"to_equity":0.0176,"factor":0.55,"from_factor":1.0,"from_cdi":0.96,"to_cdi":0.9744,"holdings":[{"ticker":"CURY3","before":0.005,"after":0.0027},{"ticker":"VIVA3","before":0.005,"after":0.0027},{"ticker":"CMIN3","before":0.005,"after":0.0027},{"ticker":"BBSE3","before":0.0044,"after":0.0024},{"ticker":"LEVE3","before":0.0026,"after":0.0014},{"ticker":"PLPL3","before":0.0019,"after":0.0011},{"ticker":"COGN3","before":0.0018,"after":0.001},{"ticker":"TEND3","before":0.0016,"after":0.0009},{"ticker":"TFCO4","before":0.0015,"after":0.0008},{"ticker":"ECOR3","before":0.0012,"after":0.0006},{"ticker":"RDOR3","before":0.0012,"after":0.0006},{"ticker":"B3SA3","before":0.001,"after":0.0006},{"ticker":"IVVB11","before":0.008,"after":0.008},{"ticker":"CDI","before":0.9598,"after":0.9745}],"why":"queda de 10.9%, acima do limite de alerta de 10%"}],"now":{"date":"2026-08-27","risk_state":1,"factor":0.55,"equity_br":0.0176,"equity_br_january":0.032,"global":0.008,"cdi":0.9744,"cdi_january":0.96,"holdings":[{"ticker":"CURY3","january":0.005,"now":0.0027},{"ticker":"VIVA3","january":0.005,"now":0.0027},{"ticker":"CMIN3","january":0.005,"now":0.0027},{"ticker":"BBSE3","january":0.0044,"now":0.0024},{"ticker":"LEVE3","january":0.0026,"now":0.0014},{"ticker":"PLPL3","january":0.0019,"now":0.0011},{"ticker":"COGN3","january":0.0018,"now":0.001},{"ticker":"TEND3","january":0.0016,"now":0.0009},{"ticker":"TFCO4","january":0.0015,"now":0.0008},{"ticker":"ECOR3","january":0.0012,"now":0.0006},{"ticker":"RDOR3","january":0.0012,"now":0.0006},{"ticker":"B3SA3","january":0.001,"now":0.0006},{"ticker":"IVVB11","january":0.008,"now":0.008}]}},"conservador":{"changes":[{"date":"2026-05-14","observed_on":"2026-05-13","from_state":0,"to_state":1,"from_equity":0.28,"to_equity":0.154,"factor":0.55,"from_factor":1.0,"from_cdi":0.65,"to_cdi":0.776,"holdings":[{"ticker":"CURY3","before":0.0434,"after":0.0239},{"ticker":"VIVA3","before":0.0434,"after":0.0239},{"ticker":"CMIN3","before":0.0434,"after":0.0239},{"ticker":"BBSE3","before":0.0389,"after":0.0214},{"ticker":"LEVE3","before":0.0224,"after":0.0123},{"ticker":"PLPL3","before":0.0169,"after":0.0093},{"ticker":"COGN3","before":0.0153,"after":0.0084},{"ticker":"TEND3","before":0.0138,"after":0.0076},{"ticker":"TFCO4","before":0.0128,"after":0.007},{"ticker":"ECOR3","before":0.0103,"after":0.0056},{"ticker":"RDOR3","before":0.0102,"after":0.0056},{"ticker":"B3SA3","before":0.0091,"after":0.005},{"ticker":"IVVB11","before":0.07,"after":0.07},{"ticker":"CDI","before":0.6501,"after":0.7761}],"why":"queda de 10.9%, acima do limite de alerta de 10%"}],"now":{"date":"2026-08-27","risk_state":1,"factor":0.55,"equity_br":0.154,"equity_br_january":0.28,"global":0.07,"cdi":0.776,"cdi_january":0.65,"holdings":[{"ticker":"CURY3","january":0.0434,"now":0.0239},{"ticker":"VIVA3","january":0.0434,"now":0.0239},{"ticker":"CMIN3","january":0.0434,"now":0.0239},{"ticker":"BBSE3","january":0.0389,"now":0.0214},{"ticker":"LEVE3","january":0.0224,"now":0.0123},{"ticker":"PLPL3","january":0.0169,"now":0.0093},{"ticker":"COGN3","january":0.0153,"now":0.0084},{"ticker":"TEND3","january":0.0138,"now":0.0076},{"ticker":"TFCO4","january":0.0128,"now":0.007},{"ticker":"ECOR3","january":0.0103,"now":0.0056},{"ticker":"RDOR3","january":0.0102,"now":0.0056},{"ticker":"B3SA3","january":0.0091,"now":0.005},{"ticker":"IVVB11","january":0.07,"now":0.07}]}},"equilibrado":{"changes":[{"date":"2026-05-14","observed_on":"2026-05-13","from_state":0,"to_state":1,"from_equity":0.44,"to_equity":0.308,"factor":0.7,"from_factor":1.0,"from_cdi":0.45,"to_cdi":0.582,"holdings":[{"ticker":"CURY3","before":0.0979,"after":0.0685},{"ticker":"VIVA3","before":0.0979,"after":0.0685},{"ticker":"CMIN3","before":0.0979,"after":0.0685},{"ticker":"BBSE3","before":0.0597,"after":0.0418},{"ticker":"LEVE3","before":0.0309,"after":0.0216},{"ticker":"PLPL3","before":0.0212,"after":0.0149},{"ticker":"COGN3","before":0.0185,"after":0.013},{"ticker":"TEND3","before":0.0159,"after":0.0112},{"ticker":"IVVB11","before":0.11,"after":0.11},{"ticker":"CDI","before":0.4501,"after":0.582}],"why":"queda de 10.9%, acima do limite de alerta de 10%"}],"now":{"date":"2026-08-27","risk_state":1,"factor":0.7,"equity_br":0.308,"equity_br_january":0.44,"global":0.11,"cdi":0.582,"cdi_january":0.45,"holdings":[{"ticker":"CURY3","january":0.0979,"now":0.0685},{"ticker":"VIVA3","january":0.0979,"now":0.0685},{"ticker":"CMIN3","january":0.0979,"now":0.0685},{"ticker":"BBSE3","january":0.0597,"now":0.0418},{"ticker":"LEVE3","january":0.0309,"now":0.0216},{"ticker":"PLPL3","january":0.0212,"now":0.0149},{"ticker":"COGN3","january":0.0185,"now":0.013},{"ticker":"TEND3","january":0.0159,"now":0.0112},{"ticker":"IVVB11","january":0.11,"now":0.11}]}},"arrojado":{"changes":[{"date":"2026-05-14","observed_on":"2026-05-13","from_state":0,"to_state":1,"from_equity":0.6,"to_equity":0.51,"factor":0.85,"from_factor":1.0,"from_cdi":0.25,"to_cdi":0.34,"holdings":[{"ticker":"VIVA3","before":0.204,"after":0.1734},{"ticker":"CURY3","before":0.1732,"after":0.1473},{"ticker":"CMIN3","before":0.1292,"after":0.1099},{"ticker":"BBSE3","before":0.0689,"after":0.0586},{"ticker":"LEVE3","before":0.0246,"after":0.0209},{"ticker":"IVVB11","before":0.15,"after":0.15},{"ticker":"CDI","before":0.2501,"after":0.3399}],"why":"queda de 10.9%, acima do limite de alerta de 10%"}],"now":{"date":"2026-08-27","risk_state":1,"factor":0.85,"equity_br":0.51,"equity_br_january":0.6,"global":0.15,"cdi":0.34,"cdi_january":0.25,"holdings":[{"ticker":"VIVA3","january":0.204,"now":0.1734},{"ticker":"CURY3","january":0.1732,"now":0.1473},{"ticker":"CMIN3","january":0.1292,"now":0.1099},{"ticker":"BBSE3","january":0.0689,"now":0.0586},{"ticker":"LEVE3","january":0.0246,"now":0.0209},{"ticker":"IVVB11","january":0.15,"now":0.15}]}}}},"calibracao":{"ultraconservador":{"anos":[{"year":2018,"p10":0.075384,"p50":0.110209,"p90":0.144331,"realised":0.071044,"inside":false},{"year":2019,"p10":0.070081,"p50":0.109019,"p90":0.146358,"realised":0.070148,"inside":true},{"year":2020,"p10":0.062103,"p50":0.106356,"p90":0.14559,"realised":0.023509,"inside":false},{"year":2021,"p10":0.045576,"p50":0.099671,"p90":0.144668,"realised":0.046076,"inside":true},{"year":2022,"p10":0.046371,"p50":0.098187,"p90":0.142682,"realised":0.112633,"inside":true},{"year":2023,"p10":0.0462,"p50":0.100873,"p90":0.143175,"realised":0.131811,"inside":true},{"year":2024,"p10":0.048804,"p50":0.103361,"p90":0.142723,"realised":0.101928,"inside":true},{"year":2025,"p10":0.049285,"p50":0.10574,"p90":0.142851,"realised":0.147538,"inside":false}],"cobertura":{"inside":5,"total":8,"observed":0.625,"nominal":0.8,"standard_error":0.1414},"vies_pp":-1.609,"nota":"A faixa deste perfil acertou 5 de 8, muito abaixo dos 80% nominais, e isso não é azar. Com 4% em ações o retorno é quase todo caixa, e a faixa é reamostrada dos retornos passados, que carregam a Selic de então. A incerteza que manda aqui é a Selic futura, que este método não modela. Entre 2018 e 2025 ela foi de dois dígitos a 2% e voltou, e o realizado ficou fora da faixa dos dois lados. Para este perfil, a régua não mede: use-a nos perfis com ação suficiente para a variância da ação dominar."},"conservador":{"anos":[{"year":2018,"p10":0.06265,"p50":0.152867,"p90":0.255452,"realised":0.143062,"inside":true},{"year":2019,"p10":0.066001,"p50":0.152138,"p90":0.248651,"realised":0.169041,"inside":true},{"year":2020,"p10":0.072031,"p50":0.15383,"p90":0.244886,"realised":0.027774,"inside":false},{"year":2021,"p10":0.04475,"p50":0.13594,"p90":0.229174,"realised":0.068277,"inside":true},{"year":2022,"p10":0.041685,"p50":0.127642,"p90":0.215112,"realised":0.044387,"inside":true},{"year":2023,"p10":0.033325,"p50":0.116008,"p90":0.201453,"realised":0.165387,"inside":true},{"year":2024,"p10":0.038528,"p50":0.121594,"p90":0.206287,"realised":0.084353,"inside":true},{"year":2025,"p10":0.040495,"p50":0.120936,"p90":0.203057,"realised":0.202343,"inside":true}],"cobertura":{"inside":7,"total":8,"observed":0.875,"nominal":0.8,"standard_error":0.1414},"vies_pp":-2.204,"nota":""},"equilibrado":{"anos":[{"year":2018,"p10":0.003698,"p50":0.164465,"p90":0.364619,"realised":0.24362,"inside":true},{"year":2019,"p10":0.028649,"p50":0.187347,"p90":0.376532,"realised":0.25966,"inside":true},{"year":2020,"p10":0.049623,"p50":0.200464,"p90":0.37734,"realised":0.04208,"inside":false},{"year":2021,"p10":0.011974,"p50":0.181255,"p90":0.356847,"realised":0.131106,"inside":true},{"year":2022,"p10":0.018168,"p50":0.17744,"p90":0.349612,"realised":0.009512,"inside":false},{"year":2023,"p10":-0.000334,"p50":0.153228,"p90":0.317862,"realised":0.190022,"inside":true},{"year":2024,"p10":0.005666,"p50":0.156514,"p90":0.319451,"realised":0.055045,"inside":true},{"year":2025,"p10":0.000542,"p50":0.149146,"p90":0.305242,"realised":0.284688,"inside":true}],"cobertura":{"inside":6,"total":8,"observed":0.75,"nominal":0.8,"standard_error":0.1414},"vies_pp":-1.927,"nota":""},"arrojado":{"anos":[{"year":2018,"p10":-0.069597,"p50":0.175433,"p90":0.499348,"realised":0.415146,"inside":true},{"year":2019,"p10":-0.016684,"p50":0.228105,"p90":0.555552,"realised":0.367134,"inside":true},{"year":2020,"p10":0.019701,"p50":0.259012,"p90":0.568444,"realised":0.076424,"inside":true},{"year":2021,"p10":-0.040399,"p50":0.236983,"p90":0.55089,"realised":0.212221,"inside":true},{"year":2022,"p10":-0.027455,"p50":0.242841,"p90":0.540867,"realised":-0.015076,"inside":true},{"year":2023,"p10":-0.046353,"p50":0.204627,"p90":0.490795,"realised":0.238971,"inside":true},{"year":2024,"p10":-0.040886,"p50":0.203676,"p90":0.485654,"realised":0.02357,"inside":true},{"year":2025,"p10":-0.044092,"p50":0.194827,"p90":0.463873,"realised":0.430784,"inside":true}],"cobertura":{"inside":8,"total":8,"observed":1.0,"nominal":0.8,"standard_error":0.1414},"vies_pp":0.046,"nota":""}},"renda_fixa":{"motor":{"ir":[{"ate_dias":180,"aliquota":0.225},{"ate_dias":360,"aliquota":0.2},{"ate_dias":720,"aliquota":0.175},{"ate_dias":1000000000,"aliquota":0.15}],"iof":[0.9667,0.9333,0.9,0.8667,0.8333,0.8,0.7667,0.7333,0.7,0.6667,0.6333,0.6,0.5667,0.5333,0.5,0.4667,0.4333,0.4,0.3667,0.3333,0.3,0.2667,0.2333,0.2,0.1667,0.1333,0.1,0.0667,0.0333],"fgc":{"por_conglomerado_brl":250000.0,"teto_movel_brl":1000000.0,"janela_anos":4},"produtos":{"CDB":{"regime":"captação bancária (CMN/BCB)","fgc":true,"ir":true},"RDB":{"regime":"captação bancária (CMN/BCB)","fgc":true,"ir":true},"LC":{"regime":"captação bancária (CMN/BCB)","fgc":true,"ir":true},"LCI":{"regime":"captação bancária (CMN/BCB)","fgc":true,"ir":false},"LCA":{"regime":"captação bancária (CMN/BCB)","fgc":true,"ir":false},"CRI":{"regime":"valor mobiliário (CVM)","fgc":false,"ir":false},"CRA":{"regime":"valor mobiliário (CVM)","fgc":false,"ir":false},"DEBENTURE":{"regime":"valor mobiliário (CVM)","fgc":false,"ir":true},"DEBENTURE_INCENTIVADA":{"regime":"valor mobiliário (CVM)","fgc":false,"ir":false},"TESOURO":{"regime":"título público federal","fgc":false,"ir":true}},"indices":["CDI","CDI+","prefixado","IPCA+","Selic"],"dias_no_ano":365.25},"cdi_anual":0.0937,"ipca_anual":0.045,"referencia":"2026-08-27","piso":{"name":"Tesouro Selic 2028","kind":"TESOURO","issuer":"Tesouro Nacional","conglomerate":"Tesouro Nacional","index":"Selic","rate":1.001067,"maturity":"2028-03-01","minimum_brl":197.6,"daily_liquidity":true,"custody_fee_annual":0.002}},"acompanhamento":{"ano":2026,"limitacao":"A faixa é uma só, calculada em janeiro, e não se ajusta ao que foi acontecendo. Um ano dentro da faixa não confirma a regra: a cobertura só significa alguma coisa somando muitos anos.","limitacao_tardia":"Esta faixa não foi declarada antes do ano: ela foi desenhada em 30/08/2026, depois que o degrau passou a existir. Nenhum dado de 2026 entrou nela, mas ela não tem a propriedade que as de janeiro têm, e por isso não entra em contagem de cobertura.","perfis":{"ultraconservador":{"faixa":[{"sessions":5,"p10":-0.000214,"p50":0.001974,"p90":0.003979},{"sessions":10,"p10":0.000755,"p50":0.003948,"p90":0.00696},{"sessions":15,"p10":0.001695,"p50":0.005957,"p90":0.00989},{"sessions":20,"p10":0.002658,"p50":0.007978,"p90":0.01277},{"sessions":25,"p10":0.003552,"p50":0.009956,"p90":0.015719},{"sessions":30,"p10":0.004507,"p50":0.01203,"p90":0.018434},{"sessions":35,"p10":0.005518,"p50":0.014066,"p90":0.02124},{"sessions":40,"p10":0.0065,"p50":0.016125,"p90":0.024101},{"sessions":45,"p10":0.007464,"p50":0.018134,"p90":0.026841},{"sessions":50,"p10":0.008308,"p50":0.020209,"p90":0.029606},{"sessions":55,"p10":0.009351,"p50":0.022284,"p90":0.032368},{"sessions":60,"p10":0.010232,"p50":0.024367,"p90":0.035224},{"sessions":65,"p10":0.011314,"p50":0.02639,"p90":0.03803},{"sessions":70,"p10":0.012382,"p50":0.028506,"p90":0.040742},{"sessions":75,"p10":0.013391,"p50":0.03062,"p90":0.043534},{"sessions":80,"p10":0.014381,"p50":0.032692,"p90":0.046352},{"sessions":85,"p10":0.01539,"p50":0.034783,"p90":0.049098},{"sessions":90,"p10":0.016487,"p50":0.036889,"p90":0.051971},{"sessions":95,"p10":0.017567,"p50":0.039094,"p90":0.054709},{"sessions":100,"p10":0.018505,"p50":0.041211,"p90":0.057568},{"sessions":105,"p10":0.01966,"p50":0.043262,"p90":0.060387},{"sessions":110,"p10":0.020775,"p50":0.045456,"p90":0.063327},{"sessions":115,"p10":0.021818,"p50":0.047569,"p90":0.066022},{"sessions":120,"p10":0.02281,"p50":0.049661,"p90":0.068972},{"sessions":125,"p10":0.023926,"p50":0.051857,"p90":0.071667},{"sessions":130,"p10":0.025026,"p50":0.053973,"p90":0.074523},{"sessions":135,"p10":0.026142,"p50":0.056177,"p90":0.077421},{"sessions":140,"p10":0.027315,"p50":0.058366,"p90":0.080295},{"sessions":145,"p10":0.028468,"p50":0.060498,"p90":0.083142},{"sessions":150,"p10":0.029471,"p50":0.062653,"p90":0.085776},{"sessions":155,"p10":0.030624,"p50":0.064834,"p90":0.088839},{"sessions":160,"p10":0.03166,"p50":0.067085,"p90":0.091632},{"sessions":165,"p10":0.032794,"p50":0.069264,"p90":0.094677},{"sessions":170,"p10":0.033738,"p50":0.071299,"p90":0.097491},{"sessions":175,"p10":0.034776,"p50":0.073518,"p90":0.100514},{"sessions":180,"p10":0.03587,"p50":0.075765,"p90":0.103478},{"sessions":185,"p10":0.037075,"p50":0.077807,"p90":0.106396},{"sessions":190,"p10":0.038104,"p50":0.080087,"p90":0.109207},{"sessions":195,"p10":0.039137,"p50":0.082371,"p90":0.112204},{"sessions":200,"p10":0.040427,"p50":0.084595,"p90":0.115063},{"sessions":205,"p10":0.041458,"p50":0.08676,"p90":0.117958},{"sessions":210,"p10":0.042369,"p50":0.088991,"p90":0.121153},{"sessions":215,"p10":0.043478,"p50":0.091226,"p90":0.124123},{"sessions":220,"p10":0.044408,"p50":0.09346,"p90":0.127063},{"sessions":225,"p10":0.045416,"p50":0.095759,"p90":0.130027},{"sessions":230,"p10":0.046436,"p50":0.098101,"p90":0.132954},{"sessions":235,"p10":0.047569,"p50":0.100283,"p90":0.136077},{"sessions":240,"p10":0.048721,"p50":0.102543,"p90":0.139112},{"sessions":245,"p10":0.050022,"p50":0.104895,"p90":0.142053},{"sessions":250,"p10":0.050925,"p50":0.107241,"p90":0.145031}],"faixa_de_janeiro":false,"faixa_desenhada":"2026-08-30","realizado":[{"sessions":1,"date":"2026-01-02","r":0.0},{"sessions":6,"date":"2026-01-09","r":0.0038},{"sessions":11,"date":"2026-01-16","r":0.005211},{"sessions":16,"date":"2026-01-23","r":0.01002},{"sessions":21,"date":"2026-01-30","r":0.012985},{"sessions":26,"date":"2026-02-06","r":0.016108},{"sessions":31,"date":"2026-02-13","r":0.018933},{"sessions":36,"date":"2026-02-24","r":0.022214},{"sessions":41,"date":"2026-03-03","r":0.022974},{"sessions":46,"date":"2026-03-10","r":0.025066},{"sessions":51,"date":"2026-03-17","r":0.026716},{"sessions":56,"date":"2026-03-24","r":0.029401},{"sessions":61,"date":"2026-03-31","r":0.031967},{"sessions":66,"date":"2026-04-08","r":0.035817},{"sessions":71,"date":"2026-04-15","r":0.038625},{"sessions":76,"date":"2026-04-23","r":0.040163},{"sessions":81,"date":"2026-04-30","r":0.041201},{"sessions":86,"date":"2026-05-08","r":0.044536},{"sessions":91,"date":"2026-05-15","r":0.046201},{"sessions":96,"date":"2026-05-22","r":0.048492},{"sessions":101,"date":"2026-05-29","r":0.051974},{"sessions":106,"date":"2026-06-08","r":0.053136},{"sessions":111,"date":"2026-06-15","r":0.057483},{"sessions":116,"date":"2026-06-22","r":0.060102},{"sessions":121,"date":"2026-06-29","r":0.063655},{"sessions":126,"date":"2026-07-06","r":0.065975},{"sessions":131,"date":"2026-07-13","r":0.069902},{"sessions":136,"date":"2026-07-20","r":0.071196},{"sessions":141,"date":"2026-07-27","r":0.074291},{"sessions":146,"date":"2026-08-03","r":0.077749},{"sessions":151,"date":"2026-08-10","r":0.079771},{"sessions":156,"date":"2026-08-17","r":0.08281},{"sessions":161,"date":"2026-08-24","r":0.085394},{"sessions":164,"date":"2026-08-27","r":0.088291}],"agora":{"sessions":164,"date":"2026-08-27","realised":0.088291,"p10":0.032567,"p50":0.068828,"p90":0.094068,"inside":true}},"conservador":{"faixa":[{"sessions":5,"p10":-0.006736,"p50":0.002647,"p90":0.011874},{"sessions":10,"p10":-0.007916,"p50":0.005043,"p90":0.017742},{"sessions":15,"p10":-0.008437,"p50":0.007233,"p90":0.023305},{"sessions":20,"p10":-0.008687,"p50":0.009353,"p90":0.029314},{"sessions":25,"p10":-0.009371,"p50":0.011819,"p90":0.033958},{"sessions":30,"p10":-0.008793,"p50":0.014468,"p90":0.038459},{"sessions":35,"p10":-0.008432,"p50":0.017007,"p90":0.043266},{"sessions":40,"p10":-0.007814,"p50":0.019535,"p90":0.04817},{"sessions":45,"p10":-0.007677,"p50":0.022081,"p90":0.05233},{"sessions":50,"p10":-0.006887,"p50":0.024824,"p90":0.056625},{"sessions":55,"p10":-0.006527,"p50":0.027181,"p90":0.061067},{"sessions":60,"p10":-0.005583,"p50":0.029291,"p90":0.065307},{"sessions":65,"p10":-0.004693,"p50":0.031923,"p90":0.069352},{"sessions":70,"p10":-0.003959,"p50":0.034404,"p90":0.073036},{"sessions":75,"p10":-0.003031,"p50":0.036805,"p90":0.077212},{"sessions":80,"p10":-0.001645,"p50":0.039419,"p90":0.081175},{"sessions":85,"p10":-0.000697,"p50":0.041891,"p90":0.085053},{"sessions":90,"p10":0.00068,"p50":0.044548,"p90":0.088605},{"sessions":95,"p10":0.001505,"p50":0.046868,"p90":0.092438},{"sessions":100,"p10":0.002696,"p50":0.049214,"p90":0.096297},{"sessions":105,"p10":0.004058,"p50":0.051748,"p90":0.100115},{"sessions":110,"p10":0.00525,"p50":0.054577,"p90":0.104005},{"sessions":115,"p10":0.006751,"p50":0.057151,"p90":0.107776},{"sessions":120,"p10":0.007985,"p50":0.059429,"p90":0.111607},{"sessions":125,"p10":0.009151,"p50":0.061847,"p90":0.115396},{"sessions":130,"p10":0.010139,"p50":0.064659,"p90":0.11918},{"sessions":135,"p10":0.012337,"p50":0.067432,"p90":0.122878},{"sessions":140,"p10":0.013283,"p50":0.070006,"p90":0.126833},{"sessions":145,"p10":0.0149,"p50":0.07252,"p90":0.130596},{"sessions":150,"p10":0.016421,"p50":0.07544,"p90":0.133991},{"sessions":155,"p10":0.018211,"p50":0.077753,"p90":0.138007},{"sessions":160,"p10":0.019283,"p50":0.080251,"p90":0.14161},{"sessions":165,"p10":0.020377,"p50":0.082821,"p90":0.145465},{"sessions":170,"p10":0.022336,"p50":0.0852,"p90":0.149578},{"sessions":175,"p10":0.023903,"p50":0.087865,"p90":0.153203},{"sessions":180,"p10":0.025226,"p50":0.09053,"p90":0.157511},{"sessions":185,"p10":0.026962,"p50":0.093577,"p90":0.161494},{"sessions":190,"p10":0.028767,"p50":0.095922,"p90":0.165302},{"sessions":195,"p10":0.030273,"p50":0.098252,"p90":0.169451},{"sessions":200,"p10":0.031481,"p50":0.100516,"p90":0.172893},{"sessions":205,"p10":0.032904,"p50":0.103263,"p90":0.176199},{"sessions":210,"p10":0.035036,"p50":0.105913,"p90":0.179784},{"sessions":215,"p10":0.037042,"p50":0.109089,"p90":0.183132},{"sessions":220,"p10":0.038557,"p50":0.111482,"p90":0.187081},{"sessions":225,"p10":0.03995,"p50":0.114061,"p90":0.190456},{"sessions":230,"p10":0.042109,"p50":0.11669,"p90":0.193769},{"sessions":235,"p10":0.043557,"p50":0.11931,"p90":0.197693},{"sessions":240,"p10":0.045075,"p50":0.122078,"p90":0.20186},{"sessions":245,"p10":0.046708,"p50":0.124728,"p90":0.204381},{"sessions":250,"p10":0.048788,"p50":0.127193,"p90":0.208627}],"faixa_de_janeiro":true,"faixa_desenhada":"2026-01-02","realizado":[{"sessions":1,"date":"2026-01-02","r":0.0},{"sessions":6,"date":"2026-01-09","r":0.011864},{"sessions":11,"date":"2026-01-16","r":0.00276},{"sessions":16,"date":"2026-01-23","r":0.02334},{"sessions":21,"date":"2026-01-30","r":0.027718},{"sessions":26,"date":"2026-02-06","r":0.033415},{"sessions":31,"date":"2026-02-13","r":0.036451},{"sessions":36,"date":"2026-02-24","r":0.043419},{"sessions":41,"date":"2026-03-03","r":0.028264},{"sessions":46,"date":"2026-03-10","r":0.02471},{"sessions":51,"date":"2026-03-17","r":0.017224},{"sessions":56,"date":"2026-03-24","r":0.019009},{"sessions":61,"date":"2026-03-31","r":0.01976},{"sessions":66,"date":"2026-04-08","r":0.031691},{"sessions":71,"date":"2026-04-15","r":0.034445},{"sessions":76,"date":"2026-04-23","r":0.026031},{"sessions":81,"date":"2026-04-30","r":0.013244},{"sessions":86,"date":"2026-05-08","r":0.020782},{"sessions":91,"date":"2026-05-15","r":0.01365},{"sessions":96,"date":"2026-05-22","r":0.011943},{"sessions":101,"date":"2026-05-29","r":0.020588},{"sessions":106,"date":"2026-06-08","r":0.008882},{"sessions":111,"date":"2026-06-15","r":0.024985},{"sessions":116,"date":"2026-06-22","r":0.026122},{"sessions":121,"date":"2026-06-29","r":0.035521},{"sessions":126,"date":"2026-07-06","r":0.034077},{"sessions":131,"date":"2026-07-13","r":0.046635},{"sessions":136,"date":"2026-07-20","r":0.036095},{"sessions":141,"date":"2026-07-27","r":0.041255},{"sessions":146,"date":"2026-08-03","r":0.049527},{"sessions":151,"date":"2026-08-10","r":0.045404},{"sessions":156,"date":"2026-08-17","r":0.050272},{"sessions":161,"date":"2026-08-24","r":0.051102},{"sessions":164,"date":"2026-08-27","r":0.063356}],"agora":{"sessions":164,"date":"2026-08-27","realised":0.063356,"p10":0.020158,"p50":0.082307,"p90":0.144694,"inside":true}},"equilibrado":{"faixa":[{"sessions":5,"p10":-0.013272,"p50":0.003333,"p90":0.019785},{"sessions":10,"p10":-0.016815,"p50":0.00646,"p90":0.029177},{"sessions":15,"p10":-0.019813,"p50":0.009715,"p90":0.037699},{"sessions":20,"p10":-0.021982,"p50":0.012361,"p90":0.047375},{"sessions":25,"p10":-0.023068,"p50":0.015465,"p90":0.055032},{"sessions":30,"p10":-0.023441,"p50":0.018254,"p90":0.062266},{"sessions":35,"p10":-0.023669,"p50":0.021627,"p90":0.06972},{"sessions":40,"p10":-0.024297,"p50":0.024712,"p90":0.076216},{"sessions":45,"p10":-0.025283,"p50":0.028146,"p90":0.082668},{"sessions":50,"p10":-0.024949,"p50":0.031188,"p90":0.08885},{"sessions":55,"p10":-0.02471,"p50":0.03407,"p90":0.095492},{"sessions":60,"p10":-0.024923,"p50":0.036875,"p90":0.101993},{"sessions":65,"p10":-0.024326,"p50":0.040275,"p90":0.107572},{"sessions":70,"p10":-0.023282,"p50":0.043169,"p90":0.113481},{"sessions":75,"p10":-0.02316,"p50":0.046538,"p90":0.120613},{"sessions":80,"p10":-0.02235,"p50":0.049366,"p90":0.126369},{"sessions":85,"p10":-0.021492,"p50":0.052618,"p90":0.132371},{"sessions":90,"p10":-0.020743,"p50":0.055648,"p90":0.138593},{"sessions":95,"p10":-0.020444,"p50":0.059043,"p90":0.144142},{"sessions":100,"p10":-0.020276,"p50":0.061737,"p90":0.149838},{"sessions":105,"p10":-0.019325,"p50":0.065035,"p90":0.154963},{"sessions":110,"p10":-0.018565,"p50":0.068716,"p90":0.161104},{"sessions":115,"p10":-0.016943,"p50":0.071679,"p90":0.167549},{"sessions":120,"p10":-0.015878,"p50":0.074575,"p90":0.173222},{"sessions":125,"p10":-0.015406,"p50":0.078167,"p90":0.178462},{"sessions":130,"p10":-0.013764,"p50":0.080878,"p90":0.184398},{"sessions":135,"p10":-0.013724,"p50":0.084244,"p90":0.190582},{"sessions":140,"p10":-0.012876,"p50":0.087605,"p90":0.196948},{"sessions":145,"p10":-0.01236,"p50":0.090882,"p90":0.202391},{"sessions":150,"p10":-0.010503,"p50":0.09377,"p90":0.207276},{"sessions":155,"p10":-0.009222,"p50":0.096783,"p90":0.211987},{"sessions":160,"p10":-0.008739,"p50":0.100078,"p90":0.217802},{"sessions":165,"p10":-0.008099,"p50":0.104011,"p90":0.223647},{"sessions":170,"p10":-0.006568,"p50":0.107558,"p90":0.22841},{"sessions":175,"p10":-0.005842,"p50":0.110522,"p90":0.233538},{"sessions":180,"p10":-0.004218,"p50":0.113903,"p90":0.23983},{"sessions":185,"p10":-0.002654,"p50":0.116974,"p90":0.246435},{"sessions":190,"p10":-0.000441,"p50":0.120408,"p90":0.251852},{"sessions":195,"p10":0.00046,"p50":0.123007,"p90":0.258256},{"sessions":200,"p10":0.002333,"p50":0.126238,"p90":0.263141},{"sessions":205,"p10":0.002238,"p50":0.129906,"p90":0.26888},{"sessions":210,"p10":0.004631,"p50":0.132903,"p90":0.273445},{"sessions":215,"p10":0.005865,"p50":0.136002,"p90":0.278619},{"sessions":220,"p10":0.007294,"p50":0.139191,"p90":0.284352},{"sessions":225,"p10":0.008664,"p50":0.143354,"p90":0.289853},{"sessions":230,"p10":0.009334,"p50":0.146504,"p90":0.295102},{"sessions":235,"p10":0.011915,"p50":0.150233,"p90":0.300032},{"sessions":240,"p10":0.01378,"p50":0.153876,"p90":0.306784},{"sessions":245,"p10":0.015509,"p50":0.157273,"p90":0.312272},{"sessions":250,"p10":0.018358,"p50":0.160576,"p90":0.317498}],"faixa_de_janeiro":true,"faixa_desenhada":"2026-01-02","realizado":[{"sessions":1,"date":"2026-01-02","r":0.0},{"sessions":6,"date":"2026-01-09","r":0.015284},{"sessions":11,"date":"2026-01-16","r":-0.00348},{"sessions":16,"date":"2026-01-23","r":0.025432},{"sessions":21,"date":"2026-01-30","r":0.030379},{"sessions":26,"date":"2026-02-06","r":0.043385},{"sessions":31,"date":"2026-02-13","r":0.045846},{"sessions":36,"date":"2026-02-24","r":0.053174},{"sessions":41,"date":"2026-03-03","r":0.029893},{"sessions":46,"date":"2026-03-10","r":0.019075},{"sessions":51,"date":"2026-03-17","r":0.004129},{"sessions":56,"date":"2026-03-24","r":0.007401},{"sessions":61,"date":"2026-03-31","r":0.004032},{"sessions":66,"date":"2026-04-08","r":0.020993},{"sessions":71,"date":"2026-04-15","r":0.020288},{"sessions":76,"date":"2026-04-23","r":0.007414},{"sessions":81,"date":"2026-04-30","r":-0.014753},{"sessions":86,"date":"2026-05-08","r":-0.004969},{"sessions":91,"date":"2026-05-15","r":-0.014719},{"sessions":96,"date":"2026-05-22","r":-0.019038},{"sessions":101,"date":"2026-05-29","r":-0.005839},{"sessions":106,"date":"2026-06-08","r":-0.027957},{"sessions":111,"date":"2026-06-15","r":-0.001522},{"sessions":116,"date":"2026-06-22","r":0.000364},{"sessions":121,"date":"2026-06-29","r":0.013008},{"sessions":126,"date":"2026-07-06","r":0.008773},{"sessions":131,"date":"2026-07-13","r":0.032714},{"sessions":136,"date":"2026-07-20","r":0.014191},{"sessions":141,"date":"2026-07-27","r":0.023049},{"sessions":146,"date":"2026-08-03","r":0.034359},{"sessions":151,"date":"2026-08-10","r":0.027164},{"sessions":156,"date":"2026-08-17","r":0.037683},{"sessions":161,"date":"2026-08-24","r":0.035805},{"sessions":164,"date":"2026-08-27","r":0.055545}],"agora":{"sessions":164,"date":"2026-08-27","realised":0.055545,"p10":-0.008227,"p50":0.103224,"p90":0.222478,"inside":true}},"arrojado":{"faixa":[{"sessions":5,"p10":-0.022034,"p50":0.0044,"p90":0.031211},{"sessions":10,"p10":-0.027977,"p50":0.008147,"p90":0.046178},{"sessions":15,"p10":-0.034073,"p50":0.011062,"p90":0.060386},{"sessions":20,"p10":-0.037343,"p50":0.016829,"p90":0.07205},{"sessions":25,"p10":-0.041633,"p50":0.019583,"p90":0.084395},{"sessions":30,"p10":-0.043713,"p50":0.023416,"p90":0.095985},{"sessions":35,"p10":-0.045115,"p50":0.027029,"p90":0.105882},{"sessions":40,"p10":-0.047285,"p50":0.03128,"p90":0.116283},{"sessions":45,"p10":-0.04909,"p50":0.035565,"p90":0.126379},{"sessions":50,"p10":-0.049789,"p50":0.039293,"p90":0.134521},{"sessions":55,"p10":-0.050411,"p50":0.043649,"p90":0.145331},{"sessions":60,"p10":-0.051504,"p50":0.047127,"p90":0.153751},{"sessions":65,"p10":-0.051897,"p50":0.051365,"p90":0.163887},{"sessions":70,"p10":-0.052153,"p50":0.054972,"p90":0.173377},{"sessions":75,"p10":-0.052376,"p50":0.059429,"p90":0.183189},{"sessions":80,"p10":-0.053582,"p50":0.063097,"p90":0.192698},{"sessions":85,"p10":-0.054187,"p50":0.066217,"p90":0.200798},{"sessions":90,"p10":-0.054634,"p50":0.07097,"p90":0.209034},{"sessions":95,"p10":-0.053319,"p50":0.075845,"p90":0.217521},{"sessions":100,"p10":-0.054306,"p50":0.079107,"p90":0.227254},{"sessions":105,"p10":-0.053273,"p50":0.083343,"p90":0.237136},{"sessions":110,"p10":-0.053565,"p50":0.08778,"p90":0.244439},{"sessions":115,"p10":-0.052901,"p50":0.091801,"p90":0.252113},{"sessions":120,"p10":-0.05253,"p50":0.095893,"p90":0.261538},{"sessions":125,"p10":-0.051477,"p50":0.100291,"p90":0.270533},{"sessions":130,"p10":-0.0508,"p50":0.104791,"p90":0.278524},{"sessions":135,"p10":-0.049366,"p50":0.109221,"p90":0.287827},{"sessions":140,"p10":-0.051064,"p50":0.113616,"p90":0.29672},{"sessions":145,"p10":-0.049253,"p50":0.118228,"p90":0.302357},{"sessions":150,"p10":-0.048436,"p50":0.122345,"p90":0.311265},{"sessions":155,"p10":-0.047579,"p50":0.126622,"p90":0.319845},{"sessions":160,"p10":-0.047831,"p50":0.131068,"p90":0.329435},{"sessions":165,"p10":-0.046555,"p50":0.13489,"p90":0.336597},{"sessions":170,"p10":-0.045956,"p50":0.139468,"p90":0.344774},{"sessions":175,"p10":-0.04503,"p50":0.143922,"p90":0.353822},{"sessions":180,"p10":-0.043927,"p50":0.14838,"p90":0.361913},{"sessions":185,"p10":-0.043713,"p50":0.153152,"p90":0.370371},{"sessions":190,"p10":-0.0425,"p50":0.155893,"p90":0.379927},{"sessions":195,"p10":-0.041398,"p50":0.160486,"p90":0.389135},{"sessions":200,"p10":-0.040393,"p50":0.16401,"p90":0.398373},{"sessions":205,"p10":-0.038962,"p50":0.16807,"p90":0.4063},{"sessions":210,"p10":-0.037059,"p50":0.172979,"p90":0.413881},{"sessions":215,"p10":-0.03595,"p50":0.178023,"p90":0.421684},{"sessions":220,"p10":-0.034671,"p50":0.182299,"p90":0.430272},{"sessions":225,"p10":-0.033825,"p50":0.188052,"p90":0.438172},{"sessions":230,"p10":-0.03143,"p50":0.19218,"p90":0.446756},{"sessions":235,"p10":-0.029832,"p50":0.19644,"p90":0.455621},{"sessions":240,"p10":-0.028191,"p50":0.201248,"p90":0.46449},{"sessions":245,"p10":-0.027278,"p50":0.206465,"p90":0.473561},{"sessions":250,"p10":-0.026444,"p50":0.210756,"p90":0.481184}],"faixa_de_janeiro":true,"faixa_desenhada":"2026-01-02","realizado":[{"sessions":1,"date":"2026-01-02","r":0.0},{"sessions":6,"date":"2026-01-09","r":0.010179},{"sessions":11,"date":"2026-01-16","r":-0.024192},{"sessions":16,"date":"2026-01-23","r":0.009466},{"sessions":21,"date":"2026-01-30","r":0.010652},{"sessions":26,"date":"2026-02-06","r":0.040224},{"sessions":31,"date":"2026-02-13","r":0.044277},{"sessions":36,"date":"2026-02-24","r":0.055021},{"sessions":41,"date":"2026-03-03","r":0.026494},{"sessions":46,"date":"2026-03-10","r":0.00477},{"sessions":51,"date":"2026-03-17","r":-0.022346},{"sessions":56,"date":"2026-03-24","r":-0.017114},{"sessions":61,"date":"2026-03-31","r":-0.024586},{"sessions":66,"date":"2026-04-08","r":-0.001947},{"sessions":71,"date":"2026-04-15","r":-0.005943},{"sessions":76,"date":"2026-04-23","r":-0.022916},{"sessions":81,"date":"2026-04-30","r":-0.048636},{"sessions":86,"date":"2026-05-08","r":-0.040695},{"sessions":91,"date":"2026-05-15","r":-0.055399},{"sessions":96,"date":"2026-05-22","r":-0.061376},{"sessions":101,"date":"2026-05-29","r":-0.045907},{"sessions":106,"date":"2026-06-08","r":-0.077611},{"sessions":111,"date":"2026-06-15","r":-0.040359},{"sessions":116,"date":"2026-06-22","r":-0.039625},{"sessions":121,"date":"2026-06-29","r":-0.019252},{"sessions":126,"date":"2026-07-06","r":-0.0271},{"sessions":131,"date":"2026-07-13","r":0.004745},{"sessions":136,"date":"2026-07-20","r":-0.021725},{"sessions":141,"date":"2026-07-27","r":-0.010297},{"sessions":146,"date":"2026-08-03","r":0.005597},{"sessions":151,"date":"2026-08-10","r":-0.005484},{"sessions":156,"date":"2026-08-17","r":0.005548},{"sessions":161,"date":"2026-08-24","r":0.003434},{"sessions":164,"date":"2026-08-27","r":0.030735}],"agora":{"sessions":164,"date":"2026-08-27","realised":0.030735,"p10":-0.04681,"p50":0.134126,"p90":0.335165,"inside":true}}}}};
const BRL = v => "R$ " + Math.round(v).toLocaleString("pt-BR");
const PCT = (v, c = 1) => (v * 100).toFixed(c).replace(".", ",") + "%";
// A ordem da escada vem do payload, do mais apertado ao mais solto. Escrita
// à mão ela ficou com três degraus: quando a escada ganhou o quarto, a
// resposta que apertava para ele dava RANK indefinido, a comparação virava
// falsa e o perfil caía silenciosamente no degrau de cima.
const RANK = Object.fromEntries(Object.keys(DADOS.profiles).map((n, i) => [n, i]));
const respostas = {};

const $ = id => document.getElementById(id);
// Nome de posicao e texto que a propria pessoa digitou, e ele chega a innerHTML
// em mais de um lugar. A exposicao aqui e ao proprio navegador de quem digitou,
// porque nada disto e guardado nem compartilhado, mas texto de usuario dentro de
// marcacao e um habito que envelhece mal quando o proximo campo vier de fora.
const escapa = v => String(v).replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
};
const mostra = (...ids) => ids.forEach(i => $(i).classList.remove("hidden"));
const esconde = (...ids) => ids.forEach(i => $(i).classList.add("hidden"));
const etapa = n => [...$("etapas").children].forEach((li, i) =>
  i <= n ? li.setAttribute("data-on", "1") : li.removeAttribute("data-on"));

/* --- tema --- */
// O claro é o padrão, e é o que o :root descreve. O guia é escuro por
// definição, mas o padrão foi pedido claro, e a inversão também conserta um
// defeito: enquanto o escuro era o :root, qualquer regra que tivesse escapado
// com cor literal ficava com a cor do escuro dentro do tema claro, que é a
// borda preta em volta de cartão branco e o texto que some no fundo.
const temaBtn = $("tema");
const guardado = (() => { try { return localStorage.getItem("tema"); } catch (e) { return null; } })();
function aplicaTema(valor) {
  const escuro = valor === "dark";
  if (escuro) document.documentElement.setAttribute("data-theme", "dark");
  else document.documentElement.removeAttribute("data-theme");
  $("tema-icone").textContent = escuro ? "☾" : "☀";
  $("tema-txt").textContent = escuro ? "Escuro" : "Claro";
  temaBtn.setAttribute("aria-pressed", String(escuro));
}
aplicaTema(guardado === "dark" ? "dark" : "light");
temaBtn.onclick = () => {
  const novo = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  aplicaTema(novo);
  try { localStorage.setItem("tema", novo); } catch (e) { /* janela anônima: segue sem salvar */ }
};

/* --- rolagem --- */
// Rolar a cada clique era o defeito: quando o destino já está à vista, mover a
// página desorienta, e no celular a barra do navegador aparece e some a cada
// movimento. Só rola quando o alvo está mesmo fora de vista, e nunca com
// animação para quem pediu movimento reduzido no sistema.
const menosMovimento = matchMedia("(prefers-reduced-motion: reduce)");
function rolaPara(alvo, bloco) {
  if (!alvo) return;
  const r = alvo.getBoundingClientRect();
  const altura = window.innerHeight || document.documentElement.clientHeight;
  if (r.top >= 0 && r.top <= altura * 0.6) return;
  alvo.scrollIntoView({ behavior: menosMovimento.matches ? "auto" : "smooth",
                        block: bloco || "nearest" });
}

/* --- conexão com a B3 --- */
const b3 = DADOS.b3;
const pendentes = Object.entries(b3.gaps.pendentes);
const nomesPendentes = pendentes.map(([t]) => t).join(", ");

$("conectar").onclick = () => {
  mostra("chegou");
  $("conectar").textContent = "Conta conectada";
  $("conectar").disabled = true;

  const total = Object.keys(b3.cost_basis).length;
  $("chegou-tit").textContent = b3.gaps.com_custo_defensavel + " de " + total +
    " posições completas";
  $("chegou-txt").textContent =
    "A B3 manda o que você tem, mas não manda por quanto você comprou, esse dado não " +
    "existe nas APIs dela. Ele é remontado a partir das suas negociações, e o histórico " +
    "começa em " + b3.base_starts.split("-").reverse().join("/") + ".";

  const lista = (id, itens) => {
    const ul = $(id); ul.innerHTML = "";
    itens.forEach(t => ul.append(el("li", null, t)));
  };
  lista("vem", b3.coverage.entrega);
  lista("nvem", b3.coverage.nao_entrega.concat(b3.coverage.entrega_pela_metade));

  const alerta = $("lacuna");
  if (!pendentes.length) alerta.style.display = "none";
  else {
    const [ticker, dados] = pendentes[0];
    const jaSabe = (b3.cost_basis[ticker] || {}).valor_brl || 0;
    alerta.innerHTML = "<p><b>Falta saber por quanto você comprou " + ticker + ".</b> " +
      "A compra é anterior a " + b3.base_starts.split("-").reverse().join("/") + " e não " +
      "está no histórico da B3. Sem ela o imposto não sai, e aqui não se chuta imposto: " +
      "chutado tem a mesma cara de calculado.</p>";
    alerta.append(campoDeCusto(ticker, jaSabe));
  }
  mostra("perguntas");
  etapa(1);
  rolaPara($("perguntas"), "start");
};

/* --- o custo informado pelo cliente --- */
// A aritmética abaixo é transcrição literal de resolver(), em
// tests/test_b3_connection.py, que é comparada com o módulo de verdade em
// vários valores de custo. Reescrever a apuração inteira aqui criaria duas
// implementações da mesma regra, e elas divergem em silêncio porque as duas
// continuam plausíveis sozinhas. A tela faz só a aritmética final.
const custosInformados = {};
let perfilAtual = null, planoAtual = null;

// Aceita "180.000,50" e "180000,50"; um ponto seguido de uma ou duas casas é
// lido como decimal, porque é assim que muita gente digita.
function leValor(txt) {
  const limpo = String(txt).replace(/[^\d.,-]/g, "");
  if (!limpo) return NaN;
  const decimal = limpo.includes(",")
    ? limpo.replace(/\./g, "").replace(",", ".")
    : (/^\d+\.\d{1,2}$/.test(limpo) ? limpo : limpo.replace(/\./g, ""));
  return parseFloat(decimal);
}

function campoDeCusto(ticker, jaSabe) {
  const caixa = el("div", "informar");
  const anterior = custosInformados[ticker];
  caixa.innerHTML =
    "<label for='custo'>Quanto você pagou, ao todo, pela sua posição em " + ticker + "?</label>" +
    "<div class='campo'><input id='custo' type='text' inputmode='decimal' autocomplete='off' " +
    "placeholder='R$ 0,00' aria-describedby='custo-ajuda'>" +
    "<button class='btn' type='button' id='custo-ok'>Informar</button></div>" +
    "<p class='ajuda' id='custo-ajuda'>Some tudo que pagou pela posição, em todas as compras. " +
    (jaSabe > 0 ? "Das compras que a B3 mandou já sabemos " + BRL(jaSabe) + ". Falta somar as " +
                  "anteriores. " : "") +
    "O valor está na sua declaração de imposto de renda ou nas notas de corretagem.</p>";
  const campo = caixa.querySelector("#custo");
  // Campo de dinheiro devolve centavo: 1.000,5 é um valor que ninguém digitou.
  if (anterior !== undefined) campo.value = anterior.toLocaleString("pt-BR",
    anterior % 1 ? { minimumFractionDigits: 2 } : {});
  caixa.querySelector("#custo-ok").onclick = () => informar(ticker, jaSabe);
  campo.onkeydown = e => { if (e.key === "Enter") informar(ticker, jaSabe); };
  return caixa;
}

function informar(ticker, jaSabe) {
  const campo = $("custo"), ajuda = $("custo-ajuda");
  const valor = leValor(campo.value);
  if (!isFinite(valor) || valor < 0) {
    campo.setAttribute("aria-invalid", "true");
    ajuda.className = "ajuda ruim";
    ajuda.textContent = "Informe um valor em reais, como 180.000,00.";
    campo.focus();
    return;
  }
  custosInformados[ticker] = valor;
  const alerta = $("lacuna");
  alerta.className = "resolvido";
  alerta.innerHTML = "<p><b>" + ticker + ": " + BRL(valor) + " informados.</b> " +
    "O imposto fecha, e os dois planos abaixo já estão com ele. O valor foi declarado por " +
    "você e não conferido contra nota de corretagem.</p>";
  // Um dígito a mais muda o imposto em ordem de grandeza, e quem digitou errado
  // precisa de caminho de volta, sem ele, o único recerto é recarregar a página.
  const trocar = el("button", "link", "Corrigir o valor");
  trocar.type = "button";
  trocar.onclick = () => {
    alerta.className = "aviso erro";
    alerta.innerHTML = "<p><b>Corrigindo o custo de " + ticker + ".</b> O valor anterior era " +
      BRL(valor) + ".</p>";
    alerta.append(campoDeCusto(ticker, jaSabe));
    $("custo").focus();
  };
  alerta.append(trocar);
  if (perfilAtual) render(perfilAtual);
}

function resolvido(m) {
  const r = m.pending_resolution;
  if (!r || !r.positions || !r.positions.length) return m;
  if (r.positions.some(p => !(p.ticker in custosInformados))) return m;

  let total = r.fixed_brl;
  const impostoDaCesta = {}, ganhoDaCesta = {};
  Object.entries(r.buckets).forEach(([cesta, cfg]) => {
    let ganho = cfg.other_gain_brl;
    r.positions.forEach(p => {
      if (p.bucket === cesta) ganho += p.sale_brl - custosInformados[p.ticker] * p.sale_fraction;
    });
    ganho -= cfg.carried_loss_brl;
    const imposto = (ganho > 0 && cesta !== "fora_do_escopo" && !cfg.exempt_month)
      ? ganho * cfg.rate : 0;
    ganhoDaCesta[cesta] = ganho + cfg.carried_loss_brl;
    impostoDaCesta[cesta] = imposto;
    total += imposto;
  });

  const cestas = Object.assign({}, m.tax_by_bucket);
  Object.keys(impostoDaCesta).forEach(c => {
    cestas[c] = { realised_gain_brl: ganhoDaCesta[c], tax_brl: impostoDaCesta[c] };
  });
  const moves = m.moves.map(x => {
    if (!(x.ticker in custosInformados) || x.action === "manter") return x;
    const p = r.positions.find(q => q.ticker === x.ticker);
    if (!p) return x;
    return Object.assign({}, x, {
      realised_gain_brl: p.sale_brl - custosInformados[x.ticker] * p.sale_fraction,
      notes: ["custo informado por você, não conferido contra nota de corretagem"],
    });
  });
  return Object.assign({}, m, {
    transition_tax_brl: total - m.transition_cost_brl,
    transition_total_brl: total,
    transition_cost_pct: total / m.total_brl,
    tax_is_complete: true,
    positions_without_cost_basis: [],
    unpriced_sale_brl: 0,
    tax_by_bucket: cestas,
    moves: moves,
  });
}

/* --- perguntas --- */
const escolha = DADOS.questionnaire.questions.filter(q => q.kind === "escolha");
const qsBox = $("qs");
escolha.forEach(q => {
  const box = el("div", "q");
  box.append(el("p", null, q.prompt), el("p", "help", q.help));
  const opts = el("div", "opts");
  q.options.forEach(o => {
    const b = el("button", "opt", o.label);
    b.type = "button";
    b.setAttribute("aria-pressed", "false");
    b.onclick = () => {
      respostas[q.key] = o;
      opts.querySelectorAll(".opt").forEach(x => x.setAttribute("aria-pressed", "false"));
      b.setAttribute("aria-pressed", "true");
      avaliar();
    };
    opts.append(b);
  });
  box.append(opts);
  qsBox.append(box);
});

const resumoBox = $("resumo");
// Quem abriu o formulário para mudar uma resposta continua com ele aberto: antes
// ele fechava sozinho a cada clique, e a página saltava a cada opção escolhida.
// Fecha quando a pessoa disser que terminou.
let editando = false;
function editar(abrir) {
  editando = abrir;
  qsBox.classList.toggle("hidden", !abrir);
  $("chips").classList.toggle("hidden", abrir);
  $("alterar").textContent = abrir ? "Pronto" : "Alterar respostas";
  if (abrir) rolaPara(qsBox, "start");
}
$("alterar").onclick = () => editar(!editando);

function avaliar() {
  if (Object.keys(respostas).length < escolha.length) {
    $("veredito").textContent = "";
    esconde("mapa", "planos-sec", "razao-sec", "acompanhar-sec", "alertas-sec");
    return;
  }
  // Respondido, o formulário vira uma linha: no celular, deixá-lo aberto obriga
  // a rolar por tudo que já foi respondido para chegar ao resultado.
  if (!editando) qsBox.classList.add("hidden");
  resumoBox.classList.remove("hidden");
  $("chips").innerHTML = escolha.map(q => "<span>" + respostas[q.key].brief + "</span>").join("");

  // O perfil é o menor teto, igual ao módulo: sem soma, sem peso, sem nota.
  let perfil = "arrojado";
  escolha.forEach(q => {
    const o = respostas[q.key];
    if (o.caps_profile && RANK[o.caps_profile] < RANK[perfil]) perfil = o.caps_profile;
  });
  // Todas as respostas que prenderam no teto final, não só a primeira: quando
  // duas apertam igual, mostrar uma faz a outra parecer não ter contado.
  const causas = escolha.map(q => respostas[q.key])
    .filter(o => o.caps_profile === perfil && o.note);
  const pior = DADOS.questionnaire.worst_measured_drawdown[perfil];
  $("veredito").innerHTML = "Perfil <b>" + perfil + "</b>, " +
    (causas.length ? causas.map(o => o.note).join(", e ")
                   : "nenhuma resposta impôs teto abaixo do máximo") +
    ". A pior queda já medida neste perfil foi de <b class='num neg'>" + PCT(pior) + "</b>.";
  etapa(2);
  if (perfilAtual !== perfil) planoAtual = null;
  render(perfil);
}

/* --- mapa --- */
function render(perfil) {
  perfilAtual = perfil;
  desenhaCarteira();
  const p = DADOS.profiles[perfil];
  const a = resolvido(p.adequar), b = resolvido(p.adaptar);
  mostra("mapa", "planos-sec");

  // "Sem movimentação" e "não atualizou" precisam ser distinguíveis aqui. Com
  // 97% de SLA a carteira falha em chegar cerca de uma vez por mês, e tratar os
  // dois casos igual mostra a posição de anteontem como se fosse a de ontem.
  const carga = b3.freshness.example;
  const faixa = $("quando");
  faixa.className = "quando" + (carga.utilizavel ? "" : " velho");
  faixa.innerHTML = "<span>Posição de <b>" +
    carga.data_referencia.split("-").reverse().join("/") + "</b></span><span>" +
    carga.explicacao + "</span>";

  $("aderencia").textContent = PCT(a.alignment) + " já serve";
  $("aderencia-txt").textContent =
    "De " + BRL(a.total_brl) + ", essa parte já está de acordo com o que a política declara " +
    "para o perfil " + perfil + ". É o resto que os dois planos tratam de forma diferente.";

  const fora = b.out_of_scope_brl / b.total_brl;
  barra("bar-hoje", [b.equity_before, 1 - b.equity_before - fora, fora]);
  barra("bar-alvo", [b.equity_budget, 1 - b.equity_budget, 0]);

  desenhaFgc(a);
  regua(perfil);
  planos(perfil, a, b);
}

/* --- o quanto a régua erra ---------------------------------------------
   Não é projeção de patrimônio, e a diferença é o produto inteiro. Todo
   janeiro a regra projeta uma faixa para o ano seguinte usando só o que se
   sabia até ali; depois o ano acontece e cai dentro ou fora. O que se publica
   é a contagem, não a promessa. */
function regua(perfil) {
  const c = DADOS.calibracao[perfil];
  if (!c) return;
  const host = $("regua");
  const dentro = c.cobertura.inside, total = c.cobertura.total;
  const vies = c.vies_pp;
  const otimista = vies < -0.5;

  host.innerHTML = "";
  host.append(el("h3", null, "O quanto esta régua erra"));
  host.append(el("p", null,
    "Todo janeiro a regra projeta uma faixa para os doze meses seguintes, usando só o " +
    "que se sabia até aquele dia. Depois o ano acontece. Em <b>" + total + " anos</b>, o " +
    "resultado caiu dentro da faixa em <b>" + dentro + "</b>."));
  host.append(el("p", null, otimista
    ? "E o meio da faixa ficou <b class='neg'>" + Math.abs(vies).toFixed(1).replace(".", ",") +
      " pontos otimista por ano</b>: a régua erra para o lado que favorece quem vende. " +
      "Está publicado aqui porque é o número que ninguém mostra."
    : (vies > 0.5
        ? "E o meio da faixa ficou <b>" + vies.toFixed(1).replace(".", ",") +
          " pontos abaixo</b> do que aconteceu: aqui a régua erra para o lado conservador."
        : "E o meio da faixa não puxou para lado nenhum de forma perceptível: o desvio " +
          "médio foi de " + Math.abs(vies).toFixed(1).replace(".", ",") + " ponto por ano.")));
  // Sem esta linha, "8 de 8" vira argumento de venda. Com oito observações e
  // erro padrão de catorze pontos, nenhuma contagem dessas se distingue de
  // acaso, e é justamente o perfil que acertou tudo que precisa dizer isso.
  const ep = Math.round((c.cobertura.standard_error || 0) * 100);
  host.append(el("p", null,
    c.nota
      ? "<b>A régua não mede este perfil.</b> " + c.nota
      : "<b>Oito anos é pouco.</b> A margem de erro é de " + ep + " pontos: acertar 6 ou 8 " +
        "não se distingue de sorte. Isto mede a régua, não promete resultado."));
  host.append(grafico(c.anos));
  const chaves = el("div", "chaves",
    "<span><i style='background:var(--line-strong)'></i>faixa projetada em janeiro</span>" +
    "<span><i style='background:var(--acao)'></i>o que aconteceu</span>" +
    "<span><i style='background:var(--neg)'></i>ficou fora da faixa</span>");
  host.append(chaves);
}


/* --- a carteira inteira --- */
// Três origens, uma lista só. Separar em três telas faria a pessoa somar de
// cabeça, e é justamente a soma que decide o plano.
//
// Valor ausente aparece como "?" e nunca como zero. Zero é uma resposta, e a
// diferença entre "vale zero" e "não sei quanto vale" é o que decide se o plano
// pode ser calculado. Enquanto houver "?", o total se declara parcial.
const acrescentados = [];
const valoresInformados = {};

function carteiraToda() {
  const daB3 = (b3.posicoes || []).map(p => Object.assign({}, p, {
    valor_brl: valoresInformados[p.nome] != null ? valoresInformados[p.nome] : p.valor_brl,
  }));
  return daB3.concat(acrescentados);
}

function desenhaCarteira() {
  const itens = carteiraToda();
  const host = $("lista-posicoes");
  host.innerHTML = "";

  itens.forEach((p, i) => {
    const linha = el("div", "pos");
    const temValor = p.valor_brl != null;
    linha.append(el("b", null, p.nome));
    const v = el("span", "val" + (temValor ? "" : " sem-valor"),
                 temValor ? BRL(p.valor_brl) : "R$ ?");
    linha.append(v);

    const de = el("span", "de");
    const detalhe = [p.tipo, p.origem];
    if (p.vencimento) detalhe.push("vence em " + p.vencimento.split("-").reverse().join("/"));
    if (p.emissor) detalhe.push(p.emissor);
    de.textContent = detalhe.join(" · ");

    if (!temValor) {
      de.append(document.createTextNode(". " + p.falta + ". "));
      const b = el("button", "pos-acao", "Informar o valor");
      b.type = "button";
      b.onclick = () => pedeValor(p.nome);
      de.append(b);
    } else if (p.origem === "informado por você") {
      de.append(document.createTextNode(". "));
      const b = el("button", "pos-acao", "Remover");
      b.type = "button";
      b.onclick = () => { acrescentados.splice(acrescentados.indexOf(p), 1); desenhaCarteira(); };
      de.append(b);
    }
    linha.append(de);
    host.append(linha);
  });

  const comValor = itens.filter(p => p.valor_brl != null);
  const sem = itens.filter(p => p.valor_brl == null);
  const total = comValor.reduce((s, p) => s + p.valor_brl, 0);
  $("total-carteira").innerHTML =
    "<span>" + (sem.length ? "Total do que já tem valor" : "Total") + "</span>" +
    "<span>" + BRL(total) + "</span>";

  const aviso = $("sem-valor");
  if (sem.length) {
    aviso.classList.remove("hidden");
    aviso.innerHTML = "<p><b>" + sem.length + " posição(ões) sem valor.</b> O total é " +
      "parcial, e toda porcentagem sobre o patrimônio sai baixa: " +
      sem.map(p => escapa(p.nome)).join(", ") + ".</p>";
  } else {
    aviso.classList.add("hidden");
  }
}

function pedeValor(nome) {
  const bruto = prompt("Quanto vale " + nome + " hoje, em reais?");
  if (bruto == null) return;
  const v = leValor(bruto);
  if (!isFinite(v) || v < 0) { alert("Valor não reconhecido. Use algo como 25.000,00"); return; }
  valoresInformados[nome] = v;
  desenhaCarteira();
  if (perfilAtual) render(perfilAtual);
}

/* --- o limite do FGC, inteiro --- */
// Havia meia conta aqui: so o teto de 250 mil por conglomerado, so o primeiro
// estouro na tela, e o limite lido de um numero escrito na frase. Faltavam
// duas coisas que mudam a resposta.
//
// A primeira e o teto movel de um milhao por CPF em quatro anos. Ele e o total
// que o FGC paga a uma pessoa somando todas as instituicoes na janela, entao
// espalhar tres milhoes por quinze bancos, cada um abaixo de 250 mil, nao deixa
// os tres milhoes garantidos: deixa um milhao. Quem so olha o teto por emissor
// nunca ve isso.
//
// A segunda e que o que a pessoa acrescenta a mao nao entrava na conta. Os
// papeis que mais dependem do FGC sao justamente CDB, LCI e LCA, que a B3 nao
// manda e que ela digita, e eles eram invisiveis para o unico aviso que
// existia sobre eles.
function exposicaoPorConglomerado(a) {
  const soma = {};
  const junta = (nome, valor) => {
    if (!nome || !(valor > 0)) return;
    soma[nome] = (soma[nome] || 0) + valor;
  };
  Object.entries(a.fgc_exposure || a.fgc_breaches || {}).forEach(([n, v]) => junta(n, v));
  acrescentados.forEach(item => {
    if (item.regua && item.regua.fgc) junta(item.conglomerado || item.emissor, item.valor_brl);
  });
  return soma;
}

function desenhaFgc(a) {
  const caixa = $("fgc");
  const limites = DADOS.renda_fixa.motor.fgc;
  const porConglomerado = exposicaoPorConglomerado(a);
  const r = resumoFgc(porConglomerado, limites);

  if (!r.estouros.length && !r.acima_do_teto_movel) { caixa.style.display = "none"; return; }
  caixa.style.display = "block";

  const partes = [];
  if (r.estouros.length) {
    const linhas = r.estouros.map(n => "<li>" + escapa(n) + ": " + BRL(porConglomerado[n]) +
      ", sendo " + BRL(porConglomerado[n] - limites.por_conglomerado_brl) + " a descoberto</li>");
    partes.push("<p><b>" + BRL(r.excedente_por_emissor) + " acima do teto por emissor.</b> " +
      "A garantia cobre " + BRL(limites.por_conglomerado_brl) + " por CPF em cada " +
      "conglomerado.</p><ul>" + linhas.join("") + "</ul>");
  }
  if (r.acima_do_teto_movel) {
    partes.push("<p><b>" + BRL(r.excedente_movel) + " além do teto de quatro anos.</b> " +
      "Somando o que cabe em cada emissor dá " + BRL(r.coberto) + ", e o FGC paga no máximo " +
      BRL(limites.teto_movel_brl) + " por CPF em " + limites.janela_anos + " anos, " +
      "por mais bancos que sejam. Dividir em mais emissores não levanta esse teto.</p>");
  }
  partes.push("<p>Os dois planos mantêm a posição: é risco assumido, e assumir precisa " +
    "ser decisão.</p>");
  caixa.innerHTML = partes.join("");
}

/* --- a regua da renda fixa --- */
// A mesma conta que fixed_income_catalog faz em Python, refeita aqui porque a
// pessoa digita a oferta e espera o numero na hora. As tabelas nao sao
// reescritas: elas chegam prontas em DADOS.renda_fixa.motor, e um teste roda as
// duas implementacoes sobre a mesma grade de casos.

function aliquotaIR(dias) {
  const faixas = DADOS.renda_fixa.motor.ir;
  for (const f of faixas) if (dias <= f.ate_dias) return f.aliquota;
  return faixas[faixas.length - 1].aliquota;
}

// O IOF morde o rendimento antes do imposto de renda e some no trigesimo dia.
function fatorIOF(dias) {
  const tabela = DADOS.renda_fixa.motor.iof;
  if (dias >= 30) return 0;
  return tabela[Math.max(dias - 1, 0)];
}

function brutoAoAno(papel, cdi, ipca) {
  if (papel.indice === "cdi" || papel.indice === "selic") return cdi * papel.taxa;
  if (papel.indice === "cdi_mais") return cdi + papel.taxa;
  if (papel.indice === "pre") return papel.taxa;
  if (papel.indice === "ipca") return (1 + ipca) * (1 + papel.taxa) - 1;
  return NaN;
}

function diasEntre(deIso, ateIso) {
  const dia = 86400000;
  return Math.round((Date.parse(ateIso + "T00:00:00Z") - Date.parse(deIso + "T00:00:00Z")) / dia);
}

// Rendimento liquido anualizado no horizonte do proprio papel. Comparar um CDB
// de seis meses com um de tres anos pela taxa anunciada ignora que o primeiro
// paga 22,5% de imposto e o segundo 15%.
function liquidoAoAno(papel, referencia) {
  const rf = DADOS.renda_fixa;
  const regra = rf.motor.produtos[papel.tipo];
  if (!regra) return null;
  const dias = diasEntre(referencia, papel.vencimento);
  if (!(dias > 0)) return null;
  const anos = dias / rf.motor.dias_no_ano;

  const bruto = brutoAoAno(papel, rf.cdi_anual, rf.ipca_anual);
  if (!isFinite(bruto)) return null;
  const depoisDeTaxas = bruto - (papel.custodia || 0);
  const acumulado = Math.pow(1 + depoisDeTaxas, anos) - 1;

  const ir = regra.ir ? aliquotaIR(dias) : 0;
  const iof = regra.ir ? fatorIOF(dias) : 0;
  const liquidoAcumulado = acumulado * (1 - iof) * (1 - ir);
  const liquido = Math.pow(1 + liquidoAcumulado, 1 / anos) - 1;
  return {
    dias: dias, bruto: bruto, ir: ir, iof: iof, liquido: liquido,
    // Fracao do CDI bruto. E o numero que se compara, porque indice nao paga
    // imposto: um CDB anunciado a 118% do CDI entrega perto de 101% dele.
    sobre_cdi: rf.cdi_anual ? liquido / rf.cdi_anual : null,
    fgc: regra.fgc, regime: regra.regime,
  };
}

// O piso: Tesouro Selic mais curto, liquidez diaria, sem risco de credito, ja
// com custodia. Toda oferta de banco e medida contra ele.
function pisoLiquido(vencimento, referencia) {
  const piso = DADOS.renda_fixa.piso;
  return liquidoAoAno({ tipo: "TESOURO", indice: "selic", taxa: piso.rate,
                        vencimento: vencimento, custodia: piso.custody_fee_annual },
                      referencia);
}

// O resumo do FGC, sem tocar em tela. Fica aqui junto da regua porque e conta,
// e conta que imprime dinheiro precisa de teste: o ramo do teto movel so
// aparece em carteira grande, que e justamente a que ninguem monta a mao para
// conferir.
//
// "coberto" soma o que cabe em cada emissor, nao o que a pessoa tem. Espalhar
// tres milhoes por quinze bancos deixa um milhao garantido, nao tres, porque o
// teto de quatro anos e por CPF somando todas as instituicoes.
function resumoFgc(porConglomerado, limites) {
  const nomes = Object.keys(porConglomerado);
  const estouros = nomes
    .filter(n => porConglomerado[n] > limites.por_conglomerado_brl)
    .sort((x, y) => porConglomerado[y] - porConglomerado[x]);
  const coberto = nomes.reduce(
    (s, n) => s + Math.min(porConglomerado[n], limites.por_conglomerado_brl), 0);
  return {
    estouros: estouros,
    excedente_por_emissor: estouros.reduce(
      (s, n) => s + porConglomerado[n] - limites.por_conglomerado_brl, 0),
    coberto: coberto,
    excedente_movel: Math.max(0, coberto - limites.teto_movel_brl),
    acima_do_teto_movel: coberto > limites.teto_movel_brl,
  };
}



const TIPOS_RF = ["CDB", "LCI", "LCA", "LC", "RDB"];

function mostraCamposRF() {
  const eRF = TIPOS_RF.indexOf($("add-tipo").value) >= 0;
  $("add-rf").classList.toggle("hidden", !eRF);
  if (!eRF) $("add-regua").classList.add("hidden");
}

// A pessoa digita 110 para "110% do CDI" e 1,2 para "CDI mais 1,2%". Os dois
// sao percentuais na tela e fracao na conta, e por isso a leitura e a mesma.
// O que muda entre eles e o significado, e quem decide isso e brutoAoAno.
function leTaxa(texto) {
  const bruto = leValor(texto);
  return isFinite(bruto) && bruto > 0 ? bruto / 100 : NaN;
}

$("add-tipo").onchange = mostraCamposRF;
mostraCamposRF();

$("add-botao").onclick = () => {
  const nome = $("add-nome").value.trim();
  const valor = leValor($("add-valor").value);
  const tipo = $("add-tipo").value;
  const erro = $("add-erro");
  const diz = m => { erro.textContent = m; erro.classList.remove("hidden"); };
  if (!nome) { diz("Escreva o que é."); return; }
  if (!isFinite(valor) || valor <= 0) { diz("Escreva quanto vale, como 25.000,00."); return; }

  const item = { nome: nome, tipo: tipo, origem: "informado por você", valor_brl: valor,
                 quantidade: null, vencimento: null, emissor: null,
                 completa: true, falta: "" };

  if (TIPOS_RF.indexOf(tipo) >= 0) {
    const emissor = $("add-emissor").value.trim();
    const taxa = leTaxa($("add-taxa").value);
    const venc = $("add-venc").value;
    if (!emissor) { diz("Escreva quem emite. É o que decide o limite do FGC."); return; }
    if (!isFinite(taxa)) { diz("Escreva a taxa, como 110 para 110% do CDI."); return; }
    if (!venc) { diz("Escreva o vencimento. Sem ele não dá para saber o imposto."); return; }
    item.emissor = emissor;
    item.conglomerado = emissor;
    item.indice = $("add-indice").value;
    item.taxa = taxa;
    item.vencimento = venc;
    const r = liquidoAoAno(item, DADOS.renda_fixa.referencia);
    if (!r) { diz("O vencimento precisa ser depois de hoje."); return; }
    item.regua = r;
  }

  erro.classList.add("hidden");
  acrescentados.push(item);
  $("add-nome").value = ""; $("add-valor").value = "";
  $("add-emissor").value = ""; $("add-taxa").value = ""; $("add-venc").value = "";
  mostraRegua(item);
  desenhaCarteira();
  // O aviso do FGC é desenhado junto do plano, e um papel acrescentado depois
  // dele deixava o aviso velho na tela: a pessoa somava trezentos mil num banco
  // que já tinha duzentos e não via nada mudar. Redesenhar o plano inteiro é o
  // que o resto da tela já faz quando a carteira muda.
  if (perfilAtual) render(perfilAtual);
};

// O que o papel rende na mesma unidade que todo o resto, e contra o piso.
function mostraRegua(item) {
  const caixa = $("add-regua");
  if (!item.regua) { caixa.classList.add("hidden"); return; }
  const r = item.regua;
  const piso = pisoLiquido(item.vencimento, DADOS.renda_fixa.referencia);
  const diferenca = piso ? (r.liquido - piso.liquido) * 100 : null;
  const veredito = diferenca === null ? ""
    : diferenca >= 0
      ? "<p>Rende <b>" + diferenca.toFixed(2).replace(".", ",") + " ponto</b> ao ano acima do "
        + "Tesouro Selic no mesmo prazo. É o que este papel paga pelo risco de crédito e "
        + "pela carência.</p>"
      : "<p>Rende <b>" + Math.abs(diferenca).toFixed(2).replace(".", ",") + " ponto</b> ao ano "
        + "abaixo do Tesouro Selic no mesmo prazo, que tem liquidez diária e não tem risco de "
        + "crédito. A oferta está cobrando risco sem pagar por ele.</p>";
  caixa.innerHTML = "<p><b>" + escapa(item.nome) + "</b> rende <b>" + PCT(r.liquido) +
    "</b> líquido ao ano, que é <b>" + PCT(r.sobre_cdi) + " do CDI</b>." +
    (r.ir ? " O imposto no prazo é de " + PCT(r.ir) + "." : " É isento de imposto de renda.") +
    "</p>" + veredito +
    "<p class='ajuda'>" + (r.fgc ? "Coberto pelo FGC, dentro dos limites abaixo."
                                 : "Sem cobertura do FGC.") +
    " Régua com CDI a " + PCT(DADOS.renda_fixa.cdi_anual) + " ao ano" +
    (item.indice === "ipca" ? " e IPCA a " + PCT(DADOS.renda_fixa.ipca_anual) + ", premissa declarada" : "") +
    ". Não é recomendação.</p>";
  caixa.classList.remove("hidden");
}


/* --- alertas de mudança na estratégia --- */
// Só aparece para quem escolheu adequar, ou seja, para quem está copiando a
// política. Quem escolheu manter a própria carteira não recebe alerta de uma
// estratégia que ele não segue: seria ruído com aparência de instrução.
//
// O alerta diz o que aconteceu e o que isso pede da carteira dele, em reais,
// porque "a camada reduziu para 55%" não é acionável e "venda R$ 12.600 de
// ações" é.
function alertas(perfil, chave) {
  const m = DADOS.mudancas && DADOS.mudancas.perfis ? DADOS.mudancas.perfis[perfil] : null;
  if (chave !== "adequar" || !m) { esconde("alertas-sec"); return; }
  mostra("alertas-sec");

  const host = $("alertas");
  host.innerHTML = "";
  const tudo = carteiraToda();
  const patrimonio = tudo.reduce((s, p) => s + (p.valor_brl || 0), 0);
  // Quantas linhas ainda não têm valor. O número em reais abaixo sai deste
  // patrimônio, então enquanto faltar posição ele é piso, não valor final, e a
  // tela precisa dizer isso no mesmo parágrafo em que dá a ordem de grandeza.
  const semValor = tudo.filter(p => p.valor_brl == null).length;

  if (!m.changes.length) {
    $("alertas-lede").textContent =
      "Nada mudou na política desde a decisão de janeiro. Se algo mudar, aparece aqui.";
    return;
  }
  $("alertas-lede").textContent =
    "Você escolheu seguir a política. Quando ela se mexe, a sua carteira precisa " +
    "acompanhar, e é isto que mudou até agora.";

  m.changes.forEach(c => {
    const caixa = el("div", "alerta");
    caixa.append(el("p", "quando", c.date.split("-").reverse().join("/")));
    const p1 = el("p");
    p1.innerHTML = "A camada de proteção entrou: " + c.why + ", no fechamento de " +
      c.observed_on.split("-").reverse().join("/") + ". Cada ação passou a valer <b>" +
      Math.round(c.factor * 100) + "%</b> do peso de janeiro.";
    caixa.append(p1);

    const p2 = el("p");
    const saiu = c.from_equity - c.to_equity;
    p2.innerHTML = "Na sua carteira: vender <b>" + BRL(patrimonio * saiu) + "</b> em ações " +
      "para o CDI, na mesma proporção. A parte em S&P 500 fica." +
      (semValor ? " Piso, porque " + semValor + " posição(ões) sem valor ficam fora da conta."
                : "");
    caixa.append(p2);
    host.append(caixa);
  });
}

/* --- acompanhar --- */
// A faixa foi calculada no primeiro pregão do ano e não se mexe. Se ela se
// ajustasse ao que foi acontecendo, nunca erraria, e uma faixa que nunca erra
// não mede nada. O que anda é a linha do realizado.
//
// A comparação é por pregão decorrido, não por data: em agosto o realizado é
// comparado com a faixa de agosto. Comparar meio ano com a faixa do ano
// inteiro faria a carteira parecer atrasada só porque o ano não acabou.
function acompanhar(perfil) {
  const ac = DADOS.acompanhamento;
  const r = ac.perfis[perfil];
  if (!r) { esconde("acompanhar-sec"); return; }
  mostra("acompanhar-sec");
  etapa(3);

  const n = r.agora;
  $("ac-quando").textContent = n.sessions + " pregões de " + ac.ano +
    " · até " + n.date.split("-").reverse().join("/");
  $("ac-numero").textContent = PCT(n.realised);
  $("ac-numero").className = "big num" + (n.realised < 0 ? " neg" : "");
  const quando = r.faixa_de_janeiro ? "projetada em janeiro"
    : "desenhada em " + r.faixa_desenhada.split("-").reverse().join("/") + ", com dados anteriores a " + ac.ano;
  $("ac-frase").innerHTML = "Para este ponto do ano, a faixa " + quando + " vai de <b>" +
    PCT(n.p10) + "</b> a <b>" + PCT(n.p90) + "</b>. O resultado está <b>" +
    (n.inside ? "dentro" : "fora") + "</b> dela.";
  $("ac-grafico").innerHTML = cone(r.faixa, r.realizado);
  $("ac-legenda").textContent = r.faixa_de_janeiro
    ? "Área: o projetado em janeiro. Linha: o que aconteceu."
    : "Área: o projetado para o ano. Linha: o que aconteceu. Esta carteira foi declarada com o ano em curso, e a série dela é reconstruída.";
  $("ac-limite").innerHTML = "<p>" + (r.faixa_de_janeiro ? ac.limitacao : ac.limitacao_tardia) + "</p>";
}

function cone(faixaBruta, realizado) {
  // No primeiro pregão o retorno acumulado é zero por definição, e a faixa tem
  // largura zero junto. Sem esse ponto o desenho começa no pregão cinco e a
  // linha aparece solta à esquerda da área, como se estivesse fora dela.
  const faixa = [{ sessions: 0, p10: 0, p50: 0, p90: 0 }].concat(faixaBruta);
  const W = 320, H = 140, T = 10, B = 18, L = 4, R = 4;
  const maxS = faixa[faixa.length - 1].sessions;
  const baixo = Math.min(...faixa.map(p => p.p10), ...realizado.map(p => p.r));
  const alto = Math.max(...faixa.map(p => p.p90), ...realizado.map(p => p.r));
  const folga = (alto - baixo) * 0.08 || 0.01;
  const min = baixo - folga, max = alto + folga;
  const x = s => L + (W - L - R) * (s / maxS);
  const y = v => T + (H - T - B) * (1 - (v - min) / (max - min));

  // A faixa é um polígono só: o contorno de cima na ida, o de baixo na volta.
  const area = faixa.map(p => x(p.sessions) + "," + y(p.p90)).join(" ") + " " +
    faixa.slice().reverse().map(p => x(p.sessions) + "," + y(p.p10)).join(" ");
  const linha = realizado.map(p => x(p.sessions) + "," + y(p.r)).join(" ");
  const fim = realizado[realizado.length - 1];

  return "<svg viewBox='0 0 " + W + " " + H + "' role='img' aria-label='" +
    "A faixa projetada para o ano e o retorno acumulado até agora, por pregão decorrido.'>" +
    "<polygon points='" + area + "' fill='var(--acao-fraco)'/>" +
    "<polyline points='" + linha + "' fill='none' stroke='var(--acao)' stroke-width='2' " +
      "stroke-linejoin='round' stroke-linecap='round'/>" +
    "<circle cx='" + x(fim.sessions) + "' cy='" + y(fim.r) + "' r='4' fill='var(--acao)' " +
      "stroke='var(--canvas)' stroke-width='2'/>" +
    "<text x='" + x(0) + "' y='" + (H - 5) + "' font-size='9' fill='var(--fg-2)'>janeiro</text>" +
    "<text x='" + x(maxS) + "' y='" + (H - 5) + "' font-size='9' fill='var(--fg-2)' " +
      "text-anchor='end'>fim do ano</text></svg>";
}

function grafico(anos) {
  const L = 8, R = 8, T = 12, B = 22, W = 320, H = 132;
  const baixo = Math.min(...anos.map(a => Math.min(a.p10, a.realised)));
  const alto = Math.max(...anos.map(a => Math.max(a.p90, a.realised)));
  const folga = (alto - baixo) * 0.08;
  const min = baixo - folga, max = alto + folga;
  const y = v => T + (H - T - B) * (1 - (v - min) / (max - min));
  const passo = (W - L - R) / anos.length;
  const x = i => L + passo * (i + 0.5);

  const svg = ["<svg viewBox='0 0 " + W + " " + H + "' role='img' aria-label='" +
    "Para cada ano, a faixa projetada em janeiro e o retorno que de fato aconteceu.'>"];
  // O eixo de porcentagem, a linha do zero e o traço da mediana saíram. O
  // gráfico responde uma pergunta só, o resultado caiu dentro do que foi
  // projetado?, e nenhum dos três ajudava a responder.
  anos.forEach((a, i) => {
    const cx = x(i);
    svg.push("<line x1='" + cx + "' x2='" + cx + "' y1='" + y(a.p10) + "' y2='" + y(a.p90) +
      "' stroke='var(--acao-fraco)' stroke-width='9' stroke-linecap='round'/>");
    // Anel na cor do fundo: sem ele o ponto tem contraste 1,0 contra a barra no
    // tema escuro, ou seja, some justamente quando cai dentro da faixa, que é
    // o caso comum e o que o gráfico existe para mostrar.
    svg.push("<circle cx='" + cx + "' cy='" + y(a.realised) + "' r='4' fill='" +
      (a.inside ? "var(--acao)" : "var(--neg)") +
      "' stroke='var(--canvas)' stroke-width='2'/>");
    svg.push("<text x='" + cx + "' y='" + (H - 6) + "' text-anchor='middle' font-size='9' " +
      "fill='var(--fg-2)'>" + String(a.year).slice(2) + "</text>");
  });
  svg.push("</svg>");

  const fig = el("figure");
  fig.innerHTML = svg.join("") +
    "<figcaption>Cada barra é a faixa de 80% projetada em janeiro daquele ano, com o " +
    "traço no meio. O ponto é o retorno que aconteceu.</figcaption>";
  return fig;
}

function barra(id, partes) {
  // Cada faixa carrega o próprio par de cores, e não uma cor de texto só para
  // todas. O rótulo era var(--canvas), "o oposto do fundo da página", o que
  // funcionava no escuro e reprovava no claro: branco sobre a faixa neutra dava
  // 1,91 de contraste, e o número sumia dentro da barra. Medidos, claro e
  // escuro: 5,35 e 10,66 na faixa de ações, 10,37 e 9,59 na neutra, 5,31 e
  // 7,13 na de perda.
  const faixas = [
    ["var(--acao-vivo)", "var(--acao-vivo-fg)"],
    ["var(--line-strong)", "var(--fg)"],
    ["var(--neg)", "var(--canvas)"],
  ];
  const host = $(id);
  host.innerHTML = "";
  host.style.cssText = "display:flex;height:2rem;overflow:hidden;gap:1px";
  partes.forEach((v, i) => {
    if (v <= 0.001) return;
    const s = el("div");
    s.style.cssText = "flex:" + v + ";background:" + faixas[i][0] +
      ";display:grid;place-items:center;font-size:12px;color:" + faixas[i][1];
    s.className = "num";
    s.textContent = v > 0.09 ? PCT(v, 0) : "";
    s.title = PCT(v);
    host.append(s);
  });
}

/* --- os dois planos --- */
function planos(perfil, a, b) {
  const host = $("planos");
  host.innerHTML = "";
  [["adequar", a], ["adaptar", b]].forEach(([chave, m]) => {
    const d = el("button", "plano");
    d.type = "button";
    d.setAttribute("aria-pressed", "false");
    d.append(
      el("h3", null, m.path_label),
      el("div", "custo num", BRL(m.transition_total_brl) +
        "<small>" + (m.tax_is_complete ? "custo total" : "custo já calculado") + " · " +
        (m.transition_cost_pct < 0.0001 ? "menos de 0,01%" : PCT(m.transition_cost_pct, 2)) +
        " do patrimônio</small>"),
      el("dl", null,
        "<dt>Movimenta</dt><dd class='num'>" + BRL(m.turnover_brl) + "</dd>" +
        "<dt>Imposto</dt><dd class='num'>" + BRL(m.transition_tax_brl) + "</dd>"));
    // Em vez de um "a partir de" que ninguém decifra, a falta é dita por
    // extenso: o que falta, de quanto é, e por quê.
    if (!m.tax_is_complete) {
      d.append(el("div", "falta",
        "<b>Ainda falta o imposto de " + m.positions_without_cost_basis.map(p => p.ticker).join(", ") +
        // Sem "e só aumenta": um ganho eleva o imposto, um prejuízo abate o das
      // outras vendas da mesma cesta. Só dá para afirmar a direção quem sabe o
      // custo, que é justamente o que falta.
      "</b>" + BRL(m.unpriced_sale_brl) + " vão ser vendidos e a B3 não informou por quanto " +
        "você comprou. Esse imposto entra na conta quando você informar o valor."));
    }
    d.append(el("div", "selo " + (m.track_record_applies ? "" : "nao"),
      m.track_record_applies
        ? "O resultado que publicamos foi medido nesta carteira"
        : "O resultado que publicamos NÃO foi medido nesta carteira"));
    d.onclick = () => {
      host.querySelectorAll(".plano").forEach(x => x.setAttribute("aria-pressed", "false"));
      d.setAttribute("aria-pressed", "true");
      planoAtual = chave;
      razao(perfil, chave, true);
    };
    host.append(d);
    if (planoAtual === chave) { d.setAttribute("aria-pressed", "true"); razao(perfil, chave, false); }
  });
}

/* --- o que muda no plano escolhido --- */
// O que a tela entrega ao gerador do dossiê: respostas, custos declarados e a
// escolha. Nenhum número atravessa, o gerador refaz as contas com o mesmo
// módulo, e é isso que impede o PDF de discordar da tela por acidente.
function registroDaDecisao(perfil, chave) {
  const respostasBrutas = {};
  escolha.forEach(q => { respostasBrutas[q.key] = respostas[q.key].value; });
  return {
    schema: "benevente_plan_record_v1",
    decided_at: new Date().toISOString(),
    client: "",
    answers: respostasBrutas,
    profile: perfil,
    declared_costs: Object.fromEntries(
      Object.entries(custosInformados).map(([t, v]) => [t, Math.round(v * 100) / 100])),
    chosen_path: chave,
  };
}

function razao(perfil, chave, rolar) {
  const m = resolvido(DADOS.profiles[perfil][chave]);
  const outro = resolvido(DADOS.profiles[perfil][chave === "adequar" ? "adaptar" : "adequar"]);
  mostra("razao-sec");
  etapa(3);
  $("razao-h").textContent = m.path_label;
  $("razao-lede").textContent = m.honesty;

  const grupos = [["vender", "Sai"], ["reduzir", "Reduz"], ["comprar", "Entra"], ["manter", "Fica"]];
  const host = $("razao");
  host.innerHTML = "";
  const plural = { vender: "saem", reduzir: "diminuem", comprar: "entram", manter: "ficam" };
  const contagem = grupos
    .map(([a]) => [plural[a], m.moves.filter(x => x.action === a).length])
    .filter(([, n]) => n > 0);
  $("razao-resumo").innerHTML = "<b>" + contagem.reduce((s, [, n]) => s + n, 0) +
    " ativos</b> · " + contagem.map(([rot, n]) => n + " " + rot).join(", ");
  grupos.forEach(([acao, titulo]) => {
    const linhas = m.moves.filter(x => x.action === acao);
    if (!linhas.length) return;
    host.append(el("p", "grupo", titulo + " · " + linhas.length));
    linhas.forEach(x => {
      const r = el("div", "linha");
      const delta = x.delta_brl;
      r.append(
        el("b", null, x.ticker),
        el("div", "val num" + (delta < 0 ? " neg" : ""),
          (delta === 0 ? BRL(x.from_brl) : (delta > 0 ? "+" : "−") + BRL(Math.abs(delta))) +
          "<small>" + BRL(x.from_brl) + " para " + BRL(x.to_brl) + "</small>"),
        // O motivo primeiro: é ele que responde "por que essa linha existe". A
        // nota vem depois porque é consequência, não causa.
        el("div", "porque", x.reason + (x.notes && x.notes.length ? " · " + x.notes[0] : "")));
      host.append(r);
    });
  });

  const conta = $("conta");
  let html = "<div><span>Execução</span><span class='num'>" +
    BRL(m.transition_cost_brl) + "</span></div>";
  Object.entries(m.tax_by_bucket).forEach(([cesta, d]) => {
    const nome = { renda_variavel: "Ações e fundos", renda_fixa: "Renda fixa",
                   fora_do_escopo: "Fora da estratégia" }[cesta] || cesta;
    // Prejuízo não é base de imposto, é crédito, mas só dentro da própria
    // cesta. O prejuízo de cripto não abate imposto de ação, e prometer isso
    // aqui contradiria a regra que o módulo implementa três telas atrás.
    const rotulo = d.realised_gain_brl >= 0
      ? nome + " · imposto sobre " + BRL(d.realised_gain_brl) + " de ganho"
      : cesta === "fora_do_escopo"
        ? nome + " · prejuízo de " + BRL(-d.realised_gain_brl) + ", que se apura à parte"
        : nome + " · prejuízo de " + BRL(-d.realised_gain_brl) + ", que vira crédito neste tipo";
    html += "<div><span>" + rotulo + "</span><span class='num'>" + BRL(d.tax_brl) + "</span></div>";
  });
  if (!m.tax_is_complete) {
    html += "<div><span class='neg'>Imposto de " +
      m.positions_without_cost_basis.map(p => p.ticker).join(", ") + ", sobre " +
      BRL(m.unpriced_sale_brl) + " vendidos</span>" +
      "<span class='num neg'>ainda sem calcular</span></div>";
  }
  html += "<div class='total'><span>" +
    (m.tax_is_complete ? "Total, pago uma vez" : "Calculado até aqui, pago uma vez") +
    "</span><span class='num'>" + BRL(m.transition_total_brl) + "</span></div>";
  html += "<p>Ganho e prejuízo se compensam dentro do mesmo tipo de investimento, nunca " +
    "entre tipos." +
    (m.exempt_month_assumed && (m.tax_by_bucket.renda_variavel || {}).realised_gain_brl > 0
      ? " Ações ficam em zero pela isenção de R$ 20 mil no mês. Outra venda no mesmo mês " +
        "derruba a isenção."
      : "") +
    (m.tax_by_bucket.fora_do_escopo
      ? " O zero em Fora da estratégia não é isenção, é conta que não fazemos aqui, " +
        "porque cripto tem regras próprias."
      : "") +
    " O outro plano custaria " + BRL(outro.transition_total_brl) + ".</p>";
  conta.innerHTML = html;

  const caixa = $("registro");
  caixa.classList.add("hidden");
  $("gerar").onclick = () => {
    // O visualizador bloqueia download iniciado pela página, então o protótipo
    // mostra o que seria enviado em vez de fingir um arquivo que não desce.
    caixa.classList.remove("hidden");
    caixa.innerHTML = "";
    const texto = el("p", null,
      "Este é o registro da sua decisão. No app ele vai para o servidor, que " +
      "refaz as contas e devolve o PDF assinável. Aqui ele aparece para você ver " +
      "o que seria enviado: só respostas e escolhas, nenhum número calculado.");
    const pre = el("pre");
    pre.textContent = JSON.stringify(registroDaDecisao(perfil, chave), null, 2);
    caixa.append(texto, pre);
    rolaPara(caixa, "nearest");
  };

  alertas(perfil, chave);
  acompanhar(perfil);
  if (rolar) rolaPara($("razao-sec"), "start");
}

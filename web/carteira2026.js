// A carteira do ano corrente na home. Lê os documentos que o monitor diário
// publica, um por perfil, e mostra o que cada livro carrega e quanto rendeu
// desde a decisão de janeiro. Não recalcula nada: se o número aqui divergir do
// arquivo, é o arquivo que manda.
(() => {
  const host = document.querySelector("#carteira-2026-cards");
  if (!host) return;
  const note = document.querySelector("#carteira-2026-note");
  const LABELS = { conservador: "Conservador", equilibrado: "Equilibrado", arrojado: "Arrojado" };
  const pct = (v, d = 2) => `${(v * 100).toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d })}%`;
  const escapeHtml = value => String(value).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const dateBr = iso => iso ? iso.split("-").reverse().join("/") : "—";

  // O que a pessoa vê ao abrir a carteira: cada posição com o seu peso, o
  // motivo pelo qual ela está ali, e a lista do que a camada de proteção mudou
  // no ano, com a data e o limite que foi cruzado.
  //
  // O motivo da seleção é o mesmo para todas as ações, então aparece uma vez
  // embaixo da tabela em vez de repetido em treze linhas.
  // A linha de divisão do cartão. Ela mostrava sempre os pesos de janeiro, e
  // depois que a camada de proteção dispara isso deixa de ser a carteira atual.
  const divisao = (perfil, livro, mudancas) => {
    const m = mudancas && mudancas.profiles ? mudancas.profiles[perfil] : null;
    if (!m || !m.now) {
      const br = livro.holdings.filter(h => h.ticker !== "IVVB11")
        .reduce((s, h) => s + h.weight, 0);
      const gl = livro.holdings.filter(h => h.ticker === "IVVB11")
        .reduce((s, h) => s + h.weight, 0);
      return `<p class="carteira-2026-split">Em janeiro: ações ${pct(br, 0)} ·
        S&amp;P 500 ${pct(gl, 0)} · CDI ${pct(livro.cdi_weight, 0)}</p>`;
    }
    const n = m.now;
    const rotulo = n.factor === 1 ? "Hoje, como em janeiro" : "Hoje";
    return `<p class="carteira-2026-split">${rotulo}: ações ${pct(n.equity_br, 0)} ·
      S&amp;P 500 ${pct(n.global, 0)} · CDI ${pct(n.cdi, 0)}</p>`;
  };

  const detalhe = (perfil, livro, mudancas) => {
    const m = mudancas && mudancas.profiles ? mudancas.profiles[perfil] : null;
    const ano = mudancas ? mudancas.year : "";
    const agora = m ? m.now : null;
    // Sem o arquivo de mudanças não dá para dizer o peso de hoje. Nesse caso a
    // tabela mostra só janeiro e diz que é janeiro, em vez de deixar o leitor
    // supor que está vendo a posição atual.
    const mudou = agora ? agora.factor !== 1 : false;
    const hoje = agora
      ? Object.fromEntries(agora.holdings.map(h => [h.ticker, h.now]))
      : null;

    const linhas = livro.holdings.map(h => `<tr>
      <td>${escapeHtml(h.ticker)}</td>
      ${mudou ? `<td class="num c26-antes">${pct(h.weight, 1)}</td>` : ""}
      <td class="num">${pct(hoje ? hoje[h.ticker] : h.weight, 1)}</td>
      <td class="num">${h.score == null ? "—" : h.score.toFixed(2)}</td></tr>`).join("");

    const rodape = agora ? `<tr class="c26-total">
      <td>CDI</td>
      ${mudou ? `<td class="num c26-antes">${pct(agora.cdi_january, 1)}</td>` : ""}
      <td class="num">${pct(agora.cdi, 1)}</td><td></td></tr>` : "";

    const cabecalho = mudou
      ? `<tr><th>Ativo</th><th class="num">Janeiro</th><th class="num">Hoje</th>
         <th class="num">Nota</th></tr>`
      : `<tr><th>Ativo</th><th class="num">Peso</th><th class="num">Nota</th></tr>`;

    const motivos = [...new Set(livro.holdings.map(h => h.why))]
      .map(x => `<p class="c26-motivo">${escapeHtml(x)}</p>`).join("");

    let historico;
    if (!m) {
      historico = `<p class="c26-motivo">O histórico de mudanças não pôde ser carregado,
        então os pesos acima são os de janeiro.</p>`;
    } else if (!m.changes.length) {
      historico = `<p class="c26-motivo">Nada mudou desde a decisão de janeiro. A carteira
        não é rebalanceada durante o ano, e a camada de proteção não foi acionada.</p>`;
    } else {
      historico = m.changes.map(c => `<div class="c26-evento">
        <p><b>${dateBr(c.date)}</b> · ${escapeHtml(c.why)}, no fechamento de
        ${dateBr(c.observed_on)}. Cada ação passou a valer
        <b>${(c.factor * 100).toFixed(0)}%</b> do peso de janeiro, a mesma proporção para
        todas. A perna global não se mexeu, porque o sinal é do mercado brasileiro. A
        ordem entra no pregão seguinte, que é quando dá para negociar o que o fechamento
        mostrou.</p>
        ${c.holdings ? `<table class="c26-tab"><thead><tr><th>Ativo</th>
          <th class="num">Antes</th><th class="num">Depois</th>
          <th class="num">Variação</th></tr></thead><tbody>${c.holdings.map(h => {
            const d = h.after - h.before;
            const classe = h.ticker === "CDI" ? " c26-total" : "";
            return `<tr class="${classe.trim()}"><td>${escapeHtml(h.ticker)}</td>
              <td class="num c26-antes">${pct(h.before, 2)}</td>
              <td class="num">${pct(h.after, 2)}</td>
              <td class="num ${d < 0 ? "c26-baixa" : d > 0 ? "c26-alta" : ""}">${
                Math.abs(d) < 5e-5 ? "sem mudança"
                : (d > 0 ? "+" : "−") + pct(Math.abs(d), 2)}</td></tr>`;
          }).join("")}</tbody></table>` : ""}
      </div>`).join("");
    }

    const titulo = mudou
      ? `Composição de hoje, ao lado da de janeiro`
      : `Composição`;

    return `<details class="c26-det">
      <summary>Abrir a carteira</summary>
      <div class="c26-corpo">
        <p class="c26-titulo">${titulo}</p>
        <table class="c26-tab"><thead>${cabecalho}</thead>
          <tbody>${linhas}${rodape}</tbody></table>
        <p class="c26-titulo">Por que estes</p>
        ${motivos}
        <p class="c26-titulo">O que mudou em ${ano}</p>
        ${historico}
      </div>
    </details>`;
  };

  const load = async name => {
    const response = await fetch(`./${name}`, { cache: "no-store" });
    if (!response.ok) throw new Error(name);
    return response.json();
  };

  // O resumo diário já traz retorno e data de cada perfil em 1,3 KB. Buscar as
  // séries completas para mostrar três números custava 249 KB, quase metade do
  // peso da página, e nenhum deles aparecia na tela.
  Promise.all([
    load("live_profiles_2026.json"),
    ...Object.keys(LABELS).map(p => load(`current_decision_2026_${p}.json`)),
    // As mudanças vêm de um arquivo próprio, de um kilobyte. A série diária que
    // as contém tem 249 KB por perfil, e a página precisa só dos dias em que
    // alguma coisa mudou.
    load("mudancas_2026.json").catch(() => null),
  ]).then(([summary, ...rest]) => {
    const mudancas = rest.pop();
    const perfis = Object.keys(LABELS);
    const live = summary.profiles;
    const books = Object.fromEntries(perfis.map((p, i) => [p, rest[i]]));

    host.innerHTML = `<div class="carteira-2026-grid">${perfis.map(p => {
      const l = live[p], b = books[p];
      const acoes = b.holdings.filter(h => h.ticker !== "IVVB11");
      const retorno = l.portfolio_return;
      const nomes = acoes.map(h => escapeHtml(h.ticker)).join(" · ");
      return `<article class="carteira-2026-card">
        <header><b>${LABELS[p]}</b><small>teto de ${pct(b.declared.maximum_equity_weight, 0)} em ações · ${acoes.length} emissores</small></header>
        <strong class="${retorno >= 0 ? "up" : "down"}">${retorno >= 0 ? "+" : ""}${pct(retorno)}</strong>
        <span class="carteira-2026-since">desde ${dateBr(b.decision_date)} · até ${dateBr(l.through)}</span>
        <p class="carteira-2026-names">${nomes}</p>
        ${divisao(p, b, mudancas)}
        ${detalhe(p, b, mudancas)}
      </article>`;
    }).join("")}</div>`;

    if (note) {
      // Quatro frases curtas no lugar de um bloco só. O bloco anterior tinha
      // aposto, dois pontos e oração encaixada na mesma sentença, e numa coluna
      // estreita virava parede de texto.
      note.textContent = `Decisão de ${dateBr(summary.decision_date)}, `
        + `congelada por ${summary.approved_by}. O retorno é parcial e usa o preço de `
        + `fechamento da B3. Não ajusta proventos, então subestima quem pagou dividendos. `
        + `Este ano é reconstrução acompanhada. A validação prospectiva começa no primeiro `
        + `pregão de 2027.`;
    }
  }).catch(() => {
    host.innerHTML = `<p class="carteira-2026-names">O acompanhamento de 2026 não pôde ser carregado agora.</p>`;
  });
})();

// Esperado contra realizado, no ano que está correndo.
//
// A faixa foi calculada em janeiro, com dados anteriores ao primeiro pregão de
// 2026, e não se mexe mais. O que anda é a linha do realizado, que o
// acompanhamento diário reescreve. As duas metades vêm de forecast_2026.json,
// que junta as duas sem recalcular nenhuma.
//
// A comparação é por pregão decorrido, não por data. Em agosto o realizado é
// comparado com a faixa de agosto: comparar meio ano com a faixa do ano inteiro
// faria a carteira parecer atrasada só porque o ano não acabou.
(() => {
  const host = document.querySelector("#forecast-2026");
  if (!host) return;
  const NOMES = { conservador: "Conservador", equilibrado: "Equilibrado", arrojado: "Arrojado" };
  const pct = (v, d = 2) => `${v >= 0 ? "+" : ""}${(v * 100).toLocaleString("pt-BR",
    { minimumFractionDigits: d, maximumFractionDigits: d })}%`;
  const esc = v => String(v).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const dataBr = iso => iso ? iso.split("-").reverse().join("/") : "";

  const desenho = (bandBruta, realised) => {
  // No primeiro pregão o retorno acumulado é zero por definição, e a faixa tem
  // largura zero junto. Sem esse ponto o desenho começa no pregão cinco e a
  // linha aparece solta à esquerda da área, como se estivesse fora dela.
    const band = [{ sessions: 0, p10: 0, p50: 0, p90: 0 }].concat(bandBruta);
    const W = 460, H = 150, T = 10, B = 20, L = 4, R = 4;
    const maxS = band[band.length - 1].sessions;
    const baixo = Math.min(...band.map(p => p.p10), ...realised.map(p => p.r));
    const alto = Math.max(...band.map(p => p.p90), ...realised.map(p => p.r));
    const folga = (alto - baixo) * 0.08 || 0.01;
    const min = baixo - folga, max = alto + folga;
    const x = s => L + (W - L - R) * (s / maxS);
    const y = v => T + (H - T - B) * (1 - (v - min) / (max - min));

    // A faixa é uma área só: o contorno de cima ida, o de baixo volta.
    const area = band.map(p => `${x(p.sessions)},${y(p.p90)}`).join(" ") + " " +
      band.slice().reverse().map(p => `${x(p.sessions)},${y(p.p10)}`).join(" ");
    const linha = realised.map(p => `${x(p.sessions)},${y(p.r)}`).join(" ");
    const fim = realised[realised.length - 1];

    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="A faixa projetada em
      janeiro de 2026 e o retorno acumulado até agora, por pregão decorrido.">
      <polygon points="${area}" fill="var(--acao-fraco)"/>
      <polyline points="${linha}" fill="none" stroke="var(--acao)" stroke-width="2"
        stroke-linejoin="round" stroke-linecap="round"/>
      <circle cx="${x(fim.sessions)}" cy="${y(fim.r)}" r="4" fill="var(--acao)"
        stroke="var(--canvas)" stroke-width="2"/>
      <text x="${x(0)}" y="${H - 6}" font-size="9" fill="var(--fg-2)">janeiro</text>
      <text x="${x(maxS)}" y="${H - 6}" font-size="9" fill="var(--fg-2)"
        text-anchor="end">fim do ano</text>
    </svg>`;
  };

  fetch("./forecast_2026.json", { cache: "no-store" })
    .then(r => { if (!r.ok) throw new Error("indisponível"); return r.json(); })
    .then(dados => {
      host.innerHTML = Object.keys(NOMES).map(perfil => {
        const p = dados.profiles[perfil];
        if (!p) return "";
        const n = p.now;
        return `<article class="fc-perfil">
          <h3>${NOMES[perfil]}</h3>
          <p>Em <b>${n.sessions} pregões</b> de 2026, o resultado é
             <b>${pct(n.realised)}</b>. A faixa projetada em janeiro para este
             ponto do ano vai de <b>${pct(n.p10)}</b> a <b>${pct(n.p90)}</b>.
             ${n.inside ? "Está dentro dela." : "Está fora dela."}</p>
          <figure class="fc-fig">${desenho(p.band, p.realised)}
            <figcaption>A faixa foi calculada em janeiro e não muda. A linha é o
              retorno acumulado, até ${esc(dataBr(n.date))}.</figcaption>
          </figure>
        </article>`;
      }).join("");
      const nota = document.querySelector("#forecast-2026-note");
      if (nota) nota.textContent = dados.limitation;
    })
    .catch(() => {
      host.innerHTML = `<p>A comparação de 2026 não pôde ser carregada agora.</p>`;
    });
})();

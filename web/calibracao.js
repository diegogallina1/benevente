/* Esperado contra realizado: o quanto a régua erra.
 *
 * Esta seção existe para publicar um número desfavorável. Todo janeiro a regra
 * projeta uma faixa de 80% para os doze meses seguintes, com apenas o que se
 * sabia até aquele dia; depois o ano acontece e cai dentro ou fora. O que se
 * publica é a contagem e o viés, nunca uma projeção de patrimônio.
 *
 * Os dados vêm de calibracao.json, gerado do artefato pela ferramenta
 * build_calibration_web.py. Nenhum número é escrito à mão aqui.
 */
(async function () {
  const host = document.querySelector("[data-calibracao]");
  if (!host) return;

  const pct = (v, casas = 1) => (v * 100).toFixed(casas).replace(".", ",") + "%";
  const el = (tag, cls, html) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html !== undefined) n.innerHTML = html;
    return n;
  };

  let dados;
  try {
    const resposta = await fetch("./calibracao.json", { cache: "no-store" });
    if (!resposta.ok) throw new Error(resposta.status);
    dados = await resposta.json();
  } catch (erro) {
    host.textContent = "A calibração não pôde ser carregada.";
    return;
  }

  // A ordem vem do próprio artefato, que já sai da política do degrau mais
  // apertado ao mais solto. Escrita à mão aqui ela tinha três nomes, e o
  // "if (!r) return" logo abaixo fazia o quarto degrau sumir sem erro nenhum:
  // a página carregava a calibração dele e não desenhava.
  const ordem = Object.keys(dados.profiles);
  ordem.forEach(perfil => {
    const r = dados.profiles[perfil];
    if (!r) return;
    const bloco = el("div", "calib-perfil");
    const vies = r.median_bias_pp;
    const otimista = vies < -0.5;
    bloco.append(el("h3", null, perfil[0].toUpperCase() + perfil.slice(1)));
    bloco.append(el("p", null,
      "Em <b>" + r.total + " anos</b>, o resultado caiu dentro da faixa projetada em <b>" +
      r.inside + "</b>. " + (otimista
        ? "O meio da faixa ficou <b>" + Math.abs(vies).toFixed(1).replace(".", ",") +
          " pontos otimista por ano</b>."
        : (vies > 0.5
            ? "O meio da faixa ficou " + vies.toFixed(1).replace(".", ",") +
              " pontos abaixo do que aconteceu."
            : "O meio da faixa não puxou para lado nenhum de forma perceptível."))));
    bloco.append(grafico(r.years));
    host.append(bloco);
  });

  // A limitação vem do artefato, que agora deriva os números da amostra. Repetir
  // a contagem aqui produziria dois "erro padrão de X" no mesmo parágrafo, foi
  // o que aconteceu quando o texto do artefato ainda estava escrito à mão.
  host.append(el("p", "calib-nota",
    "<b>Acertar seis ou acertar oito não se distingue de sorte.</b> " + dados.limitation));

  function grafico(anos) {
    const L = 8, R = 8, T = 12, B = 22, W = 340, H = 132;
    const baixo = Math.min(...anos.map(a => Math.min(a.p10, a.realised)));
    const alto = Math.max(...anos.map(a => Math.max(a.p90, a.realised)));
    const folga = (alto - baixo) * 0.08;
    const min = baixo - folga, max = alto + folga;
    const y = v => T + (H - T - B) * (1 - (v - min) / (max - min));
    const passo = (W - L - R) / anos.length;

    const partes = ["<svg viewBox='0 0 " + W + " " + H + "' role='img' aria-label='" +
      "Para cada ano, a faixa de oitenta por cento projetada em janeiro e o retorno que " +
      "de fato aconteceu.'>"];
    anos.forEach((a, i) => {
      const cx = L + passo * (i + 0.5);
      // A faixa e so uma faixa: o eixo, a linha do zero e o traco da mediana
      // sairam porque o grafico responde uma pergunta unica, o resultado caiu
      // dentro do que foi projetado?, e nenhum dos tres ajudava a responder.
      partes.push("<line x1='" + cx + "' x2='" + cx + "' y1='" + y(a.p10) + "' y2='" + y(a.p90) +
        "' class='calib-faixa'/>");
      // O anel na cor do fundo separa o ponto da barra: sem ele o marcador some
      // justamente quando cai dentro da faixa, que é o caso comum.
      partes.push("<circle cx='" + cx + "' cy='" + y(a.realised) + "' r='4' class='" +
        (a.inside ? "calib-dentro" : "calib-fora") + "'/>");
      partes.push("<text x='" + cx + "' y='" + (H - 6) + "' text-anchor='middle' " +
        "class='calib-eixo'>" + String(a.year).slice(2) + "</text>");
    });
    partes.push("</svg>");

    const fig = el("figure", "calib-fig");
    fig.innerHTML = partes.join("") +
      "<figcaption>Cada faixa é o que foi projetado em janeiro daquele ano. O ponto é o " +
      "retorno que aconteceu: dentro da faixa ou fora dela.</figcaption>";
    return fig;
  }
})();

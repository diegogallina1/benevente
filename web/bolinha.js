/* Um halo verde que segue o ponteiro.
 *
 * Ele persegue o mouse com atraso, nao colado nele: colado vira um cursor
 * alternativo e atrapalha a leitura. Fica atras de todo o conteudo, nao recebe
 * clique e nao entra na arvore de acessibilidade.
 *
 * Sai de cena em duas situacoes, e as duas importam: tela de toque, onde nao
 * existe ponteiro para seguir, e sistema com movimento reduzido pedido, porque
 * um elemento que persegue o cursor e exatamente o tipo de movimento que a
 * pessoa desligou.
 */
(function () {
  if (!window.matchMedia) return;
  if (matchMedia("(hover: none)").matches) return;
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  var alvo = document.createElement("div");
  alvo.id = "bolinha";
  alvo.setAttribute("aria-hidden", "true");
  (document.body || document.documentElement).appendChild(alvo);

  // Destino e posicao desenhada. A distancia entre as duas e o atraso.
  var mx = innerWidth / 2, my = innerHeight / 2, x = mx, y = my, ligada = false;

  addEventListener("pointermove", function (e) {
    mx = e.clientX; my = e.clientY;
    if (!ligada) { x = mx; y = my; ligada = true; alvo.style.opacity = "1"; }
  }, { passive: true });
  addEventListener("pointerleave", function () { alvo.style.opacity = "0"; });

  (function quadro() {
    x += (mx - x) * 0.14;
    y += (my - y) * 0.14;
    alvo.style.transform = "translate3d(" + x.toFixed(1) + "px," + y.toFixed(1) + "px,0)";
    requestAnimationFrame(quadro);
  })();
})();

/* Alternador de tema, injetado por script.
 *
 * O escuro e o padrao porque o design system e escuro por definicao: a
 * preferencia do sistema nao e consultada. A escolha do visitante fica guardada.
 *
 * O botao nao e escrito no HTML de cada pagina porque sao varias e uma seria
 * esquecida.
 */
(function () {
  var CHAVE = "benevente-tema";

  function aplica(valor) {
    var claro = valor === "light";
    if (claro) document.documentElement.setAttribute("data-theme", "light");
    else document.documentElement.removeAttribute("data-theme");
    var b = document.querySelector(".tema-toggle");
    if (b) {
      b.textContent = claro ? "\u2600 Claro" : "\u263E Escuro";
      b.setAttribute("aria-pressed", String(!claro));
      b.setAttribute("aria-label", claro
        ? "Tema claro; alternar para escuro" : "Tema escuro; alternar para claro");
    }
  }

  var guardado = null;
  try { guardado = localStorage.getItem(CHAVE); } catch (e) { /* janela anonima */ }
  aplica(guardado === "light" ? "light" : "dark");

  function monta() {
    var nav = document.querySelector("header nav, .nav nav, nav");
    if (!nav || document.querySelector(".tema-toggle")) return;
    var b = document.createElement("button");
    b.type = "button";
    b.className = "tema-toggle";
    b.onclick = function () {
      var novo = document.documentElement.getAttribute("data-theme") === "light"
        ? "dark" : "light";
      aplica(novo);
      try { localStorage.setItem(CHAVE, novo); } catch (e) { /* segue sem salvar */ }
    };
    nav.appendChild(b);
    aplica(document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark");
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", monta);
  else monta();
})();

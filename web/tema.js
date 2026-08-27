/* Alternador de tema, injetado por script.
 *
 * O claro e o padrao, e por isso ele e o :root do tokens.css: quando ninguem
 * escolheu nada, nenhum atributo e carimbado e a pagina abre no tema que o
 * :root descreve. A preferencia do sistema nao e consultada, para que o estado
 * sem escolha seja um so. O escuro e escolha explicita e fica guardada.
 *
 * Inverter isso foi o conserto de um defeito real: enquanto o escuro era o
 * :root, qualquer regra antiga que trouxesse cor literal em vez de token ficava
 * com a cor do escuro no tema claro — texto que somia no fundo e borda preta em
 * volta de cartao branco. Com o claro no :root, uma regra esquecida erra para
 * o lado do tema que quase todo mundo ve.
 *
 * O botao nao e escrito no HTML de cada pagina porque sao varias e uma seria
 * esquecida.
 */
(function () {
  var CHAVE = "benevente-tema";

  function escuroAtivo() {
    return document.documentElement.getAttribute("data-theme") === "dark";
  }

  function aplica(valor) {
    var escuro = valor === "dark";
    if (escuro) document.documentElement.setAttribute("data-theme", "dark");
    else document.documentElement.removeAttribute("data-theme");
    var b = document.querySelector(".tema-toggle");
    if (b) {
      b.textContent = escuro ? "☾ Escuro" : "☀ Claro";
      b.setAttribute("aria-pressed", String(escuro));
      b.setAttribute("aria-label", escuro
        ? "Tema escuro; alternar para claro" : "Tema claro; alternar para escuro");
    }
  }

  var guardado = null;
  try { guardado = localStorage.getItem(CHAVE); } catch (e) { /* janela anonima */ }
  aplica(guardado === "dark" ? "dark" : "light");

  function monta() {
    var nav = document.querySelector("header nav, .nav nav, nav");
    if (!nav || document.querySelector(".tema-toggle")) return;
    var b = document.createElement("button");
    b.type = "button";
    b.className = "tema-toggle";
    b.onclick = function () {
      var novo = escuroAtivo() ? "light" : "dark";
      aplica(novo);
      try { localStorage.setItem(CHAVE, novo); } catch (e) { /* segue sem salvar */ }
    };
    nav.appendChild(b);
    aplica(escuroAtivo() ? "dark" : "light");
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", monta);
  else monta();
})();

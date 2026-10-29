// Lightbox + before/after compare for clinical photos (images come from the authorized /arquivos/foto/ view).
(function () {
  "use strict";
  var box;
  function open(src, caption) {
    if (!box) {
      box = document.createElement("div");
      box.className = "fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/85 p-4";
      box.innerHTML = '<img class="max-h-[85vh] max-w-full rounded-lg" alt=""><p class="mt-3 text-sm text-white/80"></p>';
      box.addEventListener("click", function () { box.remove(); box = null; });
    }
    box.querySelector("img").src = src;
    box.querySelector("p").textContent = caption || "";
    document.body.appendChild(box);
  }
  document.addEventListener("click", function (e) {
    var a = e.target.closest("[data-lightbox]");
    if (a) { e.preventDefault(); open(a.getAttribute("href"), a.getAttribute("data-caption")); }
  });
  document.addEventListener("change", function (e) {
    if (!e.target.matches("[data-compare-select]")) return;
    var wrap = e.target.closest("[data-compare]");
    var side = e.target.getAttribute("data-compare-select");
    var img = wrap.querySelector("[data-compare-img='" + side + "']");
    img.src = e.target.value;
    img.classList.toggle("hidden", !e.target.value);
  });
  document.addEventListener("input", function (e) {
    if (!e.target.matches("[data-compare-range]")) return;
    var wrap = e.target.closest("[data-compare]");
    wrap.querySelector("[data-compare-clip]").style.width = e.target.value + "%";
  });
})();

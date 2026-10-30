// wbook — small helpers, no framework.
(function () {
  "use strict";

  // CSRF header for HTMX
  document.addEventListener("htmx:configRequest", function (e) {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    if (m) e.detail.headers["X-CSRFToken"] = m[1];
  });

  // Toasts auto-dismiss
  function toasts(root) {
    (root || document).querySelectorAll("[data-toast]").forEach(function (el) {
      setTimeout(function () { el.style.opacity = "0"; setTimeout(function () { el.remove(); }, 300); }, 6000);
      var x = el.querySelector("[data-toast-close]");
      if (x) x.addEventListener("click", function () { el.remove(); });
    });
  }

  // Mobile sidebar
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-sidebar-toggle]");
    if (t) {
      document.querySelector("[data-sidebar]").classList.toggle("-translate-x-full");
      var o = document.querySelector("[data-sidebar-overlay]");
      if (o) o.classList.toggle("hidden");
    }
    var c = e.target.closest("[data-copy]");
    if (c) {
      e.preventDefault();
      navigator.clipboard.writeText(c.getAttribute("data-copy")).then(function () {
        var old = c.innerHTML;
        c.textContent = c.getAttribute("data-copied") || "✓";
        setTimeout(function () { c.innerHTML = old; }, 1500);
      });
    }
    var d = e.target.closest("[data-dropdown]");
    document.querySelectorAll("[data-dropdown-menu]").forEach(function (m) {
      if (!d || m !== d.parentElement.querySelector("[data-dropdown-menu]")) m.classList.add("hidden");
    });
    if (d) {
      e.preventDefault();
      d.parentElement.querySelector("[data-dropdown-menu]").classList.toggle("hidden");
    }
  });

  // Confirm forms
  document.addEventListener("submit", function (e) {
    var f = e.target;
    if (f.hasAttribute("data-confirm") && !window.confirm(f.getAttribute("data-confirm"))) e.preventDefault();
  });

  // Auto submit
  document.addEventListener("change", function (e) {
    if (e.target.matches("[data-autosubmit]")) e.target.form.submit();
  });

  // Ctrl/Cmd+Enter submits textareas
  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && e.target.matches("textarea[data-submit-shortcut]")) e.target.form.submit();
  });

  // Formsets: add rows from <template>, live total
  function formsets(root) {
    (root || document).querySelectorAll("[data-formset]").forEach(function (box) {
      if (box._wb) return;
      box._wb = true;
      var prefix = box.getAttribute("data-formset");
      var total = document.getElementById("id_" + prefix + "-TOTAL_FORMS");
      var tpl = box.querySelector("template");
      var list = box.querySelector("[data-formset-list]");
      var add = box.querySelector("[data-formset-add]");
      if (add) add.addEventListener("click", function () {
        var n = parseInt(total.value, 10);
        list.insertAdjacentHTML("beforeend", tpl.innerHTML.replace(/__prefix__/g, n));
        total.value = n + 1;
        sum(box);
      });
      box.addEventListener("input", function () { sum(box); });
      sum(box);
    });
  }
  function sum(box) {
    var out = box.querySelector("[data-formset-total]");
    if (!out) return;
    var t = 0;
    box.querySelectorAll("[data-formset-list] > *").forEach(function (row) {
      var del = row.querySelector("input[name$='-DELETE']");
      if (del && del.checked) return;
      var q = parseFloat((row.querySelector("input[name$='-quantity']") || {}).value || "0");
      var a = parseFloat(((row.querySelector("input[name$='-unit_amount']") || {}).value || "0").replace(",", "."));
      if (!isNaN(q) && !isNaN(a)) t += q * a;
    });
    out.textContent = t.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }

  // Password show/hide
  function eyes(root) {
    (root || document).querySelectorAll("input[type=password]:not([data-no-toggle])").forEach(function (inp) {
      if (inp._wbEye) return;
      inp._wbEye = true;
      var wrap = document.createElement("div");
      wrap.className = "relative";
      inp.parentNode.insertBefore(wrap, inp);
      wrap.appendChild(inp);
      inp.classList.add("pr-10");
      var b = document.createElement("button");
      b.type = "button";
      b.className = "absolute inset-y-0 right-0 px-3 text-slate-400 hover:text-slate-600";
      b.setAttribute("aria-label", "Mostrar senha");
      b.innerHTML = "👁";
      b.addEventListener("click", function () { inp.type = inp.type === "password" ? "text" : "password"; });
      wrap.appendChild(b);
    });
  }

  // Absence form: hide the hour fields when "whole days" is ticked
  function absence(root) {
    (root || document).querySelectorAll("[data-absence-allday]").forEach(function (box) {
      var form = box.form;
      function sync() {
        form.querySelectorAll(".absence-time").forEach(function (w) { w.classList.toggle("hidden", box.checked); });
      }
      if (!box._wb) { box._wb = true; box.addEventListener("change", sync); }
      sync();
    });
  }
  document.addEventListener("DOMContentLoaded", function () { absence(); });

  // Slot picker: keep hidden start input in sync
  document.addEventListener("click", function (e) {
    var s = e.target.closest("[data-slot]");
    if (!s) return;
    e.preventDefault();
    var form = document.querySelector(s.getAttribute("data-target") || "[data-booking-form]");
    document.querySelectorAll("[data-slot]").forEach(function (b) { b.classList.remove("slot-btn-selected"); });
    s.classList.add("slot-btn-selected");
    if (form) {
      form.querySelector("input[name=start]").value = s.getAttribute("data-slot");
      var label = form.querySelector("[data-slot-label]");
      if (label) label.textContent = s.getAttribute("data-label");
      form.querySelectorAll("[data-needs-slot]").forEach(function (el) { el.disabled = false; el.classList.remove("hidden"); });
      if (form.hasAttribute("data-scroll")) form.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });

  function init(root) { toasts(root); formsets(root); eyes(root); }
  document.addEventListener("DOMContentLoaded", function () { init(document); });
  document.addEventListener("htmx:afterSwap", function (e) { init(e.target); });
})();

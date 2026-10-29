// Access log beacons for /<slug>/orcamento/<uuid>/ (visible time, scroll depth, PDF/WhatsApp events).
(function () {
  "use strict";
  var el = document.getElementById("quote-tracking");
  if (!el) return;
  var cfg = JSON.parse(el.textContent);
  var visible = 0, since = document.visibilityState === "visible" ? Date.now() : null, maxScroll = 0, sent = {};

  function elapsed() { return Math.round((visible + (since ? Date.now() - since : 0)) / 1000); }
  function scroll() {
    var h = document.documentElement;
    var pct = Math.round(((h.scrollTop + window.innerHeight) / h.scrollHeight) * 100);
    if (pct > maxScroll) maxScroll = Math.min(100, pct);
  }
  function post(url, data) {
    var body = JSON.stringify(data);
    if (navigator.sendBeacon && navigator.sendBeacon(url, new Blob([body], { type: "text/plain" }))) return;
    fetch(url, { method: "POST", body: body, keepalive: true, headers: { "Content-Type": "text/plain" } });
  }
  function beacon() { post(cfg.beacon, { visit: cfg.visit, duration: elapsed(), scroll: maxScroll }); }
  function track(kind) { if (sent[kind]) return; sent[kind] = true; post(cfg.event, { visit: cfg.visit, kind: kind }); }

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") { if (since) { visible += Date.now() - since; since = null; } beacon(); }
    else since = Date.now();
  });
  window.addEventListener("pagehide", beacon);
  window.addEventListener("scroll", scroll, { passive: true });
  scroll();
  setInterval(function () { if (document.visibilityState === "visible") beacon(); }, 15000);

  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-track]");
    if (t) track(t.getAttribute("data-track"));
  });
  var pdf = document.querySelector("[data-track-view='pdf']");
  if (pdf && "IntersectionObserver" in window) {
    new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (en) { if (en.isIntersecting) { track("pdf"); obs.disconnect(); } });
    }, { threshold: 0.3 }).observe(pdf);
  }
})();

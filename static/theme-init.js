/* Pre-paint theme initializer (runs synchronously in <head>, zero FOUC, CSP script-src 'self') */
(function () {
  var theme = "light";
  try {
    var saved = localStorage.getItem("probplots-theme");
    if (saved === "dark" || saved === "light") {
      theme = saved;
    } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      theme = "dark";
    }
  } catch (e) {
    // ignore storage errors
  }
  document.documentElement.setAttribute("data-theme", theme);
})();

/* Synchronous pre-paint theme initializer (CSP script-src 'self', zero FOUC) */
(function () {
  var theme = "light";
  try {
    var saved = localStorage.getItem("p05-theme") || localStorage.getItem("probplots-theme");
    if (saved === "dark" || saved === "light") {
      theme = saved;
    } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      theme = "dark";
    }
  } catch (e) {
    // Ignore storage access errors in private contexts
  }
  document.documentElement.setAttribute("data-theme", theme);
})();

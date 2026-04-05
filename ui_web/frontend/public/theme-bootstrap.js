(function () {
  function reportBootstrapError(message, error) {
    var details = {
      message: error && error.message ? String(error.message) : String(error || ""),
    };

    if (error && error.stack) {
      details.stack = String(error.stack);
    }

    try {
      fetch("/api/debug/frontend-error", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: "theme-bootstrap.js",
          message: message,
          details: details,
        }),
      }).catch(function () {});
    } catch (fetchError) {}
  }

  function reportBootstrapSignal(message, details) {
    try {
      fetch("/api/debug/frontend-error", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: "theme-bootstrap.js",
          message: message,
          details: details || {},
        }),
      }).catch(function () {});
    } catch (fetchError) {}
  }

  window.addEventListener("error", function (event) {
    reportBootstrapError("window.error", event.error || event.message);
  });

  window.addEventListener("unhandledrejection", function (event) {
    reportBootstrapError("window.unhandledrejection", event.reason);
  });

  var storageKey = "zaimanhua-color-scheme";
  var theme = "dark";
  try {
    var saved = window.localStorage.getItem(storageKey);
    if (saved === "light" || saved === "dark") {
      theme = saved;
    }
  } catch (error) {}
  document.documentElement.setAttribute("data-mantine-color-scheme", theme);
  reportBootstrapSignal("bootstrap.loaded", { theme: theme });
})();

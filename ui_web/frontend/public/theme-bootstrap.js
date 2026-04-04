(function () {
  var storageKey = "zaimanhua-color-scheme";
  var theme = "dark";
  try {
    var saved = window.localStorage.getItem(storageKey);
    if (saved === "light" || saved === "dark") {
      theme = saved;
    }
  } catch (error) {}
  document.documentElement.setAttribute("data-mantine-color-scheme", theme);
})();

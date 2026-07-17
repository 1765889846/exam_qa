const KEY = "sz.theme"; // system | light | dark

export function getThemePref() {
  return localStorage.getItem(KEY) || "system";
}

export function resolveTheme(pref = getThemePref()) {
  if (pref === "light" || pref === "dark") return pref;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function applyTheme(pref = getThemePref()) {
  document.documentElement.dataset.theme = resolveTheme(pref);
}

export function setThemePref(pref) {
  localStorage.setItem(KEY, pref);
  applyTheme(pref);
}

export function initTheme() {
  applyTheme();
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", () => {
    if (getThemePref() === "system") applyTheme("system");
  });
}

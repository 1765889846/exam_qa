import { apiGet } from "./api.js";
import { getThemePref, setThemePref, initTheme } from "./theme.js";

const COURSE_KEY = "sz.course_id";
const THEME_ORDER = ["system", "light", "dark"];
const THEME_LABEL = { system: "跟随系统", light: "亮色", dark: "暗色" };

export function getCourseId() {
  return localStorage.getItem(COURSE_KEY) || "";
}

export function setCourseId(id) {
  localStorage.setItem(COURSE_KEY, id);
}

/**
 * Fill a <select> from API items without innerHTML.
 */
function fillSelect(select, items) {
  const frag = document.createDocumentFragment();
  for (const item of items) {
    const value = String(item?.id ?? "");
    const label = String(item?.name ?? value);
    // new Option(text, value) sets text as plain text, not HTML
    frag.appendChild(new Option(label, value));
  }
  select.replaceChildren(frag);
}

function syncThemeButton(btn) {
  if (!btn) return;
  const pref = getThemePref();
  const label = THEME_LABEL[pref] || THEME_LABEL.system;
  btn.textContent = label;
  btn.title = `主题：${label}（点击切换）`;
  btn.setAttribute("aria-label", `主题：${label}`);
}

export async function initShell({ active, catalog = true } = {}) {
  initTheme();
  const root = document.querySelector("[data-sz-shell]");
  if (!root) return;

  const catalogHtml = catalog
    ? `<select id="sz-college" aria-label="学院"></select>
        <select id="sz-course" aria-label="课程"></select>`
    : "";

  root.innerHTML = `
    <header class="sz-topbar">
      <a class="sz-brand" href="/sz/" aria-label="溯知">
        <svg class="sz-brand-mark" viewBox="0 0 32 32" aria-hidden="true">
          <rect x="1.5" y="1.5" width="29" height="29" rx="10" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.35"/>
          <path fill="currentColor" d="M8 22c0-6.2 3.4-10.2 8.2-11.6.4-.1.8.3.7.7-.5 2.1-.3 3.8.7 5.2 1.4 1.9 3.9 2.8 6.4 2.1.4-.1.7.3.5.7C22.8 24.2 18.6 27 13.8 27 10.4 27 8 24.8 8 22Z"/>
          <path fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" d="M11.2 12.2c1.8-2.4 4.2-3.6 7-3.6 1.2 0 2.3.2 3.3.7"/>
          <circle cx="21.5" cy="9.2" r="1.35" fill="currentColor"/>
        </svg>
        <span class="sz-brand-word">溯知</span>
      </a>
      <nav class="sz-nav">
        <a href="/sz/" data-nav="sz" class="${active === "sz" ? "is-active" : ""}">对话</a>
        <a href="/sz-docs/" data-nav="docs" class="${active === "docs" ? "is-active" : ""}">资料</a>
        <a href="/sz-bank/" data-nav="bank" class="${active === "bank" ? "is-active" : ""}">我的题库</a>
        <a href="/sz-cfg/" data-nav="cfg" class="${active === "cfg" ? "is-active" : ""}">设置</a>
      </nav>
      <div class="sz-topbar-right">
        ${catalogHtml}
        <span id="sz-health" class="sz-health" title="health">●</span>
        <button type="button" id="sz-theme" aria-label="主题">主题</button>
      </div>
    </header>
    <div id="sz-toast" class="sz-toast" hidden></div>
  `;

  const themeBtn = document.getElementById("sz-theme");
  syncThemeButton(themeBtn);
  themeBtn.onclick = () => {
    const i = THEME_ORDER.indexOf(getThemePref());
    setThemePref(THEME_ORDER[(i + 1) % THEME_ORDER.length]);
    syncThemeButton(themeBtn);
  };

  const tasks = [refreshHealth()];
  if (catalog) tasks.push(loadCatalog());
  await Promise.all(tasks);
  setInterval(refreshHealth, 15000);
}

async function refreshHealth() {
  const el = document.getElementById("sz-health");
  if (!el) return;
  try {
    const data = await apiGet("/health");
    // data.status: "healthy" | "degraded" | "unavailable"
    if (data?.status === "healthy") {
      el.dataset.state = "ok";
    } else if (data?.status === "degraded") {
      el.dataset.state = "degraded";
    } else {
      el.dataset.state = "down";
    }
    el.title = JSON.stringify(data);
  } catch {
    el.dataset.state = "down";
  }
}

async function loadCatalog() {
  const collegeSel = document.getElementById("sz-college");
  const courseSel = document.getElementById("sz-course");
  if (!collegeSel || !courseSel) return;

  try {
    const collegesData = await apiGet("/colleges");
    const colleges = collegesData?.items || [];
    fillSelect(collegeSel, colleges);

    async function reloadCourses() {
      const coursesData = await apiGet("/courses", {
        college_id: collegeSel.value,
      });
      const list = coursesData?.items || [];
      fillSelect(courseSel, list);
      const saved = getCourseId();
      if (saved && [...courseSel.options].some((o) => o.value === saved)) {
        courseSel.value = saved;
      } else if (courseSel.value) {
        setCourseId(courseSel.value);
      }
    }

    collegeSel.onchange = reloadCourses;
    courseSel.onchange = () => setCourseId(courseSel.value);
    if (colleges.length) await reloadCourses();
  } catch (err) {
    toast(err.message || "加载目录失败", "error");
  }
}

export function toast(msg, kind = "info") {
  const el = document.getElementById("sz-toast");
  if (!el) return;
  el.hidden = false;
  el.dataset.kind = kind;
  el.textContent = msg;
  clearTimeout(el._t);
  el._t = setTimeout(() => {
    el.hidden = true;
  }, 3200);
}

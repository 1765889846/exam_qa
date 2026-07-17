import { apiGet } from "./api.js";
import { getThemePref, setThemePref, initTheme } from "./theme.js";

const COURSE_KEY = "sz.course_id";

export function getCourseId() {
  return localStorage.getItem(COURSE_KEY) || "";
}

export function setCourseId(id) {
  localStorage.setItem(COURSE_KEY, id);
}

export async function initShell({ active }) {
  initTheme();
  const root = document.querySelector("[data-sz-shell]");
  if (!root) return;

  root.innerHTML = `
    <header class="sz-topbar">
      <a class="sz-brand" href="/sz/">溯知</a>
      <nav class="sz-nav">
        <a href="/sz/" data-nav="sz" class="${active === "sz" ? "is-active" : ""}">工作台</a>
        <a href="/sz-cfg/" data-nav="cfg" class="${active === "cfg" ? "is-active" : ""}">设置</a>
      </nav>
      <div class="sz-topbar-right">
        <select id="sz-college" aria-label="学院"></select>
        <select id="sz-course" aria-label="课程"></select>
        <span id="sz-health" class="sz-health" title="health">●</span>
        <button type="button" id="sz-theme" aria-label="主题">主题</button>
      </div>
    </header>
    <div id="sz-toast" class="sz-toast" hidden></div>
  `;

  document.getElementById("sz-theme").onclick = () => {
    const order = ["system", "light", "dark"];
    const i = order.indexOf(getThemePref());
    setThemePref(order[(i + 1) % order.length]);
  };

  await Promise.all([refreshHealth(), loadCatalog()]);
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
    collegeSel.innerHTML = colleges
      .map((c) => `<option value="${c.id}">${c.name || c.id}</option>`)
      .join("");

    async function reloadCourses() {
      const coursesData = await apiGet("/courses", {
        college_id: collegeSel.value,
      });
      const list = coursesData?.items || [];
      courseSel.innerHTML = list
        .map((c) => `<option value="${c.id}">${c.name || c.id}</option>`)
        .join("");
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

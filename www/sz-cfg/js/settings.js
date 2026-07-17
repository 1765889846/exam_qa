import { apiGet, apiPatch, apiPost, apiDelete } from "../../shared/js/api.js";
import { initShell, toast } from "../../shared/js/shell.js";
import { enableColumnResize } from "../../shared/js/resize.js";

const MASKED_SECRET = "***";

const GROUPS = [
  {
    id: "llm",
    title: "LLM",
    fields: [{ key: "timeout", label: "超时（秒）", type: "number" }],
  },
  {
    id: "embedding",
    title: "Embedding",
    fields: [
      {
        key: "provider",
        label: "Provider",
        type: "select",
        options: ["local", "openai"],
      },
      { key: "model", label: "模型" },
      { key: "base_url", label: "Base URL" },
      { key: "api_key", label: "API Key", secret: true },
      { key: "timeout", label: "超时", type: "number" },
    ],
  },
  {
    id: "retrieval",
    title: "检索",
    fields: [
      { key: "top_k", label: "召回条数 (top_k)", type: "number" },
      { key: "score_threshold", label: "分数阈值", type: "number", step: "0.01" },
    ],
  },
  {
    id: "chunk",
    title: "分块",
    fields: [
      { key: "chunk_size", label: "chunk_size", type: "number" },
      { key: "chunk_overlap", label: "overlap", type: "number" },
    ],
  },
  {
    id: "parsing",
    title: "解析 / OCR",
    fields: [
      { key: "pdf_use_ocr", label: "启用 OCR", type: "checkbox" },
      { key: "pdf_force_ocr", label: "强制 OCR", type: "checkbox" },
      { key: "pdf_ocr_language", label: "OCR 语言" },
    ],
  },
  {
    id: "proxy",
    title: "代理",
    fields: [
      { key: "enabled", label: "启用", type: "checkbox" },
      { key: "url", label: "URL" },
      { key: "no_proxy", label: "NO_PROXY" },
    ],
  },
  {
    id: "app",
    title: "上传 / 日志",
    fields: [
      { key: "max_upload_mb", label: "最大上传 MB", type: "number" },
      {
        key: "log_level",
        label: "日志等级",
        type: "select",
        options: ["DEBUG", "INFO", "WARNING", "ERROR"],
      },
    ],
  },
  {
    id: "server",
    title: "服务",
    fields: [
      { key: "host", label: "Host" },
      { key: "port", label: "Port", type: "number" },
    ],
  },
];

const FORMAT_LABEL = {
  openai: "OpenAI 兼容",
  "openai-compatible": "OpenAI 兼容",
  local: "本地（Ollama 等）",
};

let cfg = null;
let activeId = GROUPS[0].id;
let filter = "";

const navEl = document.getElementById("sz-config-nav");
const mainEl = document.getElementById("sz-config-main");

async function boot() {
  await initShell({ active: "cfg", catalog: false });
  enableColumnResize({
    root: document.getElementById("sz-config"),
    cssVar: "--sz-cfg-nav-width",
    storageKey: "sz.cfg_nav_width",
    min: 160,
    max: 360,
    defaultWidth: 220,
  });
  await load();
}

boot().catch((err) => {
  console.error(err);
  if (mainEl) {
    mainEl.textContent = err?.message || "页面初始化失败";
  }
});

async function load() {
  try {
    cfg = await apiGet("/config");
    renderNav();
    renderMain();
  } catch (err) {
    toast(err.message || "加载配置失败", "error");
    if (navEl) {
      navEl.replaceChildren();
      const p = document.createElement("p");
      p.className = "sz-muted";
      p.textContent = err.message || "加载失败";
      navEl.appendChild(p);
    }
  }
}

function renderNav() {
  const q = filter.trim().toLowerCase();
  const items = GROUPS.filter(
    (g) =>
      !q ||
      g.id.includes(q) ||
      g.title.toLowerCase().includes(q) ||
      g.fields.some((f) => f.key.includes(q) || f.label.toLowerCase().includes(q)),
  );

  navEl.innerHTML = `
    <label class="sz-config-search">
      <span class="sz-sr-only">搜索分组</span>
      <input type="search" id="sz-config-filter" placeholder="搜索分组…" value="${esc(filter)}" />
    </label>
    <ul class="sz-config-list" role="listbox" aria-label="配置分组">
      ${items
        .map(
          (g) => `
        <li>
          <button type="button" class="sz-config-item${g.id === activeId ? " is-active" : ""}" data-group="${g.id}">
            <span class="sz-config-item-title">${esc(g.title)}</span>
            <span class="sz-config-item-id">${esc(g.id)}</span>
          </button>
        </li>`,
        )
        .join("")}
      ${items.length ? "" : `<li class="sz-muted">无匹配分组</li>`}
    </ul>
    <div class="sz-config-meta" id="sz-config-meta-nav"></div>
  `;

  renderMeta(document.getElementById("sz-config-meta-nav"));

  document.getElementById("sz-config-filter").oninput = (e) => {
    filter = e.target.value;
    renderNav();
  };

  navEl.querySelectorAll("[data-group]").forEach((btn) => {
    btn.onclick = () => {
      activeId = btn.dataset.group;
      renderNav();
      renderMain();
    };
  });
}

function renderMeta(el) {
  if (!el || !cfg) return;
  const storage = cfg.storage || {};
  const meta = cfg.meta || {};
  const writable = meta.env_writable;
  el.innerHTML = `
    <h3 class="sz-config-meta-title">只读信息</h3>
    <dl class="sz-config-meta-dl">
      <dt>knowledge_dir</dt>
      <dd>${esc(storage.knowledge_dir ?? "—")}</dd>
      <dt>config_path</dt>
      <dd>${esc(meta.config_path ?? "—")}</dd>
      <dt>env_writable</dt>
      <dd class="${writable ? "" : "sz-warn"}">${writable ? "是" : "否（只读）"}</dd>
    </dl>
  `;
}

function renderMain() {
  if (!cfg) {
    mainEl.innerHTML = `<p class="sz-muted">加载中…</p>`;
    return;
  }
  const group = GROUPS.find((g) => g.id === activeId) || GROUPS[0];
  if (group.id === "llm") {
    renderLlmMain(group);
    return;
  }
  const data = cfg[group.id] || {};

  mainEl.innerHTML = `
    <header class="sz-config-header">
      <h2>${esc(group.title)}</h2>
      <p class="sz-muted">${esc(group.id)}</p>
    </header>
    <form class="sz-config-form" id="sz-config-form" autocomplete="off">
      ${group.fields.map((f) => fieldHtml(f, data)).join("")}
      <div class="sz-config-actions">
        <button type="submit" class="sz-btn sz-btn-primary" ${cfg.meta?.env_writable === false ? "disabled title=\"env 不可写\"" : ""}>保存</button>
        <button type="button" class="sz-btn" id="sz-config-reset">重置</button>
      </div>
    </form>
    <div class="sz-config-effects" id="sz-config-effects" hidden></div>
  `;

  const form = document.getElementById("sz-config-form");
  form.onsubmit = (e) => {
    e.preventDefault();
    save(group);
  };
  document.getElementById("sz-config-reset").onclick = () => renderMain();

  if (cfg.settings_effects) {
    showEffects(cfg.settings_effects);
  }
}

function renderLlmMain(group) {
  const data = cfg.llm || {};
  const providers = data.providers || [];
  const active = data.active || "";
  const formats = data.formats || ["openai", "openai-compatible", "local"];

  const rows = providers.length
    ? providers
        .map((p) => {
          const isActive = p.name === active;
          return `<li class="sz-llm-row${isActive ? " is-active" : ""}" data-name="${esc(p.name)}">
            <div class="sz-llm-meta">
              <strong>${esc(p.name)}</strong>
              <span class="sz-muted">${esc(FORMAT_LABEL[p.format] || p.format)} · ${esc(p.model)}</span>
              ${p.base_url ? `<span class="sz-muted sz-llm-url">${esc(p.base_url)}</span>` : ""}
            </div>
            <div class="sz-llm-actions">
              ${
                isActive
                  ? `<span class="sz-llm-badge">使用中</span>`
                  : `<button type="button" class="sz-btn sz-btn-primary" data-activate="${esc(p.name)}">设为当前</button>`
              }
              <button type="button" class="sz-btn sz-btn-danger" data-remove="${esc(p.name)}" ${isActive && providers.length === 1 ? "disabled" : ""}>删除</button>
            </div>
          </li>`;
        })
        .join("")
    : `<li class="sz-muted">尚未注册模型，请在下方添加</li>`;

  const formatOpts = formats
    .map((f) => `<option value="${esc(f)}">${esc(FORMAT_LABEL[f] || f)}</option>`)
    .join("");

  mainEl.innerHTML = `
    <header class="sz-config-header">
      <h2>${esc(group.title)}</h2>
      <p class="sz-muted">注册多个模型，选择其一使用</p>
    </header>

    <section class="sz-llm-block">
      <h3>已注册</h3>
      <ul class="sz-llm-list" id="sz-llm-list">${rows}</ul>
    </section>

    <section class="sz-llm-block">
      <h3>注册新模型</h3>
      <form class="sz-config-form" id="sz-llm-add" autocomplete="off">
        <label class="sz-field">
          <span class="sz-field-label">名称</span>
          <input name="name" required placeholder="如 deepseek、qwen" />
        </label>
        <label class="sz-field">
          <span class="sz-field-label">类型</span>
          <select name="format">${formatOpts}</select>
        </label>
        <label class="sz-field">
          <span class="sz-field-label">模型 ID</span>
          <input name="model" required placeholder="如 deepseek-chat、gpt-4o-mini" />
        </label>
        <label class="sz-field">
          <span class="sz-field-label">Base URL</span>
          <input name="base_url" placeholder="https://api.deepseek.com/v1" />
        </label>
        <label class="sz-field">
          <span class="sz-field-label">API Key</span>
          <input type="password" name="api_key" placeholder="local 类型可留空" autocomplete="new-password" />
        </label>
        <div class="sz-config-actions">
          <button type="submit" class="sz-btn sz-btn-primary">注册</button>
        </div>
      </form>
    </section>

    <section class="sz-llm-block">
      <h3>超时</h3>
      <form class="sz-config-form" id="sz-config-form" autocomplete="off">
        ${group.fields.map((f) => fieldHtml(f, data)).join("")}
        <div class="sz-config-actions">
          <button type="submit" class="sz-btn sz-btn-primary" ${cfg.meta?.env_writable === false ? "disabled" : ""}>保存超时</button>
        </div>
      </form>
    </section>
    <div class="sz-config-effects" id="sz-config-effects" hidden></div>
  `;

  document.getElementById("sz-llm-list")?.addEventListener("click", onLlmListClick);
  document.getElementById("sz-llm-add").onsubmit = (e) => {
    e.preventDefault();
    addLlmProvider(e.target);
  };
  document.getElementById("sz-config-form").onsubmit = (e) => {
    e.preventDefault();
    save(group);
  };
  if (cfg.settings_effects) showEffects(cfg.settings_effects);
}

async function onLlmListClick(e) {
  const act = e.target.closest("[data-activate]");
  const del = e.target.closest("[data-remove]");
  if (act) {
    try {
      const data = await apiPost("/llm-providers/active", {
        name: act.getAttribute("data-activate"),
      });
      cfg.llm = {
        ...cfg.llm,
        active: data.active,
        providers: data.items,
        model: data.items?.find((p) => p.name === data.active)?.model || cfg.llm.model,
      };
      toast(`已切换为 ${data.active}`, "success");
      renderMain();
      await load();
    } catch (err) {
      toast(err.message || "切换失败", "error");
    }
    return;
  }
  if (del) {
    const name = del.getAttribute("data-remove");
    if (!name || !confirm(`删除模型「${name}」？`)) return;
    try {
      const data = await apiDelete(`/llm-providers/${encodeURIComponent(name)}`);
      cfg.llm = { ...cfg.llm, active: data.active, providers: data.items };
      toast("已删除", "success");
      await load();
    } catch (err) {
      toast(err.message || "删除失败", "error");
    }
  }
}

async function addLlmProvider(form) {
  const fd = new FormData(form);
  const payload = {
    name: String(fd.get("name") || "").trim(),
    format: String(fd.get("format") || "openai").trim(),
    model: String(fd.get("model") || "").trim(),
    base_url: String(fd.get("base_url") || "").trim(),
    api_key: String(fd.get("api_key") || "").trim(),
  };
  try {
    await apiPost("/llm-providers", payload);
    toast(`已注册 ${payload.name}`, "success");
    form.reset();
    await load();
  } catch (err) {
    toast(err.message || "注册失败", "error");
  }
}

function fieldHtml(f, data) {
  const id = `field-${f.key}`;
  if (f.type === "checkbox") {
    const checked = !!data[f.key];
    return `
      <label class="sz-field sz-field-check">
        <input type="checkbox" id="${id}" name="${f.key}" ${checked ? "checked" : ""} ${f.readonly ? "disabled" : ""} />
        <span>${esc(f.label)}${f.readonly ? " <span class=\"sz-muted\">（只读）</span>" : ""}</span>
      </label>`;
  }

  if (f.secret) {
    const configured = !!data.configured;
    const ph = configured ? "已配置" : "未配置";
    return `
      <label class="sz-field">
        <span class="sz-field-label">${esc(f.label)}</span>
        <input type="password" id="${id}" name="${f.key}" value="" placeholder="${esc(ph)}" autocomplete="new-password" />
      </label>`;
  }

  if (f.type === "select") {
    const val = data[f.key] ?? "";
    const opts = (f.options || [])
      .map((o) => `<option value="${esc(o)}" ${o === val ? "selected" : ""}>${esc(o)}</option>`)
      .join("");
    return `
      <label class="sz-field">
        <span class="sz-field-label">${esc(f.label)}</span>
        <select id="${id}" name="${f.key}">${opts}</select>
      </label>`;
  }

  const type = f.type === "number" ? "number" : "text";
  const step = f.step ? ` step="${esc(f.step)}"` : "";
  const val = data[f.key] ?? "";
  return `
    <label class="sz-field">
      <span class="sz-field-label">${esc(f.label)}</span>
      <input type="${type}" id="${id}" name="${f.key}" value="${esc(String(val))}"${step} />
    </label>`;
}

async function save(group) {
  const form = document.getElementById("sz-config-form");
  const payload = {};

  for (const f of group.fields) {
    if (f.readonly) continue;
    const el = form.elements.namedItem(f.key);
    if (!el) continue;

    if (f.type === "checkbox") {
      payload[f.key] = el.checked;
      continue;
    }

    if (f.secret) {
      const raw = String(el.value || "").trim();
      if (!raw || raw === MASKED_SECRET) continue;
      payload[f.key] = raw;
      continue;
    }

    let v = el.value;
    if (f.type === "number") {
      if (v === "" || v == null) continue;
      v = Number(v);
      if (Number.isNaN(v)) {
        toast(`${f.label} 不是有效数字`, "error");
        return;
      }
    }
    payload[f.key] = v;
  }

  if (!Object.keys(payload).length) {
    toast("没有可保存的更改", "error");
    return;
  }

  try {
    const data = await apiPatch("/config", { [group.id]: payload });
    cfg = data;
    toast("已保存", "success");
    renderNav();
    renderMain();
    if (data.settings_effects) showEffects(data.settings_effects);
  } catch (err) {
    toast(err.message || "保存失败", "error");
  }
}

function showEffects(effects) {
  const el = document.getElementById("sz-config-effects");
  if (!el || !effects) return;
  const hot = effects.hot_reload || [];
  const restart = effects.restart_required || [];
  const notes = effects.notes || [];
  if (!hot.length && !restart.length && !notes.length) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  el.innerHTML = `
    <h3>生效说明</h3>
    ${hot.length ? `<p>热更新：${esc(hot.join("、"))}</p>` : ""}
    ${restart.length ? `<p class="sz-warn">需重启：${esc(restart.join("、"))}</p>` : ""}
    ${notes.map((n) => `<p class="sz-muted">${esc(n)}</p>`).join("")}
  `;
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

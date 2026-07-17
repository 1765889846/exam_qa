import { apiAskStream } from "../../shared/js/api.js";
import { getCourseId, initShell, toast } from "../../shared/js/shell.js";
import { enableColumnResize } from "../../shared/js/resize.js";
import {
  appendTurn,
  createConversation,
  getActiveConversationId,
  getConversation,
  listConversations,
  removeConversation,
  setActiveConversationId,
} from "../../shared/js/conversations.js";

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderCitations(el, cites) {
  if (!el) return;
  if (!cites?.length) {
    el.innerHTML = "";
    return;
  }
  el.innerHTML = cites
    .map((c, i) => {
      const score =
        typeof c.score === "number"
          ? c.score.toFixed(3)
          : c.score != null
            ? String(c.score)
            : "";
      const page = c.page != null ? ` p.${c.page}` : "";
      return `<details class="sz-cite">
        <summary>[${i + 1}] ${escapeHtml(c.source_file || "")}${page}${
          score ? ` · ${escapeHtml(score)}` : ""
        }</summary>
        <pre>${escapeHtml(c.snippet || "")}</pre>
      </details>`;
    })
    .join("");
}

function renderAnswerMath(el) {
  if (!el || !window.renderMathInElement) return;
  window.renderMathInElement(el, {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "\\[", right: "\\]", display: true },
      { left: "$", right: "$", display: false },
      { left: "\\(", right: "\\)", display: false },
    ],
    throwOnError: false,
  });
}

function renderTurnHtml(turn) {
  const grounded = turn.grounded;
  const groundedAttr =
    grounded === false ? ` data-grounded="false"` : grounded === true ? ` data-grounded="true"` : "";
  return `<div class="sz-turn">
    <div class="sz-q"></div>
    <div class="sz-a"${groundedAttr}></div>
    <div class="sz-cites"></div>
  </div>`;
}

function paintTurn(node, turn) {
  node.querySelector(".sz-q").textContent = turn.question || "";
  const a = node.querySelector(".sz-a");
  a.textContent = turn.answer || "";
  if (turn.grounded === false) a.dataset.grounded = "false";
  else if (turn.grounded === true) a.dataset.grounded = "true";
  renderCitations(node.querySelector(".sz-cites"), turn.citations || []);
  renderAnswerMath(a);
}

function showAskEmpty() {
  const streamEl = document.getElementById("sz-ask-stream");
  if (!streamEl) return;
  streamEl.innerHTML = `<p class="sz-ask-empty">选择课程后提问；左侧可切换历史对话</p>`;
}

function renderConversationTurns(conv) {
  const streamEl = document.getElementById("sz-ask-stream");
  if (!streamEl) return;
  if (!conv?.turns?.length) {
    showAskEmpty();
    return;
  }
  streamEl.innerHTML = conv.turns.map(() => renderTurnHtml({})).join("");
  const nodes = streamEl.querySelectorAll(".sz-turn");
  conv.turns.forEach((t, i) => paintTurn(nodes[i], t));
  streamEl.scrollTop = streamEl.scrollHeight;
}

function refreshHistoryList() {
  const box = document.getElementById("sz-history-list");
  if (!box) return;
  const courseId = getCourseId();
  if (!courseId) {
    box.innerHTML = `<p class="sz-muted">请先选择课程</p>`;
    return;
  }
  const active = getActiveConversationId(courseId);
  const list = listConversations(courseId);
  if (!list.length) {
    box.innerHTML = `<p class="sz-muted">暂无对话，点击上方开始</p>`;
    return;
  }
  box.innerHTML = list
    .map(
      (c) => `<div class="sz-conv-row${c.id === active ? " is-active" : ""}" data-id="${c.id}" role="button" tabindex="0">
        <span class="sz-conv-title">${escapeHtml(c.title || "新对话")}</span>
        <button type="button" class="sz-conv-del" data-del="${c.id}" title="删除">删除</button>
      </div>`,
    )
    .join("");
}

function loadActiveConversation() {
  const courseId = getCourseId();
  if (!courseId) {
    showAskEmpty();
    refreshHistoryList();
    return;
  }
  let id = getActiveConversationId(courseId);
  let conv = id ? getConversation(courseId, id) : null;
  if (!conv) {
    const list = listConversations(courseId);
    conv = list[0] || null;
    if (conv) setActiveConversationId(courseId, conv.id);
  }
  refreshHistoryList();
  if (conv) renderConversationTurns(conv);
  else showAskEmpty();
}

function setupHistory() {
  const box = document.getElementById("sz-history-list");
  const newBtn = document.getElementById("sz-new-chat");
  if (!box || !newBtn) return;

  newBtn.addEventListener("click", () => {
    const courseId = getCourseId();
    if (!courseId) {
      toast("请先选择课程", "error");
      return;
    }
    createConversation(courseId);
    refreshHistoryList();
    showAskEmpty();
    document.getElementById("sz-ask-input")?.focus();
  });

  box.addEventListener("click", (e) => {
    const del = e.target.closest("[data-del]");
    if (del) {
      e.stopPropagation();
      const id = del.getAttribute("data-del");
      const courseId = getCourseId();
      if (!id || !courseId || !confirm("删除该对话？")) return;
      removeConversation(courseId, id);
      loadActiveConversation();
      return;
    }
    const row = e.target.closest(".sz-conv-row");
    if (!row) return;
    const id = row.getAttribute("data-id");
    const courseId = getCourseId();
    if (!id || !courseId) return;
    setActiveConversationId(courseId, id);
    refreshHistoryList();
    const conv = getConversation(courseId, id);
    renderConversationTurns(conv);
  });
}

function bindCourseChange() {
  const collegeSel = document.getElementById("sz-college");
  const courseSel = document.getElementById("sz-course");
  if (!collegeSel || !courseSel) return;

  const shellCollege = collegeSel.onchange;
  const shellCourse = courseSel.onchange;

  collegeSel.onchange = async (ev) => {
    if (shellCollege) await shellCollege.call(collegeSel, ev);
    loadActiveConversation();
  };
  courseSel.onchange = (ev) => {
    if (shellCourse) shellCourse.call(courseSel, ev);
    loadActiveConversation();
  };
}

function setupAsk() {
  const streamEl = document.getElementById("sz-ask-stream");
  const form = document.getElementById("sz-ask-form");
  const input = document.getElementById("sz-ask-input");
  if (!streamEl || !form || !input) return;

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = input.value.trim();
    const courseId = getCourseId();
    if (!question || !courseId) {
      toast("需要课程与问题", "error");
      return;
    }

    if (streamEl.querySelector(".sz-ask-empty")) {
      streamEl.replaceChildren();
    }

    let answer = "";
    const turnWrap = document.createElement("div");
    turnWrap.className = "sz-turn";
    turnWrap.innerHTML = `<div class="sz-q"></div><div class="sz-a" id="sz-live-a"></div><div class="sz-cites" id="sz-cites"></div>`;
    turnWrap.querySelector(".sz-q").textContent = question;
    streamEl.appendChild(turnWrap);
    const live = turnWrap.querySelector(".sz-a");
    const citesEl = turnWrap.querySelector(".sz-cites");
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;
    input.value = "";
    streamEl.scrollTop = streamEl.scrollHeight;

    let citations = [];
    let grounded = true;
    let finished = false;

    try {
      await apiAskStream({ question, course_id: courseId, mode: "qa" }, (ev) => {
        if (ev.type === "phase") {
          live.dataset.phase = ev.phase || "";
          if (!answer) {
            live.textContent =
              ev.phase === "retrieving"
                ? "检索中…（向量化问题）"
                : ev.phase === "generating"
                  ? "生成中…"
                  : "";
          }
        } else if (ev.type === "delta") {
          answer += ev.text || "";
          live.textContent = answer;
          streamEl.scrollTop = streamEl.scrollHeight;
        } else if (ev.type === "done") {
          const d = ev.data || {};
          answer = d.answer || answer;
          live.textContent = answer;
          delete live.dataset.phase;
          grounded = !!d.grounded;
          live.dataset.grounded = String(grounded);
          citations = d.citations || [];
          renderCitations(citesEl, citations);
          renderAnswerMath(live);
          streamEl.scrollTop = streamEl.scrollHeight;
          finished = true;
        } else if (ev.type === "error") {
          const msg = ev.message || "问答失败";
          live.textContent = msg;
          live.dataset.grounded = "false";
          toast(msg, "error");
        }
      });

      if (finished) {
        appendTurn(courseId, { question, answer, citations, grounded });
        refreshHistoryList();
      }
    } catch (err) {
      const msg = err.message || "问答失败";
      live.textContent = msg;
      live.dataset.grounded = "false";
      toast(msg, "error");
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
}

function setupHistoryCollapse() {
  const root = document.getElementById("sz-workbench");
  const collapseBtn = document.getElementById("sz-history-toggle");
  const expandBtn = document.getElementById("sz-history-expand");
  if (!root || !collapseBtn || !expandBtn) return;

  const KEY = "sz.history_collapsed";

  function apply(collapsed) {
    root.classList.toggle("is-history-collapsed", collapsed);
    collapseBtn.setAttribute("aria-expanded", collapsed ? "false" : "true");
    collapseBtn.title = collapsed ? "展开侧栏" : "收起侧栏";
    expandBtn.hidden = !collapsed;
    localStorage.setItem(KEY, collapsed ? "1" : "0");
  }

  apply(localStorage.getItem(KEY) === "1");
  collapseBtn.addEventListener("click", () => apply(true));
  expandBtn.addEventListener("click", () => apply(false));
}

async function main() {
  await initShell({ active: "sz" });
  enableColumnResize({
    root: document.getElementById("sz-workbench"),
    cssVar: "--sz-docs-width",
    storageKey: "sz.history_width",
    min: 180,
    max: 360,
    defaultWidth: 240,
  });
  setupHistoryCollapse();
  setupHistory();
  bindCourseChange();
  setupAsk();
  loadActiveConversation();
}

main();

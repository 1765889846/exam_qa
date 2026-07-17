import { apiGet, apiDelete, apiUpload } from "../../shared/js/api.js";
import { getCourseId, initShell, toast } from "../../shared/js/shell.js";

const ACCEPT = ".pdf,.txt,.md,.doc,.docx,.pptx";

async function refreshDocs() {
  const box = document.getElementById("sz-docs-list");
  if (!box) return;

  const courseId = getCourseId();
  if (!courseId) {
    box.textContent = "请先选择课程";
    return;
  }

  try {
    const data = await apiGet("/documents", { course_id: courseId });
    const items = data?.items || [];
    if (!items.length) {
      box.innerHTML = `<p class="sz-muted">暂无资料</p>`;
      return;
    }
    box.innerHTML = items
      .map(
        (d) => `<div class="sz-doc-row" data-id="${d.id}">
          <div class="sz-doc-meta">
            <span class="sz-doc-name">${escapeHtml(d.filename || String(d.id))}</span>
            <span class="sz-doc-status">${escapeHtml(d.status || "")}${
              d.chunk_count != null ? ` · ${d.chunk_count} 块` : ""
            }</span>
          </div>
          <button type="button" class="sz-doc-del" data-del="${d.id}">删除</button>
        </div>`,
      )
      .join("");
  } catch (err) {
    box.textContent = err.message || "加载失败";
    toast(err.message || "加载资料失败", "error");
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setupUploadZone() {
  const zone = document.getElementById("sz-upload-zone");
  if (!zone) return;

  zone.innerHTML = `
    <div class="sz-docs-actions">
      <label class="sz-upload-btn">
        上传资料
        <input type="file" id="sz-file-input" accept="${ACCEPT}" hidden />
      </label>
      <button type="button" id="sz-scan-btn">扫描目录</button>
    </div>
    <p class="sz-muted sz-upload-hint">PDF / TXT / MD / DOC / DOCX / PPTX</p>
  `;

  const input = document.getElementById("sz-file-input");
  const scanBtn = document.getElementById("sz-scan-btn");

  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;

    const courseId = getCourseId();
    if (!courseId) {
      toast("请先选择课程", "error");
      return;
    }

    const fd = new FormData();
    fd.append("file", file);
    fd.append("course_id", courseId);
    try {
      await apiUpload("/documents", fd);
      toast("上传成功", "success");
      await refreshDocs();
    } catch (err) {
      toast(err.message || "上传失败", "error");
    }
  });

  scanBtn.addEventListener("click", async () => {
    const courseId = getCourseId();
    if (!courseId) {
      toast("请先选择课程", "error");
      return;
    }
    const fd = new FormData();
    fd.append("course_id", courseId);
    scanBtn.disabled = true;
    try {
      // scan 用 Form course_id；复用 apiUpload 的 multipart POST
      await apiUpload("/documents/scan", fd);
      toast("扫描完成", "success");
      await refreshDocs();
    } catch (err) {
      toast(err.message || "扫描失败", "error");
    } finally {
      scanBtn.disabled = false;
    }
  });
}

function setupDocList() {
  const box = document.getElementById("sz-docs-list");
  if (!box) return;
  box.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-del]");
    if (!btn) return;
    const id = btn.getAttribute("data-del");
    if (!id || !confirm("确认删除该资料？")) return;
    try {
      await apiDelete(`/documents/${id}`);
      toast("已删除", "success");
      await refreshDocs();
    } catch (err) {
      toast(err.message || "删除失败", "error");
    }
  });
}

function bindCourseChange() {
  const collegeSel = document.getElementById("sz-college");
  const courseSel = document.getElementById("sz-course");
  if (!collegeSel || !courseSel) return;

  // shell 里 college onchange 会异步重载课程；包一层保证刷新在其后
  const shellCollege = collegeSel.onchange;
  const shellCourse = courseSel.onchange;

  collegeSel.onchange = async (ev) => {
    if (shellCollege) await shellCollege.call(collegeSel, ev);
    await refreshDocs();
  };
  courseSel.onchange = (ev) => {
    if (shellCourse) shellCourse.call(courseSel, ev);
    refreshDocs();
  };
}

async function main() {
  await initShell({ active: "sz" });
  setupUploadZone();
  setupDocList();
  bindCourseChange();
  await refreshDocs();
}

main();

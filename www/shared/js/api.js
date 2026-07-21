const BASE = "/api/v1";

async function parse(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok || (body.code != null && body.code >= 400)) {
    const msg = body.message || res.statusText || "请求失败";
    throw new Error(msg);
  }
  return body.data !== undefined ? body.data : body;
}

export async function apiGet(path, params) {
  const url = new URL(BASE + path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v != null && v !== "") url.searchParams.set(k, v);
    });
  }
  return parse(await fetch(url));
}

export async function apiPost(path, json) {
  return parse(
    await fetch(BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(json),
    }),
  );
}

export async function apiPatch(path, json) {
  return parse(
    await fetch(BASE + path, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(json),
    }),
  );
}

export async function apiDelete(path, params) {
  const url = new URL(BASE + path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v != null && v !== "") url.searchParams.set(k, v);
    });
  }
  return parse(await fetch(url, { method: "DELETE" }));
}

export async function apiUpload(path, formData) {
  return parse(await fetch(BASE + path, { method: "POST", body: formData }));
}

/**
 * multipart POST；onProgress({ phase, loaded?, total?, ratio? })
 */
export function apiUploadWithProgress(path, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", BASE + path);
    xhr.upload.onprogress = (ev) => {
      if (!ev.lengthComputable) return;
      onProgress?.({
        phase: "upload",
        loaded: ev.loaded,
        total: ev.total,
        ratio: ev.total ? ev.loaded / ev.total : 0,
      });
    };
    xhr.upload.onload = () => {
      onProgress?.({ phase: "processing", ratio: 1 });
    };
    xhr.onload = () => {
      let body = {};
      try {
        body = JSON.parse(xhr.responseText || "{}");
      } catch {
        /* ignore */
      }
      if (xhr.status >= 400 || (body.code != null && body.code >= 400)) {
        reject(new Error(body.message || xhr.statusText || "请求失败"));
        return;
      }
      resolve(body.data !== undefined ? body.data : body);
    };
    xhr.onerror = () => reject(new Error("网络错误"));
    xhr.onabort = () => reject(new Error("已取消"));
    xhr.send(formData);
  });
}

export async function apiAskStream(body, onEvent, signal) {
  const res = await fetch(BASE + "/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...body, stream: true }),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || res.statusText || "问答失败");
  }
  if (!res.body) {
    throw new Error("浏览器不支持流式响应");
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";

  function flushChunk(chunk) {
    for (const line of chunk.split("\n")) {
      if (!line.startsWith("data:")) continue;
      const raw = line.slice(5).trim();
      if (!raw) continue;
      try {
        onEvent(JSON.parse(raw));
      } catch {
        /* ignore bad SSE line */
      }
    }
  }

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() || "";
    for (const chunk of parts) flushChunk(chunk);
  }
  buf += dec.decode();
  if (buf.trim()) flushChunk(buf);
}

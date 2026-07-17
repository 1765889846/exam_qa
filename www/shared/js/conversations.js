/** 按课程隔离的本地会话历史（localStorage）。 */

const ACTIVE_KEY = "sz.active_conversation_id";

function storeKey(courseId) {
  return `sz.conversations.${courseId || "_none"}`;
}

function readAll(courseId) {
  try {
    const raw = localStorage.getItem(storeKey(courseId));
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

function writeAll(courseId, list) {
  localStorage.setItem(storeKey(courseId), JSON.stringify(list));
}

function uid() {
  return `c_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

/** 用首问生成侧栏标题（与内容相关，非占位「新对话」）。 */
export function titleFromQuestion(question) {
  const raw = String(question || "")
    .replace(/\s+/g, " ")
    .trim();
  if (!raw) return "新对话";
  const first = raw.split(/[。？?！!\n]/)[0].trim() || raw;
  const cleaned = first.replace(/^[#*\-·\s]+/, "").trim();
  const text = cleaned || first;
  return text.length > 36 ? `${text.slice(0, 36)}…` : text;
}

export function listConversations(courseId) {
  const list = readAll(courseId);
  let dirty = false;
  for (const c of list) {
    if ((!c.title || c.title === "新对话") && c.turns?.[0]?.question) {
      c.title = titleFromQuestion(c.turns[0].question);
      dirty = true;
    }
  }
  if (dirty) writeAll(courseId, list);
  return list.sort((a, b) =>
    String(b.updatedAt || "").localeCompare(String(a.updatedAt || "")),
  );
}

export function getConversation(courseId, id) {
  return readAll(courseId).find((c) => c.id === id) || null;
}

export function getActiveConversationId(courseId) {
  const map = JSON.parse(localStorage.getItem(ACTIVE_KEY) || "{}");
  return map[courseId || "_none"] || "";
}

export function setActiveConversationId(courseId, id) {
  const map = JSON.parse(localStorage.getItem(ACTIVE_KEY) || "{}");
  const key = courseId || "_none";
  if (id) map[key] = id;
  else delete map[key];
  localStorage.setItem(ACTIVE_KEY, JSON.stringify(map));
}

export function createConversation(courseId, title = "新对话") {
  const conv = {
    id: uid(),
    title: titleFromQuestion(title) || "新对话",
    updatedAt: new Date().toISOString(),
    turns: [],
  };
  const list = readAll(courseId);
  list.unshift(conv);
  writeAll(courseId, list);
  setActiveConversationId(courseId, conv.id);
  return conv;
}

export function removeConversation(courseId, id) {
  const list = readAll(courseId).filter((c) => c.id !== id);
  writeAll(courseId, list);
  if (getActiveConversationId(courseId) === id) {
    setActiveConversationId(courseId, list[0]?.id || "");
  }
}

export function appendTurn(courseId, turn) {
  let list = readAll(courseId);
  let id = getActiveConversationId(courseId);
  let conv = list.find((c) => c.id === id);
  const q = turn.question || "";
  if (!conv) {
    conv = {
      id: uid(),
      title: titleFromQuestion(q),
      updatedAt: new Date().toISOString(),
      turns: [],
    };
    list.unshift(conv);
    id = conv.id;
    setActiveConversationId(courseId, id);
  }
  conv.turns.push({
    question: q,
    answer: turn.answer || "",
    citations: turn.citations || [],
    grounded: turn.grounded !== false,
  });
  if (q && (conv.turns.length === 1 || !conv.title || conv.title === "新对话")) {
    conv.title = titleFromQuestion(q);
  }
  conv.updatedAt = new Date().toISOString();
  writeAll(
    courseId,
    list.map((c) => (c.id === conv.id ? conv : c)),
  );
  return conv;
}

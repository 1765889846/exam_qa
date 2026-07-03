const DOC_STATUS: Record<string, string> = {
  done: "已入库",
  pending: "排队中",
  processing: "处理中",
  failed: "失败",
};

export function formatDocStatus(status: string): string {
  return DOC_STATUS[status] ?? status;
}

const HEALTH_COMPONENT: Record<string, string> = {
  ok: "正常",
  not_ready: "未加载",
  unavailable: "不可用",
};

export function formatHealthComponent(value: string): string {
  return HEALTH_COMPONENT[value] ?? value;
}

/** 与后端 config.retrieval.score_threshold 默认值对齐 */
export const RELEVANCE_THRESHOLD = 0.25;

/** 检索相关性：对用户展示高/中/低，不暴露原始 score。 */
export function formatRelevance(
  score: number,
  threshold = RELEVANCE_THRESHOLD,
): "高" | "中" | "低" {
  const highMin = Math.max(threshold * 2, threshold + 0.25);
  if (score >= highMin) return "高";
  if (score >= threshold) return "中";
  return "低";
}

/** 引用 source_file 与资料 filename 是否对应同一文件。 */
export function matchSourceToDoc(sourceFile: string, docFilename: string): boolean {
  const base = sourceFile.split(/[/\\]/).pop() ?? sourceFile;
  const docBase = docFilename.split(/[/\\]/).pop() ?? docFilename;
  return (
    base === docBase ||
    docFilename.includes(base) ||
    sourceFile.includes(docBase)
  );
}

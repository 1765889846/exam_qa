import { useEffect, useMemo, useState } from "react";
import { Pagination, Skeleton, Spin, Modal } from "antd";
import { useWorkbench } from "@/features/workbench/WorkbenchContext";
import { formatDocStatus, matchSourceToDoc } from "@/lib/format";
import type { DocumentItem } from "@/lib/api/types";

const PAGE_SIZE = 8;

interface DocumentListProps {
  items: DocumentItem[];
  loading: boolean;
  onDelete: (id: number) => void;
}

function DocumentSkeleton() {
  return (
    <div className="exam-doc-skeleton" aria-hidden="true">
      <Skeleton active title={false} paragraph={{ rows: 2, width: ["80%", "50%"] }} />
    </div>
  );
}

export function DocumentList({ items, loading, onDelete }: DocumentListProps) {
  const { highlightedSource } = useWorkbench();
  const [page, setPage] = useState(1);

  const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const pageItems = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return items.slice(start, start + PAGE_SIZE);
  }, [items, page]);

  if (loading && items.length === 0) {
    return (
      <div aria-busy="true" aria-label="加载资料列表">
        <DocumentSkeleton />
        <DocumentSkeleton />
        <DocumentSkeleton />
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="exam-empty" style={{ padding: 20, fontSize: 13 }}>
        还没有资料，上传一个吧~
      </div>
    );
  }

  return (
    <div className="exam-doc-list-wrap">
      <ul className="exam-doc-list">
        {pageItems.map((doc) => {
          const highlighted =
            highlightedSource != null &&
            matchSourceToDoc(highlightedSource, doc.filename);
          const isPending = doc.status === "pending" || doc.status === "processing";

          return (
            <li
              key={doc.id}
              className={`exam-doc-list__item${highlighted ? " exam-doc-list__item--highlight" : ""}`}
            >
              <div className="exam-doc-list__body">
                <div className="exam-doc-list__name" title={doc.filename}>
                  {doc.filename}
                </div>
                <div className="exam-doc-list__meta">
                  {doc.chunk_count} 段 · {formatDocStatus(doc.status)}
                  {isPending && (
                    <Spin size="small" className="exam-doc-list__pending-spin" />
                  )}
                </div>
              </div>
              <button
                type="button"
                className="exam-doc-list__del"
                aria-label={`删除 ${doc.filename}`}
                onClick={() => {
                  Modal.confirm({
                    title: "确定删除这个资料吗？",
                    content: "相关向量数据也会被清除。",
                    okText: "删除",
                    okType: "danger",
                    cancelText: "取消",
                    onOk: () => onDelete(doc.id),
                  });
                }}
              >
                删除
              </button>
            </li>
          );
        })}
      </ul>

      {items.length > PAGE_SIZE ? (
        <Pagination
          className="exam-doc-list__pager"
          size="small"
          current={page}
          pageSize={PAGE_SIZE}
          total={items.length}
          showSizeChanger={false}
          showTotal={(total) => `共 ${total} 个资料`}
          onChange={setPage}
        />
      ) : null}
    </div>
  );
}

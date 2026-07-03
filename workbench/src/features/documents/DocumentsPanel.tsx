import { useCallback, useId, useRef, useState, type KeyboardEvent } from "react";
import { Spin, Tooltip } from "antd";
import { DocumentList } from "./DocumentList";
import { useDocuments } from "./useDocuments";

const ACCEPT = ".pdf,.txt,.md,.doc,.docx,.pptx";

export function DocumentsPanel() {
  const { items, loading, uploading, uploadingName, scanning, upload, remove, scan } =
    useDocuments();
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const busy = uploading || scanning;

  const pickFile = useCallback(() => {
    if (!busy) inputRef.current?.click();
  }, [busy]);

  const handleFile = useCallback(
    (file: File | undefined) => {
      if (file && !busy) upload(file);
    },
    [upload, busy],
  );

  const onUploadKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      pickFile();
    }
  };

  return (
    <>
      <h2 className="exam-section-title">
        资料库
        <Tooltip title="扫描 data/knowledge/ 目录，导入新增或变更的文件">
          <button
            type="button"
            className="exam-section-title__action"
            aria-label="扫描本地资料目录"
            disabled={scanning}
            onClick={() => scan()}
          >
            {scanning ? "扫描中…" : "扫描本地目录"}
          </button>
        </Tooltip>
      </h2>

      <button
        type="button"
        className={`exam-upload-zone${dragging ? " exam-upload-zone--drag" : ""}${busy ? " exam-upload-zone--busy" : ""}`}
        aria-label="上传资料，支持 PDF、TXT、MD、DOC、DOCX、PPTX"
        aria-busy={uploading}
        disabled={busy}
        onClick={pickFile}
        onKeyDown={onUploadKeyDown}
        onDragOver={(e) => {
          if (busy) return;
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFile(e.dataTransfer.files[0]);
        }}
      >
        {uploading ? (
          <>
            <Spin size="small" />
            <p className="exam-upload-zone__text">
              正在上传 {uploadingName}…
            </p>
            <p className="exam-upload-zone__hint">大文件可能需要较长时间</p>
          </>
        ) : scanning ? (
          <>
            <Spin size="small" />
            <p className="exam-upload-zone__text">正在扫描本地资料目录…</p>
            <p className="exam-upload-zone__hint">扫描完成前请稍候</p>
          </>
        ) : (
          <>
            <div className="exam-upload-zone__icon">上传资料</div>
            <p className="exam-upload-zone__text">点击或拖拽文件到此处</p>
            <p className="exam-upload-zone__hint">
              支持 PDF / TXT / MD / DOC / DOCX / PPTX
            </p>
          </>
        )}
      </button>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={ACCEPT}
        hidden
        disabled={busy}
        onChange={(e) => {
          handleFile(e.target.files?.[0]);
          e.target.value = "";
        }}
      />

      <DocumentList items={items} loading={loading} onDelete={remove} />
    </>
  );
}

import { useCallback, useEffect, useState } from "react";
import { message } from "antd";
import { apiClient } from "@/lib/api/client";
import { ApiError, isAbortError } from "@/lib/api/errors";
import type { DocumentItem } from "@/lib/api/types";

export function useDocuments() {
  const [items, setItems] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadingName, setUploadingName] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const data = await apiClient.get<{ items: DocumentItem[] }>(
        "/documents",
        { signal },
      );
      setItems(data.items);
    } catch (e) {
      if (signal?.aborted || isAbortError(e)) {
        return;
      }
      const msg = e instanceof ApiError ? e.message : "加载资料失败";
      message.error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const upload = useCallback(
    async (file: File) => {
      setUploading(true);
      setUploadingName(file.name);
      const form = new FormData();
      form.append("file", file);
      try {
        const data = await apiClient.postForm<{
          doc_id: number;
          filename: string;
        }>("/documents", form);
        message.success(`上传成功: ${data.filename}`);
        await load();
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : "上传失败";
        message.error(msg);
      } finally {
        setUploading(false);
        setUploadingName(null);
      }
    },
    [load],
  );

  const remove = useCallback(
    async (id: number) => {
      try {
        const data = await apiClient.delete<{ message: string }>(
          `/documents/${id}`,
        );
        message.success(data.message || "已删除");
        await load();
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : "删除失败";
        message.error(msg);
      }
    },
    [load],
  );

  const scan = useCallback(async () => {
    setScanning(true);
    try {
      const data = await apiClient.post<{ message: string }>(
        "/documents/scan",
      );
      message.success(data.message || "扫描完成");
      await load();
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "扫描失败";
      message.error(msg);
    } finally {
      setScanning(false);
    }
  }, [load]);

  useEffect(() => {
    const ac = new AbortController();
    load(ac.signal);
    return () => ac.abort();
  }, [load]);

  return {
    items,
    loading,
    uploading,
    uploadingName,
    scanning,
    load,
    upload,
    remove,
    scan,
  };
}

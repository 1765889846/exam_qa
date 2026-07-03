import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Select,
  Skeleton,
  Space,
  Switch,
  Tag,
} from "antd";
import { apiClient } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { formatHealthComponent } from "@/lib/format";
import { useHealth } from "@/features/health/useHealth";
import type { AppConfigData, ConfigUpdateRequest } from "@/lib/api/types";
import { useSettings } from "./useSettings";

type FormValues = {
  llm_api_key: string;
  llm_base_url: string;
  llm_model: string;
  llm_timeout: number;
  embedding_provider: "local" | "openai";
  embedding_api_key: string;
  embedding_base_url: string;
  embedding_model: string;
  embedding_timeout: number;
  retrieval_top_k: number;
  retrieval_score_threshold: number;
  chunk_size: number;
  chunk_overlap: number;
  max_upload_mb: number;
  pdf_use_ocr: boolean;
  pdf_force_ocr: boolean;
  pdf_ocr_language: string;
  host: string;
  port: number;
  proxy_url: string;
  proxy_no_proxy: string;
};

function toFormValues(config: AppConfigData): FormValues {
  return {
    llm_api_key: "",
    llm_base_url: config.llm.base_url,
    llm_model: config.llm.model,
    llm_timeout: config.llm.timeout,
    embedding_provider: config.embedding.provider as "local" | "openai",
    embedding_api_key: "",
    embedding_base_url: config.embedding.base_url,
    embedding_model: config.embedding.model,
    embedding_timeout: config.embedding.timeout,
    retrieval_top_k: config.retrieval.top_k,
    retrieval_score_threshold: config.retrieval.score_threshold,
    chunk_size: config.chunk.chunk_size,
    chunk_overlap: config.chunk.chunk_overlap,
    max_upload_mb: config.app.max_upload_mb,
    pdf_use_ocr: config.parsing.pdf_use_ocr,
    pdf_force_ocr: config.parsing.pdf_force_ocr,
    pdf_ocr_language: config.parsing.pdf_ocr_language,
    host: config.server.host,
    port: config.server.port,
    proxy_url: config.proxy.url,
    proxy_no_proxy: config.proxy.no_proxy,
  };
}

function toPatch(values: FormValues, config: AppConfigData): ConfigUpdateRequest {
  const patch: ConfigUpdateRequest = {
    llm: {
      base_url: values.llm_base_url,
      model: values.llm_model,
      timeout: values.llm_timeout,
    },
    embedding: {
      provider: values.embedding_provider,
      base_url: values.embedding_base_url,
      model: values.embedding_model,
      timeout: values.embedding_timeout,
    },
    retrieval: {
      top_k: values.retrieval_top_k,
      score_threshold: values.retrieval_score_threshold,
    },
    chunk: {
      chunk_size: values.chunk_size,
      chunk_overlap: values.chunk_overlap,
    },
    parsing: {
      pdf_use_ocr: values.pdf_use_ocr,
      pdf_force_ocr: values.pdf_force_ocr,
      pdf_ocr_language: values.pdf_ocr_language,
    },
    app: { max_upload_mb: values.max_upload_mb },
    server: { host: values.host, port: values.port },
    proxy: { url: values.proxy_url.trim(), no_proxy: values.proxy_no_proxy.trim() },
  };

  if (values.llm_api_key.trim()) {
    patch.llm!.api_key = values.llm_api_key.trim();
  }
  if (values.embedding_api_key.trim()) {
    patch.embedding!.api_key = values.embedding_api_key.trim();
  } else if (
    values.embedding_provider === "openai" &&
    !config.embedding.configured &&
    !config.embedding.uses_separate_credentials
  ) {
    // openai without separate key may use llm key — no empty override
  }

  return patch;
}

export function SettingsPanel() {
  const { config, loading, saving, error, reload, save } = useSettings();
  const { data: health, refresh: refreshHealth } = useHealth();
  const [form] = Form.useForm<FormValues>();
  const [warming, setWarming] = useState(false);
  const [warmupError, setWarmupError] = useState<string | null>(null);

  useEffect(() => {
    if (config) {
      form.setFieldsValue(toFormValues(config));
    }
  }, [config, form]);

  const warmupEmbedding = useCallback(async () => {
    setWarming(true);
    setWarmupError(null);
    try {
      await apiClient.post("/embedding/warmup");
      await refreshHealth();
    } catch (e) {
      setWarmupError(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setWarming(false);
    }
  }, [refreshHealth]);

  const onFinish = async (values: FormValues) => {
    if (!config) return;
    await save(toPatch(values, config));
    form.setFieldValue("llm_api_key", "");
    form.setFieldValue("embedding_api_key", "");
    await refreshHealth();
  };

  if (error) {
    return (
      <div className="exam-empty">
        <p>{error}</p>
        <Button type="primary" onClick={() => reload()}>
          重试
        </Button>
      </div>
    );
  }

  if (loading || !config) {
    return (
      <div className="exam-settings" aria-busy="true">
        <Skeleton active paragraph={{ rows: 14 }} />
      </div>
    );
  }

  const embStatus = health?.embedding ?? config.health.embedding;

  return (
    <div className="exam-settings">
      <header className="exam-settings__header">
        <div>
          <h2 className="exam-settings__title">运行配置</h2>
          <p className="exam-settings__subtitle">
            修改写入 <code>{config.meta.config_path}</code>，保存后按提示生效
          </p>
        </div>
        <Space wrap>
          <Tag color={config.llm.configured ? "success" : "warning"}>
            LLM {formatHealthComponent(config.health.llm)}
          </Tag>
          <Tag color={embStatus === "ok" ? "success" : "default"}>
            Embedding {formatHealthComponent(embStatus)}
          </Tag>
        </Space>
      </header>

      {!config.meta.env_writable ? (
        <Alert
          type="warning"
          showIcon
          className="exam-settings__alert"
          message={`无法写入 ${config.meta.config_path}，请检查文件权限`}
        />
      ) : null}

      <Form
        form={form}
        layout="vertical"
        className="exam-settings__form"
        onFinish={(v) => void onFinish(v)}
        disabled={!config.meta.env_writable}
      >
        <Card title="网络代理" className="exam-settings__card" size="small">
          <p className="exam-settings__hint exam-settings__hint--top">
            用于 LLM / Embedding API 及 Hugging Face 模型下载。留空表示直连。
          </p>
          <div className="exam-settings__grid">
            <Form.Item
              label="代理地址"
              name="proxy_url"
              extra="如 http://127.0.0.1:7890 或 socks5://127.0.0.1:7891"
            >
              <Input placeholder="留空不走代理" />
            </Form.Item>
            <Form.Item label="不走代理的地址" name="proxy_no_proxy">
              <Input placeholder="127.0.0.1,localhost" />
            </Form.Item>
          </div>
        </Card>

        <Card title="问答模型 (LLM)" className="exam-settings__card" size="small">
          <Form.Item
            label="API Key"
            name="llm_api_key"
            extra={
              config.llm.configured
                ? "留空表示不修改已保存的 Key"
                : "必填后才能调用模型"
            }
          >
            <Input.Password
              placeholder={config.llm.configured ? "••••••••（已配置）" : "sk-..."}
              autoComplete="off"
            />
          </Form.Item>
          <div className="exam-settings__grid">
            <Form.Item label="Base URL" name="llm_base_url" rules={[{ required: true }]}>
              <Input placeholder="https://api.openai.com/v1" />
            </Form.Item>
            <Form.Item label="模型" name="llm_model" rules={[{ required: true }]}>
              <Input placeholder="gpt-4o-mini" />
            </Form.Item>
            <Form.Item label="超时 (秒)" name="llm_timeout">
              <InputNumber min={1} max={300} style={{ width: "100%" }} />
            </Form.Item>
          </div>
        </Card>

        <Card title="向量化 (Embedding)" className="exam-settings__card" size="small">
          <Form.Item label="方式" name="embedding_provider">
            <Select
              options={[
                { value: "local", label: "本地模型 (sentence-transformers)" },
                { value: "openai", label: "远程 API (OpenAI 兼容)" },
              ]}
            />
          </Form.Item>
          <Form.Item
            label="API Key"
            name="embedding_api_key"
            extra="远程 API 可留空以回退 LLM Key；留空且不修改表示保持原值"
          >
            <Input.Password
              placeholder={
                config.embedding.configured ? "••••••••（已配置）" : "可选"
              }
              autoComplete="off"
            />
          </Form.Item>
          <div className="exam-settings__grid">
            <Form.Item label="Base URL" name="embedding_base_url">
              <Input placeholder="留空则回退 LLM Base URL" />
            </Form.Item>
            <Form.Item label="模型" name="embedding_model" rules={[{ required: true }]}>
              <Input placeholder="all-MiniLM-L6-v2" />
            </Form.Item>
            <Form.Item label="超时 (秒)" name="embedding_timeout">
              <InputNumber min={1} max={300} style={{ width: "100%" }} />
            </Form.Item>
          </div>
          {config.embedding.provider === "local" && embStatus === "not_ready" ? (
            <div className="exam-settings__actions">
              <Button loading={warming} onClick={() => void warmupEmbedding()}>
                加载本地模型
              </Button>
              {warmupError ? (
                <p className="exam-settings__error" role="alert">
                  {warmupError}
                </p>
              ) : null}
            </div>
          ) : null}
        </Card>

        <Card title="检索与分块" className="exam-settings__card" size="small">
          <div className="exam-settings__grid">
            <Form.Item label="检索条数 top_k" name="retrieval_top_k">
              <InputNumber min={1} max={100} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item label="置信度阈值" name="retrieval_score_threshold">
              <InputNumber min={0} max={1} step={0.05} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item label="分块大小" name="chunk_size">
              <InputNumber min={100} max={4000} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item label="分块重叠" name="chunk_overlap">
              <InputNumber min={0} max={500} style={{ width: "100%" }} />
            </Form.Item>
          </div>
        </Card>

        <Card title="PDF 解析" className="exam-settings__card" size="small">
          <div className="exam-settings__grid exam-settings__grid--switches">
            <Form.Item label="启用 OCR" name="pdf_use_ocr" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item label="强制 OCR" name="pdf_force_ocr" valuePropName="checked">
              <Switch />
            </Form.Item>
          </div>
          <Form.Item label="OCR 语言包" name="pdf_ocr_language">
            <Input placeholder="eng+chi_sim" />
          </Form.Item>
        </Card>

        <Card title="服务与上传" className="exam-settings__card" size="small">
          <div className="exam-settings__grid">
            <Form.Item label="监听地址" name="host" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item label="端口" name="port">
              <InputNumber min={1} max={65535} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item label="上传大小上限 (MB)" name="max_upload_mb">
              <InputNumber min={1} max={500} style={{ width: "100%" }} />
            </Form.Item>
          </div>
          <p className="exam-settings__hint">端口变更需重启服务后生效</p>
          <p className="exam-settings__hint">
            资料目录：<code>{config.storage.knowledge_dir}</code>
          </p>
        </Card>

        <div className="exam-settings__footer">
          <Button type="primary" htmlType="submit" loading={saving} size="large">
            保存配置
          </Button>
        </div>
      </Form>
    </div>
  );
}

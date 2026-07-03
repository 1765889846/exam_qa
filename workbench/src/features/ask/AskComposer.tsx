import { useId } from "react";
import { Button, Input } from "antd";
import { Button as MobileButton, Input as MobileInput } from "antd-mobile";
import { useIsMobile } from "@/lib/useMediaQuery";

interface AskComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
}

export function AskComposer({
  value,
  onChange,
  onSubmit,
  loading,
}: AskComposerProps) {
  const inputId = useId();
  const isMobile = useIsMobile();

  if (isMobile) {
    return (
      <div className="exam-ask-composer exam-ask-composer--mobile">
        <label htmlFor={inputId} className="exam-visually-hidden">
          问题
        </label>
        <MobileInput
          id={inputId}
          value={value}
          onChange={onChange}
          placeholder="输入问题，例如：傅里叶变换的时移性质…"
          disabled={loading}
          clearable
        />
        <MobileButton
          color="primary"
          loading={loading}
          onClick={onSubmit}
          block
        >
          提问
        </MobileButton>
      </div>
    );
  }

  return (
    <div className="exam-ask-composer">
      <label htmlFor={inputId} className="exam-visually-hidden">
        问题
      </label>
      <Input
        id={inputId}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="输入问题，例如：傅里叶变换的时移性质是什么…"
        onPressEnter={onSubmit}
        disabled={loading}
        size="large"
        aria-label="问题"
      />
      <Button
        type="primary"
        size="large"
        onClick={onSubmit}
        loading={loading}
      >
        提问
      </Button>
    </div>
  );
}

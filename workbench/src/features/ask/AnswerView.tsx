import { GroundedBadge } from "./GroundedBadge";
import { CitationList } from "./CitationList";
import { useKatexRender } from "@/lib/katex/useKatexRender";
import type { AskResult } from "@/lib/api/types";

interface AnswerViewProps {
  result: AskResult;
}

export function AnswerView({ result }: AnswerViewProps) {
  const ref = useKatexRender(result.answer);
  const boxClass = result.grounded
    ? "exam-answer-box"
    : "exam-answer-box exam-answer-box--ungrounded";

  return (
    <div className={boxClass}>
      <div className="exam-turn__label exam-turn__label--assistant">助手</div>
      <div ref={ref} className="exam-answer-text">
        {result.answer}
      </div>
      <div className="exam-answer-meta">
        <span>
          <span className="exam-answer-meta__label">可信度</span>{" "}
          <GroundedBadge grounded={result.grounded} />
        </span>
        <span>
          <span className="exam-answer-meta__label">引用数</span>{" "}
          {result.citations.length}
        </span>
      </div>
      <CitationList citations={result.citations} grounded={result.grounded} />
    </div>
  );
}

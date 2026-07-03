import { AnswerView } from "./AnswerView";
import type { ConversationTurn } from "./types";

interface ConversationTurnViewProps {
  turn: ConversationTurn;
}

export function ConversationTurnView({ turn }: ConversationTurnViewProps) {
  return (
    <article className="exam-turn" aria-label={`问题：${turn.question}`}>
      <div className="exam-turn__question">
        <span className="exam-turn__label">你</span>
        <p className="exam-turn__text">{turn.question}</p>
      </div>

      {turn.error && (
        <div className="exam-answer-box exam-answer-box--error">
          <p className="exam-answer-box__error-title">请求失败</p>
          <p className="exam-answer-box__error-detail">{turn.error}</p>
        </div>
      )}

      {turn.result && <AnswerView result={turn.result} />}
    </article>
  );
}

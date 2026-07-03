interface StreamingAnswerViewProps {
  text: string;
}

export function StreamingAnswerView({ text }: StreamingAnswerViewProps) {
  return (
    <div className="exam-answer-box exam-answer-box--streaming">
      <div className="exam-turn__label exam-turn__label--assistant">助手</div>
      <div className="exam-answer-text">
        {text}
        <span className="exam-stream-cursor" aria-hidden="true" />
      </div>
    </div>
  );
}

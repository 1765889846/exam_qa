import { useEffect, useRef, useState } from "react";
import { Button, Modal } from "antd";
import { AskComposer } from "./AskComposer";
import { AskProgress } from "./AskProgress";
import { ConversationTurnView } from "./ConversationTurnView";
import { StreamingAnswerView } from "./StreamingAnswerView";
import { useAsk } from "./useAsk";

export function AskPanel() {
  const [question, setQuestion] = useState("");
  const { turns, loading, activePhase, ask, clearTurns } = useAsk();
  const threadRef = useRef<HTMLDivElement>(null);

  const submit = () => {
    const q = question.trim();
    if (!q || loading) return;
    setQuestion("");
    ask(q);
  };

  const handleClear = () => {
    if (loading) return;
    Modal.confirm({
      title: "清空对话？",
      content: "将删除当前页面上的全部问答记录，不可恢复。",
      okText: "清空",
      okType: "danger",
      cancelText: "取消",
      onOk: () => clearTurns(),
    });
  };

  const completedTurns = turns.filter((t) => !t.phase && !t.streamingAnswer);
  const pendingTurn = turns.find((t) => t.phase || t.streamingAnswer);

  useEffect(() => {
    threadRef.current?.scrollTo({
      top: threadRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns.length, loading, pendingTurn?.streamingAnswer?.length]);

  const hasDocsHint = turns.length === 0;

  return (
    <>
      <div className="exam-section-title">
        <h2 className="exam-section-title__heading">问答</h2>
        {turns.length > 0 && (
          <Button
            type="text"
            size="small"
            className="exam-section-title__action"
            disabled={loading}
            onClick={handleClear}
          >
            清空对话
          </Button>
        )}
      </div>

      <div className="exam-qa-area exam-qa-area--chat">
        <p className="exam-qa-hint">
          每题独立检索，暂不支持追问；引用可点击在左侧资料库定位
        </p>

        <div ref={threadRef} className="exam-thread">
          {hasDocsHint && (
            <div className="exam-empty exam-empty--hint">
              <p>上传资料后开始提问</p>
              <p className="exam-empty__sub">
                资料入库后状态会变为「已入库」，届时再提问效果更好
              </p>
            </div>
          )}

          {completedTurns.map((turn) => (
            <ConversationTurnView key={turn.id} turn={turn} />
          ))}

          {pendingTurn && (
            <div className="exam-turn exam-turn--pending">
              <div className="exam-turn__question">
                <span className="exam-turn__label">你</span>
                <p className="exam-turn__text">{pendingTurn.question}</p>
              </div>

              {pendingTurn.streamingAnswer ? (
                <StreamingAnswerView text={pendingTurn.streamingAnswer} />
              ) : (
                activePhase && <AskProgress phase={activePhase} />
              )}
            </div>
          )}
        </div>

        <AskComposer
          value={question}
          onChange={setQuestion}
          onSubmit={submit}
          loading={loading}
        />
      </div>
    </>
  );
}

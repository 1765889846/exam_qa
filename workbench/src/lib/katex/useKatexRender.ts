import { useEffect, useRef } from "react";

const DELIMITERS = [
  { left: "$$", right: "$$", display: true },
  { left: "\\[", right: "\\]", display: true },
  { left: "\\(", right: "\\)", display: false },
  { left: "$", right: "$", display: false },
];

export function useKatexRender(content: string | undefined) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || !content || !window.renderMathInElement) return;
    window.renderMathInElement(el, { delimiters: DELIMITERS });
  }, [content]);

  return ref;
}

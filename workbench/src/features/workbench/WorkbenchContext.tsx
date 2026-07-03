import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";

interface WorkbenchContextValue {
  highlightedSource: string | null;
  setHighlightedSource: (source: string | null) => void;
  focusDocumentsPanel: () => void;
}

const WorkbenchContext = createContext<WorkbenchContextValue | null>(null);

export function WorkbenchProvider({
  children,
  onFocusDocuments,
}: {
  children: ReactNode;
  onFocusDocuments?: () => void;
}) {
  const [highlightedSource, setHighlightedSource] = useState<string | null>(
    null,
  );

  const focusDocumentsPanel = useCallback(() => {
    onFocusDocuments?.();
  }, [onFocusDocuments]);

  return (
    <WorkbenchContext.Provider
      value={{
        highlightedSource,
        setHighlightedSource,
        focusDocumentsPanel,
      }}
    >
      {children}
    </WorkbenchContext.Provider>
  );
}

export function useWorkbench(): WorkbenchContextValue {
  const ctx = useContext(WorkbenchContext);
  if (!ctx) {
    throw new Error("useWorkbench must be used within WorkbenchProvider");
  }
  return ctx;
}

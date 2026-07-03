import { useCallback, useState } from "react";
import { Tabs } from "antd-mobile";
import { DocumentsPanel } from "@/features/documents/DocumentsPanel";
import { AskPanel } from "@/features/ask/AskPanel";
import { WorkbenchProvider } from "@/features/workbench/WorkbenchContext";
import { useIsMobile } from "@/lib/useMediaQuery";

function DesktopWorkbench() {
  return (
    <div className="exam-workbench">
      <div className="exam-workbench__panel exam-workbench__panel--left">
        <DocumentsPanel />
      </div>
      <div className="exam-workbench__panel exam-workbench__panel--right">
        <AskPanel />
      </div>
    </div>
  );
}

function MobileWorkbench({
  tab,
  onTabChange,
}: {
  tab: string;
  onTabChange: (key: string) => void;
}) {
  return (
    <div className="exam-workbench exam-workbench--mobile">
      <Tabs activeKey={tab} onChange={onTabChange} className="exam-mobile-tabs">
        <Tabs.Tab title="资料" key="docs">
          <div className="exam-workbench__panel exam-workbench__panel--tab">
            <DocumentsPanel />
          </div>
        </Tabs.Tab>
        <Tabs.Tab title="问答" key="ask">
          <div className="exam-workbench__panel exam-workbench__panel--tab">
            <AskPanel />
          </div>
        </Tabs.Tab>
      </Tabs>
    </div>
  );
}

export function WorkbenchPage() {
  const isMobile = useIsMobile();
  const [mobileTab, setMobileTab] = useState("ask");

  const focusDocuments = useCallback(() => {
    if (isMobile) setMobileTab("docs");
  }, [isMobile]);

  return (
    <WorkbenchProvider onFocusDocuments={focusDocuments}>
      {isMobile ? (
        <MobileWorkbench tab={mobileTab} onTabChange={setMobileTab} />
      ) : (
        <DesktopWorkbench />
      )}
    </WorkbenchProvider>
  );
}

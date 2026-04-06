import { PreviewPanel } from "./PreviewPanel";

type ReplyLabProps = {
  previewMessage: string;
  previewPrompt: string;
  previewReply: string;
  previewBusy: boolean;
  selectedUserId: string;
  onPreviewMessageChange: (value: string) => void;
  onPreviewPrompt: () => void;
  onPreviewReply: () => void;
};

export function ReplyLab(props: ReplyLabProps) {
  return (
    <section className="panel lab-panel">
      <PreviewPanel {...props} />
    </section>
  );
}

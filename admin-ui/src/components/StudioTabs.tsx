export type StudioTab = "persona" | "memory" | "lab" | "proactive";

const TAB_OPTIONS: Array<{ id: StudioTab; label: string; description: string }> = [
  { id: "persona", label: "Persona Studio", description: "调角色气质、语感和规则。" },
  { id: "memory", label: "Memory Desk", description: "编辑单用户画像、偏好与里程碑。" },
  { id: "lab", label: "Reply Lab", description: "即时预览 prompt 和回复效果。" },
  { id: "proactive", label: "Proactive Studio", description: "配置主动找你聊天的节奏与预览。" },
];

type StudioTabsProps = {
  activeTab: StudioTab;
  onChange: (tab: StudioTab) => void;
};

export function StudioTabs({ activeTab, onChange }: StudioTabsProps) {
  return (
    <section className="tab-strip">
      {TAB_OPTIONS.map((tab) => (
        <button
          key={tab.id}
          className={tab.id === activeTab ? "tab-button active" : "tab-button"}
          onClick={() => onChange(tab.id)}
        >
          <strong>{tab.label}</strong>
          <span>{tab.description}</span>
        </button>
      ))}
    </section>
  );
}

import { useState } from "react";

type MetricSliderProps = {
  label: string;
  value: number;
  onChange: (value: number) => void;
};

export function MetricSlider({ label, value, onChange }: MetricSliderProps) {
  return (
    <label className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <input
        type="range"
        min={0}
        max={100}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}

type TagEditorProps = {
  label: string;
  items: string[];
  accent: "coral" | "mint" | "sky" | "amber";
  onChange: (items: string[]) => void;
};

export function TagEditor({ label, items, accent, onChange }: TagEditorProps) {
  const [draft, setDraft] = useState("");

  function addItem() {
    const value = draft.trim();
    if (!value) {
      return;
    }
    onChange([...items, value]);
    setDraft("");
  }

  return (
    <section className={`tag-editor ${accent}`}>
      <div className="tag-editor-header">
        <h3>{label}</h3>
        <span>{items.length} 条</span>
      </div>
      <div className="tag-list">
        {items.map((item) => (
          <button
            key={`${label}-${item}`}
            className="tag-chip"
            onClick={() => onChange(items.filter((candidate) => candidate !== item))}
          >
            {item}
          </button>
        ))}
      </div>
      <div className="inline-editor">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="输入后回车或点添加"
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              addItem();
            }
          }}
        />
        <button className="ghost-button" onClick={addItem}>
          添加
        </button>
      </div>
    </section>
  );
}

type TextListEditorProps = {
  label: string;
  items: string[];
  placeholder: string;
  onChange: (items: string[]) => void;
};

export function TextListEditor({ label, items, placeholder, onChange }: TextListEditorProps) {
  const [draft, setDraft] = useState("");

  function addItem() {
    const value = draft.trim();
    if (!value) {
      return;
    }
    onChange([...items, value]);
    setDraft("");
  }

  return (
    <section className="list-editor">
      <div className="tag-editor-header">
        <h3>{label}</h3>
        <span>{items.length} 条</span>
      </div>
      <div className="text-pill-list">
        {items.map((item, index) => (
          <div key={`${label}-${index}`} className="text-pill">
            <span>{item}</span>
            <button onClick={() => onChange(items.filter((_, itemIndex) => itemIndex !== index))}>
              删除
            </button>
          </div>
        ))}
      </div>
      <div className="inline-editor">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={placeholder}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              addItem();
            }
          }}
        />
        <button className="ghost-button" onClick={addItem}>
          新增
        </button>
      </div>
    </section>
  );
}

type KeyValueEditorProps = {
  label: string;
  items: Record<string, string>;
  keyPlaceholder: string;
  valuePlaceholder: string;
  onChange: (items: Record<string, string>) => void;
};

export function KeyValueEditor(props: KeyValueEditorProps) {
  const { label, items, keyPlaceholder, valuePlaceholder, onChange } = props;
  const [draftKey, setDraftKey] = useState("");
  const [draftValue, setDraftValue] = useState("");
  const entries = Object.entries(items);

  function addEntry() {
    const key = draftKey.trim();
    const value = draftValue.trim();
    if (!key || !value) {
      return;
    }
    onChange({
      ...items,
      [key]: value,
    });
    setDraftKey("");
    setDraftValue("");
  }

  return (
    <section className="key-value-editor">
      <div className="tag-editor-header">
        <h3>{label}</h3>
        <span>{entries.length} 条</span>
      </div>
      <div className="key-value-list">
        {entries.map(([key, value]) => (
          <div key={`${label}-${key}`} className="key-value-row">
            <input value={key} onChange={(event) => onChange(renameKey(items, key, event.target.value))} />
            <input value={value} onChange={(event) => onChange({ ...items, [key]: event.target.value })} />
            <button onClick={() => onChange(removeKey(items, key))}>删</button>
          </div>
        ))}
      </div>
      <div className="key-value-row draft-row">
        <input value={draftKey} onChange={(event) => setDraftKey(event.target.value)} placeholder={keyPlaceholder} />
        <input
          value={draftValue}
          onChange={(event) => setDraftValue(event.target.value)}
          placeholder={valuePlaceholder}
        />
        <button onClick={addEntry}>加</button>
      </div>
    </section>
  );
}

function renameKey(source: Record<string, string>, previousKey: string, nextKeyRaw: string) {
  const nextKey = nextKeyRaw.trim();
  const nextEntries: Record<string, string> = {};

  for (const [key, value] of Object.entries(source)) {
    if (key === previousKey) {
      if (nextKey) {
        nextEntries[nextKey] = value;
      }
    } else {
      nextEntries[key] = value;
    }
  }

  return nextEntries;
}

function removeKey(source: Record<string, string>, targetKey: string) {
  return Object.fromEntries(Object.entries(source).filter(([key]) => key !== targetKey));
}

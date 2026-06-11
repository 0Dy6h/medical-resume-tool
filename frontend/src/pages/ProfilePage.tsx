import { FileUp, Plus, Save, Sparkles, Trash2 } from "lucide-react";
import { useRef, useEffect, useState } from "react";
import { api } from "../lib/api";
import { demoProfile, emptyProfile } from "../lib/defaultProfile";
import type { Profile, ProfileImportResult } from "../types";

type Field = {
  key: string;
  label: string;
  area?: boolean;
};

type CollectionConfig = {
  key: keyof Profile;
  title: string;
  fields: Field[];
};

const configs: CollectionConfig[] = [
  {
    key: "education",
    title: "教育经历",
    fields: [
      { key: "school", label: "学校" },
      { key: "degree", label: "学历" },
      { key: "major", label: "专业" },
      { key: "start", label: "开始" },
      { key: "end", label: "结束" },
      { key: "highlights", label: "亮点", area: true }
    ]
  },
  {
    key: "experiences",
    title: "工作/实习经历",
    fields: [
      { key: "organization", label: "机构" },
      { key: "role", label: "角色" },
      { key: "start", label: "开始" },
      { key: "end", label: "结束" },
      { key: "highlights", label: "成果", area: true },
      { key: "skills", label: "技能", area: true }
    ]
  },
  {
    key: "projects",
    title: "科研/项目经历",
    fields: [
      { key: "name", label: "项目" },
      { key: "role", label: "角色" },
      { key: "highlights", label: "成果", area: true },
      { key: "skills", label: "技能", area: true }
    ]
  },
  {
    key: "publications",
    title: "发表论文",
    fields: [
      { key: "title", label: "标题" },
      { key: "journal", label: "期刊" },
      { key: "year", label: "年份" },
      { key: "authors", label: "作者", area: true },
      { key: "doi", label: "DOI" }
    ]
  },
  {
    key: "teaching",
    title: "教学经历",
    fields: [
      { key: "course", label: "课程" },
      { key: "role", label: "角色" },
      { key: "institution", label: "机构" },
      { key: "year", label: "年份" }
    ]
  },
  {
    key: "awards",
    title: "获奖荣誉",
    fields: [
      { key: "name", label: "奖项" },
      { key: "issuer", label: "颁发机构" },
      { key: "year", label: "年份" },
      { key: "level", label: "级别" }
    ]
  },
  {
    key: "certificates",
    title: "证书资质",
    fields: [
      { key: "name", label: "证书" },
      { key: "issuer", label: "机构" },
      { key: "year", label: "年份" }
    ]
  },
  {
    key: "skills",
    title: "技能能力",
    fields: [{ key: "name", label: "技能" }]
  },
  {
    key: "languages",
    title: "语言能力",
    fields: [
      { key: "name", label: "语言" },
      { key: "level", label: "水平" }
    ]
  }
];

function newId(prefix: string) {
  return `${prefix}-${Math.random().toString(16).slice(2, 8)}`;
}

function textValue(value: unknown) {
  if (Array.isArray(value)) return value.join("\n");
  return value == null ? "" : String(value);
}

function toStoredValue(value: string, area?: boolean) {
  if (!area) return value;
  return value.split(/\n+/).map((item) => item.trim()).filter(Boolean);
}

export function ProfilePage() {
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [saved, setSaved] = useState(false);
  const [preview, setPreview] = useState<ProfileImportResult | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.profile().then((payload) => setProfile({ ...emptyProfile, ...payload }));
  }, []);

  async function save() {
    await api.saveProfile(profile);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1600);
  }

  async function handleImportFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImporting(true);
    setImportError("");
    try {
      const result = await api.importProfile(file);
      const keys = new Set<string>();
      configs.forEach((config) => {
        (result[config.key as keyof ProfileImportResult] as Array<Record<string, unknown>> | undefined)?.forEach((_, index) => {
          keys.add(`${String(config.key)}-${index}`);
        });
      });
      setPreview(result);
      setSelectedKeys(keys);
    } catch (error) {
      setImportError(error instanceof Error ? error.message : "导入失败");
    } finally {
      setImporting(false);
    }
  }

  function toggleSelected(key: string) {
    setSelectedKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function confirmImport() {
    if (!preview) return;
    setProfile((current) => {
      const next = { ...current };
      configs.forEach((config) => {
        const items = (preview[config.key as keyof ProfileImportResult] as Array<Record<string, unknown>> | undefined) ?? [];
        const accepted = items
          .filter((_, index) => selectedKeys.has(`${String(config.key)}-${index}`))
          .map((item) => ({ ...item, id: newId(String(config.key)) }));
        if (accepted.length) {
          next[config.key] = [...((current[config.key] as Array<Record<string, unknown>>) ?? []), ...accepted] as never;
        }
      });
      return next;
    });
    setPreview(null);
  }

  function previewItemSummary(config: CollectionConfig, item: Record<string, unknown>) {
    return config.fields
      .map((field) => {
        const value = textValue(item[field.key]).replace(/\n/g, "；");
        return value ? `${field.label}：${value}` : "";
      })
      .filter(Boolean)
      .join(" / ");
  }

  function addItem(config: CollectionConfig) {
    setProfile((current) => ({
      ...current,
      [config.key]: [
        ...((current[config.key] as Array<Record<string, unknown>>) ?? []),
        { id: newId(String(config.key)) }
      ]
    }));
  }

  function removeItem(config: CollectionConfig, index: number) {
    setProfile((current) => ({
      ...current,
      [config.key]: (current[config.key] as Array<Record<string, unknown>>).filter((_, itemIndex) => itemIndex !== index)
    }));
  }

  function updateItem(config: CollectionConfig, index: number, field: Field, value: string) {
    setProfile((current) => {
      const items = [...(current[config.key] as Array<Record<string, unknown>>)];
      items[index] = { ...items[index], [field.key]: toStoredValue(value, field.area) };
      return { ...current, [config.key]: items };
    });
  }

  return (
    <div className="page-stack">
      <div className="toolbar">
        <div>
          <h1>我的履历</h1>
          <p className="subtle">结构化事实库</p>
        </div>
        <div className="button-row">
          <input
            ref={fileInputRef}
            type="file"
            accept=".docx"
            style={{ display: "none" }}
            onChange={handleImportFile}
          />
          <button className="icon-text-button" onClick={() => fileInputRef.current?.click()} disabled={importing}>
            <FileUp size={17} />
            {importing ? "解析中..." : "导入资料"}
          </button>
          <button className="icon-text-button" onClick={() => setProfile(demoProfile)}>
            <Sparkles size={17} />
            示例
          </button>
          <button className="primary-button" onClick={save}>
            <Save size={17} />
            {saved ? "已保存" : "保存"}
          </button>
        </div>
      </div>

      {importError && <div className="error-strip">{importError}</div>}

      {preview && (
        <section className="panel form-panel">
          <div className="panel-head">
            <h2>导入预览</h2>
            <div className="button-row">
              <button className="text-button" onClick={() => setPreview(null)}>
                取消
              </button>
              <button className="primary-button" onClick={confirmImport} disabled={selectedKeys.size === 0}>
                确认导入（{selectedKeys.size} 条）
              </button>
            </div>
          </div>
          {preview.warnings.length > 0 && (
            <div className="compact-list">
              {preview.warnings.map((warning, index) => (
                <div className="gap-card" key={index}>{warning}</div>
              ))}
            </div>
          )}
          {configs.map((config) => {
            const items = (preview[config.key as keyof ProfileImportResult] as Array<Record<string, unknown>> | undefined) ?? [];
            if (!items.length) return null;
            return (
              <div key={String(config.key)}>
                <h3>{config.title}（{items.length}）</h3>
                <div className="compact-list">
                  {items.map((item, index) => {
                    const key = `${String(config.key)}-${index}`;
                    return (
                      <label className="compact-row" key={key} style={{ cursor: "pointer" }}>
                        <input
                          type="checkbox"
                          checked={selectedKeys.has(key)}
                          onChange={() => toggleSelected(key)}
                        />
                        <span>{previewItemSummary(config, item) || "（空条目）"}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </section>
      )}

      {configs.map((config) => (
        <section className="panel form-panel" key={String(config.key)}>
          <div className="panel-head">
            <h2>{config.title}</h2>
            <button className="icon-text-button" onClick={() => addItem(config)}>
              <Plus size={17} />
              添加
            </button>
          </div>
          <div className="repeat-list">
            {((profile[config.key] as Array<Record<string, unknown>>) ?? []).map((item, index) => (
              <div className="repeat-item" key={String(item.id ?? index)}>
                <div className="repeat-fields">
                  {config.fields.map((field) => (
                    <label className={field.area ? "span-2" : ""} key={field.key}>
                      <span>{field.label}</span>
                      {field.area ? (
                        <textarea value={textValue(item[field.key])} onChange={(event) => updateItem(config, index, field, event.target.value)} />
                      ) : (
                        <input value={textValue(item[field.key])} onChange={(event) => updateItem(config, index, field, event.target.value)} />
                      )}
                    </label>
                  ))}
                </div>
                <button className="icon-button danger-button" onClick={() => removeItem(config, index)} title="删除">
                  <Trash2 size={17} />
                </button>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

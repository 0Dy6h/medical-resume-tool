import { ChevronDown, FileUp, Plus, Save, Sparkles, Trash2 } from "lucide-react";
import { useRef, useEffect, useState, useMemo } from "react";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { demoProfile, emptyProfile } from "../lib/defaultProfile";
import { mergeImportSelection } from "../lib/importMerge";
import { formatDeleteWarning, formatOverlapWarning, shouldShowDeleteWarning, shouldShowOverlapWarning } from "../lib/profileChecks";
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

type PreviewReviewItem = NonNullable<ProfileImportResult["review_items"]>[number];

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

const configByKey = new Map(configs.map((config) => [config.key, config] as const));
const collectionKeys = configs.map((config) => config.key);

const MODE_LABELS: Record<"fresh_grad" | "experienced", string> = {
  fresh_grad: "应届生",
  experienced: "职场人"
};

/**
 * Section display order and default collapsed state per profile mode.
 * Mode only affects presentation order — data is never added or removed.
 */
const MODE_LAYOUT: Record<"fresh_grad" | "experienced", { key: keyof Profile; collapsed?: boolean }[]> = {
  fresh_grad: [
    { key: "education" },
    { key: "projects" },
    { key: "experiences", collapsed: true },
    { key: "publications" },
    { key: "teaching" },
    { key: "awards" },
    { key: "certificates" },
    { key: "skills" },
    { key: "languages" }
  ],
  experienced: [
    { key: "experiences" },
    { key: "projects" },
    { key: "education" },
    { key: "publications" },
    { key: "teaching" },
    { key: "awards" },
    { key: "certificates" },
    { key: "skills" },
    { key: "languages" }
  ]
};

const BASIC_FIELDS: Field[] = [
  { key: "name", label: "姓名" },
  { key: "phone", label: "电话" },
  { key: "email", label: "邮箱" },
  { key: "intended_position", label: "求职意向" },
  { key: "location", label: "所在地" },
  { key: "summary", label: "个人简介", area: true }
];

const PREVIEW_BASICS_FIELDS: { key: string; label: string }[] = [
  { key: "name", label: "姓名" },
  { key: "phone", label: "电话" },
  { key: "email", label: "邮箱" }
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

function collectionTitle(collection: string) {
  return configByKey.get(collection as keyof Profile)?.title ?? collection;
}

/**
 * A new, empty row for a collection with every configured field present.
 *
 * The fields are spelled out rather than left absent so the row matches the
 * shape the save endpoint expects; the backend drops rows that stay blank.
 */
function blankItem(config: CollectionConfig): Record<string, unknown> {
  const item: Record<string, unknown> = { id: newId(String(config.key)) };
  for (const field of config.fields) {
    item[field.key] = field.area ? [] : "";
  }
  return item;
}

export function ProfilePage() {
  const toast = useToast();
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [saved, setSaved] = useState(false);
  const [preview, setPreview] = useState<ProfileImportResult | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [previewBasics, setPreviewBasics] = useState<Record<string, string>>({});
  const [importing, setImporting] = useState(false);
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set());
  const [deleteConfirm, setDeleteConfirm] = useState<{ config: CollectionConfig; index: number; count: number } | null>(null);
  const [overlapConfirm, setOverlapConfirm] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const currentMode: "fresh_grad" | "experienced" = profile.mode ?? "experienced";

  const orderedConfigs = useMemo(() => {
    const layout = MODE_LAYOUT[currentMode];
    return layout.map((item) => {
      const config = configByKey.get(item.key);
      return config ? { config, defaultCollapsed: item.collapsed ?? false } : null;
    }).filter((item): item is { config: CollectionConfig; defaultCollapsed: boolean } => item !== null);
  }, [currentMode]);

  useEffect(() => {
    api.profile().then((payload) => {
      const loaded = { ...emptyProfile, ...payload };
      setProfile(loaded);
      // Set initial collapsed state based on loaded mode
      const mode = loaded.mode ?? "experienced";
      const layout = MODE_LAYOUT[mode as "fresh_grad" | "experienced"];
      const collapsed = new Set<string>();
      layout.forEach((item) => {
        if (item.collapsed) collapsed.add(String(item.key));
      });
      setCollapsedSections(collapsed);
    });
  }, []);

  function toggleSection(key: string) {
    setCollapsedSections((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function switchMode(mode: "fresh_grad" | "experienced") {
    setProfile((current) => ({ ...current, mode }));
    // Reset collapsed state to mode defaults — never touches data
    const layout = MODE_LAYOUT[mode];
    const collapsed = new Set<string>();
    layout.forEach((item) => {
      if (item.collapsed) collapsed.add(String(item.key));
    });
    setCollapsedSections(collapsed);
  }

  async function save() {
    try {
      const result = await api.checkOverlap(profile);
      if (shouldShowOverlapWarning(result)) {
        setOverlapConfirm(true);
        return;
      }
    } catch {
      // If the overlap check fails, proceed with save directly
    }
    await doSave();
  }

  async function doSave() {
    try {
      await api.saveProfile(profile);
      setSaved(true);
      toast.success("履历已保存");
      window.setTimeout(() => setSaved(false), 1600);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存失败");
    }
  }

  async function handleImportFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImporting(true);
    try {
      const result = await api.importProfile(file);
      const keys = new Set<string>();
      configs.forEach((config) => {
        (result[config.key as keyof ProfileImportResult] as Array<Record<string, unknown>> | undefined)?.forEach((_, index) => {
          keys.add(`${String(config.key)}-${index}`);
        });
      });
      const reviewCount = result.review_items?.length ?? 0;
      setPreview(result);
      setSelectedKeys(keys);
      setPreviewBasics(result.basics ?? {});
      if (keys.size === 0 && reviewCount === 0) {
        toast.info("未识别出可导入的条目，请检查文档结构");
      } else if (keys.size === 0 && reviewCount > 0) {
        toast.info("有待确认条目，请在预览中勾选后导入");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "导入失败");
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
    const { profile: merged, accepted } = mergeImportSelection(
      profile,
      preview,
      selectedKeys,
      collectionKeys,
      newId,
      previewBasics
    );
    setProfile(merged);
    setPreview(null);
    toast.success(`已导入 ${accepted} 条，请检查后保存`);
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
        blankItem(config)
      ]
    }));
  }

  async function removeItem(config: CollectionConfig, index: number) {
    const items = profile[config.key] as Array<Record<string, unknown>>;
    const item = items[index];
    const itemId = String(item?.id ?? "");
    if (!itemId) {
      doRemoveItem(config, index);
      return;
    }
    try {
      const result = await api.checkFieldReferences(itemId);
      if (shouldShowDeleteWarning(result)) {
        setDeleteConfirm({ config, index, count: result.count });
        return;
      }
    } catch {
      // If the reference check fails, proceed with delete
    }
    doRemoveItem(config, index);
  }

  function doRemoveItem(config: CollectionConfig, index: number) {
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

  function updateBasics(key: string, value: string) {
    setProfile((current) => ({ ...current, basics: { ...(current.basics ?? {}), [key]: value } }));
  }

  function updatePreviewBasics(key: string, value: string) {
    setPreviewBasics((current) => ({ ...current, [key]: value }));
  }

  return (
    <div className="page-stack">
      <div className="toolbar">
        <div>
          <h1>我的履历</h1>
          <p className="subtle">结构化事实库 · 当前模式：{MODE_LABELS[currentMode]}</p>
        </div>
        <div className="button-row">
          <div className="mode-switch" role="tablist" aria-label="履历模式">
            <button
              role="tab"
              aria-selected={currentMode === "fresh_grad"}
              className={currentMode === "fresh_grad" ? "mode-tab active" : "mode-tab"}
              onClick={() => switchMode("fresh_grad")}
              title="应届生：教育/科研优先，工作经历折叠"
            >
              应届生
            </button>
            <button
              role="tab"
              aria-selected={currentMode === "experienced"}
              className={currentMode === "experienced" ? "mode-tab active" : "mode-tab"}
              onClick={() => switchMode("experienced")}
              title="职场人：工作/成果优先，教育退居次要"
            >
              职场人
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".docx,.pdf,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff"
            style={{ display: "none" }}
            onChange={handleImportFile}
          />
          <button
            className="icon-text-button"
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
            title="支持 DOCX、PDF、TXT、Markdown 和常见图片"
          >
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
          {preview.basics && Object.keys(preview.basics).length > 0 && (
            <div>
              <h3>基本信息</h3>
              <div className="repeat-fields">
                {PREVIEW_BASICS_FIELDS.map((field) => (
                  <label key={field.key}>
                    <span>{field.label}</span>
                    <input
                      value={previewBasics[field.key] ?? ""}
                      onChange={(event) => updatePreviewBasics(field.key, event.target.value)}
                    />
                  </label>
                ))}
              </div>
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
          {(preview.review_items ?? []).length > 0 && (
            <div>
              <h3>待确认（{preview.review_items?.length ?? 0}）</h3>
              <div className="compact-list">
                {preview.review_items?.map((item: PreviewReviewItem, index) => {
                  const key = `review-${index}`;
                  const config = configByKey.get(item.collection as keyof Profile);
                  return (
                    <label className="compact-row review-row" key={key}>
                      <input
                        type="checkbox"
                        checked={selectedKeys.has(key)}
                        onChange={() => toggleSelected(key)}
                      />
                      <div className="review-content">
                        <div className="review-header">
                          <strong>{collectionTitle(item.collection)}</strong>
                          <span className="review-confidence">置信度 {item.confidence.toFixed(2)}</span>
                        </div>
                        <div className="review-summary">{previewItemSummary(config ?? configs[0], item.item) || "（空条目）"}</div>
                        <div className="review-source">{item.source_text}</div>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>
          )}
          {(preview.unassigned_blocks ?? []).length > 0 && (
            <details className="unassigned-blocks">
              <summary>未归类原文（{preview.unassigned_blocks?.length ?? 0}）</summary>
              <div className="compact-list">
                {preview.unassigned_blocks?.map((block, index) => (
                  <div className="gap-card" key={`${block.text}-${index}`}>
                    {block.text}
                  </div>
                ))}
              </div>
            </details>
          )}
        </section>
      )}

      <section className="panel form-panel">
        <div className="panel-head">
          <h2>个人信息</h2>
          <span className="subtle">用于简历抬头（姓名 / 联系方式）</span>
        </div>
        <div className="repeat-fields">
          {BASIC_FIELDS.map((field) => (
            <label className={field.area ? "span-2" : ""} key={field.key}>
              <span>{field.label}</span>
              {field.area ? (
                <textarea
                  value={String(profile.basics?.[field.key] ?? "")}
                  onChange={(event) => updateBasics(field.key, event.target.value)}
                />
              ) : (
                <input
                  value={String(profile.basics?.[field.key] ?? "")}
                  onChange={(event) => updateBasics(field.key, event.target.value)}
                />
              )}
            </label>
          ))}
        </div>
      </section>

      {orderedConfigs.map(({ config }) => {
        const isCollapsed = collapsedSections.has(String(config.key));
        const items = (profile[config.key] as Array<Record<string, unknown>>) ?? [];
        return (
          <section className="panel form-panel" key={String(config.key)}>
            <div className="panel-head collapsible-head" onClick={() => toggleSection(String(config.key))}>
              <h2>
                {config.title}
                <ChevronDown
                  size={16}
                  className={`chevron ${isCollapsed ? "collapsed" : ""}`}
                />
              </h2>
              {!isCollapsed && (
                <button
                  className="icon-text-button"
                  onClick={(e) => { e.stopPropagation(); addItem(config); }}
                >
                  <Plus size={17} />
                  添加
                </button>
              )}
            </div>
            {!isCollapsed && (
              <div className="repeat-list">
                {items.map((item, index) => (
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
            )}
          </section>
        );
      })}

      {deleteConfirm && (
        <div className="dialog-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="dialog small" onClick={(e) => e.stopPropagation()}>
            <div className="dialog-header">
              <h2>确认删除</h2>
            </div>
            <div className="dialog-body">
              <p className="subtle">{formatDeleteWarning(deleteConfirm.count)}</p>
            </div>
            <div className="dialog-actions">
              <button className="text-button" onClick={() => setDeleteConfirm(null)}>
                取消
              </button>
              <button
                className="primary-button"
                onClick={() => {
                  doRemoveItem(deleteConfirm.config, deleteConfirm.index);
                  setDeleteConfirm(null);
                }}
              >
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}

      {overlapConfirm && (
        <div className="dialog-overlay" onClick={() => setOverlapConfirm(false)}>
          <div className="dialog small" onClick={(e) => e.stopPropagation()}>
            <div className="dialog-header">
              <h2>时间重叠提示</h2>
            </div>
            <div className="dialog-body">
              <p className="subtle">{formatOverlapWarning()}</p>
            </div>
            <div className="dialog-actions">
              <button className="text-button" onClick={() => setOverlapConfirm(false)}>
                取消
              </button>
              <button
                className="primary-button"
                onClick={() => {
                  setOverlapConfirm(false);
                  void doSave();
                }}
              >
                继续保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

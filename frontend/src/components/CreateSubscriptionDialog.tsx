import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { validateSubscriptionForm, hasBroadKeywordWarning } from "../lib/subscriptionUtils";
import type { Institution, Subscription } from "../types";

export function CreateSubscriptionDialog({
  institutions,
  onClose,
  onCreated
}: {
  institutions: Institution[];
  onClose: () => void;
  onCreated: (sub: Subscription) => void;
}) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [keyword, setKeyword] = useState("");
  const [selectedIds, setSelectedIds] = useState<number[]>(
    institutions.filter((i) => i.enabled).slice(0, 12).map((i) => i.id)
  );
  const [submitting, setSubmitting] = useState(false);
  const [createdSub, setCreatedSub] = useState<Subscription | null>(null);
  const [showWarning, setShowWarning] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const enabledInstitutions = institutions.filter((i) => i.enabled);

  function toggleInstitution(id: number) {
    setSelectedIds((current) =>
      current.includes(id)
        ? current.filter((i) => i !== id)
        : current.length < 12
          ? [...current, id]
          : current
    );
  }

  function selectAllEnabled() {
    setSelectedIds(enabledInstitutions.slice(0, 12).map((i) => i.id));
  }

  function clearSelection() {
    setSelectedIds([]);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const error = validateSubscriptionForm({
      name,
      keyword,
      institutionIds: selectedIds
    });
    if (error) {
      toast.error(error);
      return;
    }

    setSubmitting(true);
    try {
      const sub = await api.createSubscription({
        name: name.trim(),
        keyword: keyword.trim(),
        institution_ids: selectedIds
      });

      if (hasBroadKeywordWarning(sub.warning)) {
        setCreatedSub(sub);
        setShowWarning(true);
        setSubmitting(false);
        return;
      }

      onCreated(sub);
      onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "创建订阅失败");
    } finally {
      setSubmitting(false);
    }
  }

  function handleAcknowledgeWarning() {
    if (createdSub) {
      onCreated(createdSub);
    }
    onClose();
  }

  const error = validateSubscriptionForm({ name, keyword, institutionIds: selectedIds });

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <h2>新建订阅</h2>
          <button className="icon-button" onClick={onClose} title="关闭">
            <X size={18} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="dialog-body">
          <div className="form-field">
            <label>订阅名称</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：内科临床岗位"
              maxLength={30}
            />
            <span className="field-hint">{name.length}/30</span>
          </div>
          <div className="form-field">
            <label>关键词</label>
            <input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="例如：内科、护理、科研"
              maxLength={50}
            />
            <span className="field-hint">{keyword.length}/50 · 匹配职位标题、机构、内容</span>
          </div>
          <div className="form-field">
            <div className="field-row">
              <label>目标机构</label>
              <div className="field-actions">
                <button type="button" className="text-button" onClick={selectAllEnabled}>
                  全选启用
                </button>
                <button type="button" className="text-button" onClick={clearSelection}>
                  清空
                </button>
              </div>
            </div>
            <div className="institution-grid">
              {enabledInstitutions.map((inst) => (
                <label key={inst.id} className="institution-check">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(inst.id)}
                    onChange={() => toggleInstitution(inst.id)}
                    disabled={!selectedIds.includes(inst.id) && selectedIds.length >= 12}
                  />
                  <span>{inst.name}</span>
                </label>
              ))}
            </div>
            <span className="field-hint">
              已选 {selectedIds.length}/12 家
            </span>
          </div>
          <div className="dialog-actions">
            <button type="button" className="secondary-button" onClick={onClose} disabled={submitting}>
              取消
            </button>
            <button type="submit" className="primary-button" disabled={submitting || !!error}>
              {submitting ? "创建中…" : "创建订阅"}
            </button>
          </div>
        </form>

        {showWarning && (
          <div className="dialog-overlay" onClick={() => setShowWarning(false)}>
            <div className="dialog small" onClick={(e) => e.stopPropagation()}>
              <div className="dialog-header">
                <h3>订阅已创建</h3>
              </div>
              <div className="dialog-body">
                <p className="warning-text">{createdSub?.warning}</p>
                <p>订阅已创建，您可以在「我的订阅」中查看。</p>
              </div>
              <div className="dialog-actions">
                <button
                  type="button"
                  className="primary-button"
                  onClick={handleAcknowledgeWarning}
                >
                  知道了
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

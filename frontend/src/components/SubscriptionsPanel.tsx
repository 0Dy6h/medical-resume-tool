import { Bell, BellPlus, CheckCheck, Trash2, AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";
import { useToast } from "./Toast";
import { api } from "../lib/api";
import { subscriptionSubtitle, countMaintenanceInstitutions } from "../lib/subscriptionUtils";
import type { Subscription, Institution } from "../types";
import { CreateSubscriptionDialog } from "./CreateSubscriptionDialog";

export function SubscriptionsPanel({
  institutions,
  isLoggedIn
}: {
  institutions: Institution[];
  isLoggedIn: boolean;
}) {
  const toast = useToast();
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [markingId, setMarkingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  async function refresh() {
    if (!isLoggedIn) return;
    setLoading(true);
    try {
      const subs = await api.subscriptions();
      setSubscriptions(subs);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "加载订阅失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (isLoggedIn) {
      void refresh();
    } else {
      setSubscriptions([]);
    }
  }, [isLoggedIn]);

  function handleCreated(sub: Subscription) {
    setSubscriptions((current) => [sub, ...current]);
    toast.success("订阅创建成功");
  }

  async function handleMarkRead(id: number) {
    setMarkingId(id);
    try {
      const updated = await api.markSubscriptionRead(id);
      setSubscriptions((current) =>
        current.map((s) => (s.id === id ? updated : s))
      );
      toast.success("已标记为已读");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "操作失败");
    } finally {
      setMarkingId(null);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("确定要删除此订阅吗？")) return;
    setDeletingId(id);
    try {
      await api.deleteSubscription(id);
      setSubscriptions((current) => current.filter((s) => s.id !== id));
      toast.success("订阅已删除");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="subscriptions-panel">
      <div className="panel-header">
        <div>
          <h2>我的订阅</h2>
          <p className="subtle">
            {subscriptions.length > 0
              ? `${subscriptions.length} 个订阅`
              : "暂无订阅"}
          </p>
        </div>
        {isLoggedIn && (
          <button
            className="icon-text-button compact"
            onClick={() => setShowCreateDialog(true)}
            title="新建订阅"
          >
            <BellPlus size={16} />
            新建
          </button>
        )}
      </div>

      <div className="subscription-list">
        {loading && subscriptions.length === 0 && (
          <div className="empty-state">加载中…</div>
        )}
        {!loading && subscriptions.length === 0 && isLoggedIn && (
          <div className="empty-state">
            <Bell size={24} />
            <p>还没有订阅</p>
            <p className="subtle small">点击「新建」关注感兴趣的岗位</p>
          </div>
        )}
        {!isLoggedIn && (
          <div className="empty-state">
            <Bell size={24} />
            <p>登录后使用订阅</p>
          </div>
        )}
        {subscriptions.map((sub) => {
          const maintenanceCount = countMaintenanceInstitutions(sub.institution_statuses);
          return (
            <div key={sub.id} className="subscription-card">
              <div className="subscription-card-header">
                <h3>{sub.name}</h3>
                <button
                  className="icon-button subtle"
                  onClick={() => void handleDelete(sub.id)}
                  disabled={deletingId === sub.id}
                  title="删除订阅"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <p className="subscription-keyword">关键词：{sub.keyword}</p>
              <p className="subscription-subtitle">
                {sub.new_count > 0 && <span className="new-badge">{sub.new_count} 条新</span>}
                {subscriptionSubtitle(sub)}
              </p>
              {maintenanceCount > 0 && (
              <p className="maintenance-note">
                <AlertTriangle size={12} />
                {maintenanceCount} 家机构维护中 · 暂停推送
              </p>
            )}
              <div className="subscription-card-actions">
                <button
                  className="text-button"
                  onClick={() => void handleMarkRead(sub.id)}
                  disabled={markingId === sub.id || sub.new_count === 0}
                >
                  <CheckCheck size={14} />
                  {markingId === sub.id ? "处理中…" : "检查更新"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {showCreateDialog && (
        <CreateSubscriptionDialog
          institutions={institutions}
          onClose={() => setShowCreateDialog(false)}
          onCreated={handleCreated}
        />
      )}
    </div>
  );
}

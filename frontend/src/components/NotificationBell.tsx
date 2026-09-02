import { Bell, CheckCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { formatDate } from "../lib/format";
import type { NotificationItem } from "../types";

/**
 * 顶栏通知铃铛（B2 订阅触达）：未读角标 + 下拉通知面板。
 * 订阅扫描产生新岗位时写入通知，用户在此查看摘要并标记已读。
 */
export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  async function load() {
    try {
      const [list, count] = await Promise.all([api.notifications(20), api.unreadCount()]);
      setItems(list);
      setUnread(count.count);
    } catch {
      // 通知加载失败不打断主流程，角标保持现状
    }
  }

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next) {
      setLoading(true);
      await load();
      setLoading(false);
    }
  }

  async function markRead(item: NotificationItem) {
    if (item.read) return;
    try {
      await api.markNotificationRead(item.id);
      await load();
    } catch {
      // 标记失败保持未读，用户可重试
    }
  }

  async function markAll() {
    try {
      await api.markAllNotificationsRead();
      await load();
    } catch {
      // 同上
    }
  }

  return (
    <div className="notif-bell" ref={rootRef}>
      <button
        className="icon-button"
        onClick={toggle}
        aria-label={unread > 0 ? `通知，${unread} 条未读` : "通知"}
        title="订阅通知"
      >
        <Bell size={18} />
        {unread > 0 && <span className="notif-badge">{unread > 99 ? "99+" : unread}</span>}
      </button>
      {open && (
        <div className="notif-panel" role="dialog" aria-label="订阅通知">
          <div className="notif-head">
            <strong>订阅通知</strong>
            {unread > 0 && (
              <button className="text-button" onClick={markAll}>
                <CheckCheck size={14} /> 全部已读
              </button>
            )}
          </div>
          <div className="notif-list">
            {loading && items.length === 0 && <p className="notif-empty">加载中…</p>}
            {!loading && items.length === 0 && (
              <p className="notif-empty">
                暂无通知。订阅扫描发现新岗位时会在这里提示（每日自动扫描，也可在订阅面板手动触发）。
              </p>
            )}
            {items.map((item) => (
              <button
                className={item.read ? "notif-item" : "notif-item unread"}
                key={item.id}
                onClick={() => markRead(item)}
                title={item.read ? "已读" : "点击标记已读"}
              >
                <div className="notif-item-head">
                  <strong>{item.subscription_name}</strong>
                  <span className="notif-time">{formatDate(item.created_at)}</span>
                </div>
                <p className="notif-summary">
                  关键词「{item.keyword}」新增 {item.job_count} 条：{item.summary}
                </p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

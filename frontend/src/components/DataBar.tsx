import { AnimatedNumber } from "./AnimatedNumber";
import { maxCount } from "../lib/format";

type DataBarProps = {
  title: string;
  items: Array<{ name: string; count: number }>;
};

export function DataBar({ title, items }: DataBarProps) {
  const max = maxCount(items);
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{title}</h2>
      </div>
      <div className="bar-list stagger-children">
        {items.length === 0 ? (
          <div className="empty-line">暂无数据</div>
        ) : (
          items.slice(0, 10).map((item) => (
            <div className="bar-row" key={`${title}-${item.name}`}>
              <span className="bar-name">{item.name}</span>
              <div className="bar-track">
                <span className="bar-fill" style={{ width: `${Math.max(8, (item.count / max) * 100)}%` }} />
              </div>
              {/* B5: Animated number for bar count */}
              <span className="bar-count"><AnimatedNumber value={item.count} /></span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

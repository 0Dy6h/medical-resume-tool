import { statusLabel, statusTone } from "../lib/status";

type StatusPillProps = {
  value?: string | null;
};

export function StatusPill({ value }: StatusPillProps) {
  const status = value ?? "never";
  return <span className={`status ${statusTone(status)}`}>{statusLabel(status)}</span>;
}

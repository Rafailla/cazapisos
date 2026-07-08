import { formatRelativeTime } from "@/lib/relativeTime";
import type { PlatformStatusRow } from "./types";

type Status = "sin-revisar" | "novedades" | "sin-novedades";

function statusOf(platform: PlatformStatusRow): Status {
  if (!platform.last_checked_at) return "sin-revisar";
  return (platform.last_run_new_count ?? 0) > 0 ? "novedades" : "sin-novedades";
}

function StatusIcon({ status }: { status: Status }) {
  if (status === "sin-revisar") {
    return (
      <svg className="platform-status-icon" viewBox="0 0 16 16" aria-hidden="true">
        <circle cx="8" cy="8" r="5" fill="var(--muted)" />
      </svg>
    );
  }

  const color = status === "novedades" ? "var(--accent)" : "var(--muted)";
  return (
    <svg className="platform-status-icon" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" fill="none" stroke={color} strokeWidth="1.5" />
      <path
        d="M4.5 8.2l2.2 2.2 4.8-4.8"
        fill="none"
        stroke={color}
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const STATUS_LABEL: Record<Status, string> = {
  "sin-revisar": "Aún no revisado",
  novedades: "Novedades encontradas",
  "sin-novedades": "Revisado, sin novedades",
};

export default function PlatformStatus({ platforms }: { platforms: PlatformStatusRow[] }) {
  return (
    <section className="card platform-status">
      <h2>Estado de las plataformas</h2>
      <ul className="platform-status-list">
        {platforms.map((platform) => {
          const status = statusOf(platform);
          return (
            <li key={platform.id} className="platform-status-item">
              <StatusIcon status={status} />
              <span className="platform-status-name">{platform.name}</span>
              <span className="platform-status-time" title={STATUS_LABEL[status]}>
                {platform.last_checked_at ? formatRelativeTime(platform.last_checked_at) : "aún no revisado"}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

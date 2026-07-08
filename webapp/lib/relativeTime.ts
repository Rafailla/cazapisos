export function formatRelativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60000);

  if (minutes < 1) return "hace un momento";
  if (minutes < 60) return `hace ${minutes} minuto${minutes === 1 ? "" : "s"}`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours} hora${hours === 1 ? "" : "s"}`;

  const days = Math.floor(hours / 24);
  return `hace ${days} día${days === 1 ? "" : "s"}`;
}

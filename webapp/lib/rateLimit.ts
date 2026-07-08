import "server-only";

export const SEARCH_COOLDOWN_HOURS = 16;

export type SearchAvailability = {
  canSearch: boolean;
  hoursSinceLast: number | null;
  hoursRemaining: number;
};

export function evaluateSearchAvailability(lastExecutedAt: string | null): SearchAvailability {
  if (!lastExecutedAt) {
    return { canSearch: true, hoursSinceLast: null, hoursRemaining: 0 };
  }

  const hoursSinceLast = (Date.now() - new Date(lastExecutedAt).getTime()) / (1000 * 60 * 60);
  const hoursRemaining = Math.max(0, SEARCH_COOLDOWN_HOURS - hoursSinceLast);

  return {
    canSearch: hoursSinceLast >= SEARCH_COOLDOWN_HOURS,
    hoursSinceLast,
    hoursRemaining,
  };
}

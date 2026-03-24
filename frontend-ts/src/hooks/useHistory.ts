import { useEffect, useState } from "react";
import { buildHistoryUrl } from "../lib/api";
import type { BackendHistoryItem } from "../lib/types";

interface HistoryResponse {
  status?: string;
  data?: BackendHistoryItem[];
}

export function useHistory(enabled: boolean) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<BackendHistoryItem[]>([]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let isCancelled = false;

    async function loadHistory() {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(buildHistoryUrl());
        const payload = (await response.json()) as HistoryResponse;

        if (isCancelled) {
          return;
        }

        if (payload.status === "success" && Array.isArray(payload.data)) {
          const sorted = [...payload.data].sort(
            (left, right) =>
              new Date(right.metadata.timestamp).getTime() - new Date(left.metadata.timestamp).getTime(),
          );

          setItems(sorted);
          return;
        }

        setItems([]);
      } catch {
        if (!isCancelled) {
          setError("Error loading history. Is the backend running?");
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadHistory();

    return () => {
      isCancelled = true;
    };
  }, [enabled]);

  return {
    error,
    isLoading,
    items,
  };
}

import { useEffect, useRef } from "react";
import { ColorType, createChart, type CandlestickData } from "lightweight-charts";
import { buildChartUrl } from "../lib/api";

interface ChartApiResponse {
  status?: string;
  message?: string;
  data?: CandlestickData[];
}

export function PriceChart({ asOf, ticker }: { asOf?: string; ticker: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;

    if (!container) {
      return;
    }

    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;
    let chart: ReturnType<typeof createChart> | null = null;

    async function loadChart() {
      container.innerHTML = '<div style="padding:1rem;color:var(--text-secondary);font-size:0.85rem;">Loading chart...</div>';

      try {
        const response = await fetch(buildChartUrl(ticker, asOf));
        const payload = (await response.json()) as ChartApiResponse;

        if (cancelled) {
          return;
        }

        if (payload.status !== "success" || !Array.isArray(payload.data)) {
          throw new Error(payload.message || "Chart API error");
        }

        container.innerHTML = "";
        chart = createChart(container, {
          grid: { horzLines: { color: "#334155" }, vertLines: { color: "#334155" } },
          height: 300,
          layout: {
            background: { color: "#1e293b", type: ColorType.Solid },
            textColor: "#d1d5db",
          },
        });

        const series = chart.addCandlestickSeries({
          borderDownColor: "#ef4444",
          borderUpColor: "#10b981",
          downColor: "#ef4444",
          upColor: "#10b981",
          wickDownColor: "#ef4444",
          wickUpColor: "#10b981",
        });

        series.setData(payload.data);

        if (asOf && payload.data.length > 0) {
          series.setMarkers([
            {
              color: "#3b82f6",
              position: "aboveBar",
              shape: "arrowDown",
              text: "Analysis Date",
              time: asOf as CandlestickData["time"],
            },
          ]);
        }

        chart.timeScale().fitContent();
        resizeObserver = new ResizeObserver((entries) => {
          for (const entry of entries) {
            chart?.applyOptions({ width: entry.contentRect.width });
          }
        });
        resizeObserver.observe(container);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Chart unavailable";
        container.innerHTML = `<p class="notice">Chart unavailable: ${message}</p>`;
      }
    }

    void loadChart();

    return () => {
      cancelled = true;
      resizeObserver?.disconnect();
      chart?.remove();
    };
  }, [asOf, ticker]);

  return <div className="chart-card" ref={containerRef} />;
}

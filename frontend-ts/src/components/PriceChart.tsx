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
      container.classList.remove("chart-card-error");
      container.classList.add("chart-card-loading");
      container.innerHTML = '<div class="chart-state">Loading chart...</div>';

      try {
        const response = await fetch(buildChartUrl(ticker, asOf));
        const payload = (await response.json()) as ChartApiResponse;

        if (cancelled) {
          return;
        }

        if (payload.status !== "success" || !Array.isArray(payload.data)) {
          throw new Error(payload.message || "Chart API error");
        }

        container.classList.remove("chart-card-error", "chart-card-loading");
        container.innerHTML = "";
        chart = createChart(container, {
          grid: { horzLines: { color: "#e2e8f0" }, vertLines: { color: "#eef2ff" } },
          height: 300,
          layout: {
            background: { color: "#ffffff", type: ColorType.Solid },
            textColor: "#64748b",
          },
          rightPriceScale: {
            borderColor: "#e2e8f0",
          },
          timeScale: {
            borderColor: "#e2e8f0",
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
        container.classList.remove("chart-card-loading");
        container.classList.add("chart-card-error");
        container.innerHTML = `<p class="chart-state chart-state-error">Chart unavailable: ${message}</p>`;
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

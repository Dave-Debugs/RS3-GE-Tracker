import { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts";
import type { ChartMode, PriceSeries } from "../types";
import { formatDateTime, formatGP, formatGPExact, formatPct } from "../lib/format";

const PALETTE = [
  "#e8b64c", "#5ec8e5", "#e06c75", "#98c379", "#c678dd",
  "#d19a66", "#61afef", "#56b6c2", "#f2777a", "#a7c080",
];

interface Props {
  series: PriceSeries[];
  mode: ChartMode;
  showVolume: boolean;
  showHighLow: boolean;
  maKeys: string[];
  dark: boolean;
  onToggleItem?: (itemId: number) => void;
  onFocusItem?: (itemId: number) => void;
}

export default function PriceChart({
  series,
  mode,
  showVolume,
  showHighLow,
  maKeys,
  dark,
  onToggleItem,
  onFocusItem,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  const hasData = series.length > 0 && series.some((s) => s.points && s.points.length > 0);

  const option = useMemo(() => {
    return buildOption(series, mode, showVolume, showHighLow, maKeys, dark);
  }, [series, mode, showVolume, showHighLow, maKeys, dark]);

  useEffect(() => {
    if (!ref.current) return;
    if (!chartRef.current) {
      chartRef.current = echarts.init(ref.current);
    }

    if (hasData) {
      chartRef.current.setOption(option, { notMerge: true });
      chartRef.current.resize();
    } else {
      chartRef.current.clear();
    }

    const ro = new ResizeObserver(() => {
      chartRef.current?.resize();
    });
    ro.observe(ref.current);

    const t = setTimeout(() => {
      chartRef.current?.resize();
    }, 50);

    return () => {
      clearTimeout(t);
      ro.disconnect();
    };
  }, [option, hasData]);

  useEffect(() => {
    return () => {
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  return (
    <div className="chart-wrapper" style={{ display: "flex", flexDirection: "column", gap: "8px", position: "relative" }}>
      {hasData && series.length > 1 && (
        <div className="chart-legend-chips">
          {series.map((s, i) => {
            const color = PALETTE[i % PALETTE.length];
            return (
              <span
                key={s.item_id}
                className="chart-chip"
                onClick={() => onFocusItem && onFocusItem(s.item_id)}
                title={`Click to focus ${s.name}`}
              >
                <span className="chip-dot" style={{ background: color }} />
                <span className="chip-label">{s.name}</span>
                {onToggleItem && (
                  <button
                    type="button"
                    className="chip-remove"
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleItem(s.item_id);
                    }}
                    title="Hide from chart"
                  >
                    ✕
                  </button>
                )}
              </span>
            );
          })}
        </div>
      )}

      {!hasData && (
        <div className="chart-empty" style={{ position: "absolute", inset: 0, zIndex: 10 }}>
          <div>
            <p className="chart-empty-title">No price data to display yet</p>
            <p className="chart-empty-sub">
              Select items from your watchlist below or click any Top Mover to load chart history.
            </p>
          </div>
        </div>
      )}

      <div ref={ref} className="chart-canvas" style={{ opacity: hasData ? 1 : 0.15 }} />
    </div>
  );
}

function buildOption(
  seriesData: PriceSeries[],
  mode: ChartMode,
  showVolume: boolean,
  showHighLow: boolean,
  maKeys: string[],
  dark: boolean
): echarts.EChartsOption {
  const fg = dark ? "#c9cdd6" : "#2d3138";
  const grid = dark ? "#2a2f3a" : "#e2e5ea";
  const single = seriesData.length === 1;

  const baselines = new Map<number, number>();
  for (const s of seriesData) {
    const first = s.points?.find((p) => p.average_price != null && p.average_price > 0);
    if (first?.average_price) baselines.set(s.item_id, first.average_price);
  }

  const val = (itemId: number, price: number | null): number | null => {
    if (price == null || isNaN(price)) return null;
    if (mode === "percent") {
      const base = baselines.get(itemId);
      return base ? +(((price - base) / base) * 100).toFixed(3) : 0;
    }
    return price;
  };

  const out: echarts.SeriesOption[] = [];
  seriesData.forEach((s, i) => {
    if (!s.points || !s.points.length) return;
    const color = PALETTE[i % PALETTE.length];
    out.push({
      name: s.name,
      type: "line",
      showSymbol: false,
      connectNulls: true,
      smooth: 0.15,
      sampling: "lttb",
      lineStyle: { width: 2, color },
      itemStyle: { color },
      emphasis: { focus: "series" },
      areaStyle:
        single && mode === "price"
          ? { opacity: 0.12, color }
          : undefined,
      data: s.points
        .filter((p) => p && p.timestamp)
        .map((p) => [p.timestamp * 1000, val(s.item_id, p.average_price)]),
    });

    if (single && showHighLow && mode === "price") {
      out.push({
        name: "Instant buy (high)",
        type: "line",
        showSymbol: false,
        connectNulls: true,
        lineStyle: { width: 1, type: "dashed", color: "#98c379" },
        itemStyle: { color: "#98c379" },
        data: s.points
          .filter((p) => p && p.timestamp)
          .map((p) => [p.timestamp * 1000, p.high_price]),
      });
      out.push({
        name: "Instant sell (low)",
        type: "line",
        showSymbol: false,
        connectNulls: true,
        lineStyle: { width: 1, type: "dashed", color: "#e06c75" },
        itemStyle: { color: "#e06c75" },
        data: s.points
          .filter((p) => p && p.timestamp)
          .map((p) => [p.timestamp * 1000, p.low_price]),
      });
    }

    if (single) {
      for (const [j, key] of maKeys.entries()) {
        const ma = s.moving_averages?.[key];
        if (!ma || !ma.length) continue;
        const maColor = ["#c678dd", "#61afef", "#d19a66", "#56b6c2"][j % 4];
        out.push({
          name: `MA ${key}`,
          type: "line",
          showSymbol: false,
          lineStyle: { width: 1.5, color: maColor, opacity: 0.9 },
          itemStyle: { color: maColor },
          data: ma
            .filter((p) => p && p.timestamp)
            .map((p) => [
              p.timestamp * 1000,
              mode === "percent" ? val(s.item_id, p.value) : p.value,
            ]),
        });
      }
    }
  });

  if (single && showVolume && seriesData[0]?.points) {
    out.push({
      name: "Volume",
      type: "bar",
      xAxisIndex: 0,
      yAxisIndex: 1,
      itemStyle: { color: dark ? "#3d4657" : "#b9c2d0", opacity: 0.7 },
      barMaxWidth: 6,
      data: seriesData[0].points
        .filter((p) => p && p.timestamp)
        .map((p) => [p.timestamp * 1000, p.volume || 0]),
    });
  }

  return {
    backgroundColor: "transparent",
    animation: false,
    textStyle: { color: fg },
    legend: { show: false },
    grid: {
      left: 80,
      right: showVolume && single ? 65 : 20,
      top: 30,
      bottom: 55,
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: dark ? "#1c202a" : "#ffffff",
      borderColor: grid,
      textStyle: { color: fg, fontSize: 12 },
      formatter: (params: any) => {
        const list = Array.isArray(params) ? params : [params];
        if (!list.length) return "";
        const ts = list[0].value[0];
        let html = `<b>${formatDateTime(ts / 1000)}</b><br/>`;
        for (const p of list) {
          if (p.value[1] == null) continue;
          const v = p.value[1];
          const text =
            p.seriesName === "Volume"
              ? Math.round(v).toLocaleString() + " traded"
              : mode === "percent" && !p.seriesName.startsWith("Instant")
              ? formatPct(v)
              : formatGPExact(v);
          html += `${p.marker} ${p.seriesName}: <b>${text}</b><br/>`;
        }
        return html;
      },
    },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    xAxis: {
      type: "time",
      axisLine: { lineStyle: { color: grid } },
      axisLabel: {
        color: fg,
        hideOverlap: true,
        formatter: (value: number) => {
          const d = new Date(value);
          const isSubDay = seriesData.some((s) => {
            if (!s.points || s.points.length < 2) return false;
            const first = s.points[0]?.timestamp || 0;
            const last = s.points[s.points.length - 1]?.timestamp || 0;
            return (last - first) <= 36 * 3600;
          });
          if (isSubDay) {
            return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
          }
          return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
        },
      },
      splitLine: { show: false },
    },
    yAxis: [
      {
        type: "value",
        scale: true,
        name: mode === "percent" ? "% Change" : "Price (GP)",
        nameTextStyle: { color: fg, fontWeight: 700, fontSize: 11, padding: [0, 0, 4, 0] },
        axisLabel: {
          color: fg,
          formatter: (v: number) => (mode === "percent" ? `${v > 0 ? "+" : ""}${v}%` : `${formatGP(v)} gp`),
        },
        splitLine: { lineStyle: { color: grid } },
      },
      {
        type: "value",
        show: showVolume && single,
        name: "Volume",
        nameTextStyle: { color: fg, fontWeight: 700, fontSize: 11, padding: [0, 0, 4, 0] },
        axisLabel: { color: fg, formatter: (v: number) => formatGP(v) },
        splitLine: { show: false },
      },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: 0, filterMode: "none" },
      {
        type: "slider",
        xAxisIndex: 0,
        height: 20,
        bottom: 6,
        left: 80,
        right: showVolume && single ? 65 : 20,
        showDetail: false,
        borderColor: grid,
        backgroundColor: dark ? "#161a22" : "#f2f4f7",
        fillerColor: dark ? "rgba(232,182,76,0.12)" : "rgba(90,120,200,0.12)",
        handleStyle: { color: "#e8b64c" },
        textStyle: { color: fg },
      },
    ],
    series: out,
  };
}

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
}

export default function PriceChart({
  series, mode, showVolume, showHighLow, maKeys, dark,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  const option = useMemo(() => buildOption(
    series, mode, showVolume, showHighLow, maKeys, dark,
  ), [series, mode, showVolume, showHighLow, maKeys, dark]);

  useEffect(() => {
    if (!ref.current) return;
    if (!chartRef.current) {
      chartRef.current = echarts.init(ref.current);
      const onResize = () => chartRef.current?.resize();
      window.addEventListener("resize", onResize);
    }
    chartRef.current.setOption(option, { notMerge: true });
  }, [option]);

  useEffect(() => () => { chartRef.current?.dispose(); chartRef.current = null; }, []);

  if (!series.length || series.every((s) => !s.points.length)) {
    return (
      <div className="chart-empty">
        <div>
          <p className="chart-empty-title">No price data to display yet</p>
          <p className="chart-empty-sub">
            Track an item and let the collector run — history builds automatically.
          </p>
        </div>
      </div>
    );
  }
  return <div ref={ref} className="chart-canvas" />;
}

function buildOption(
  seriesData: PriceSeries[], mode: ChartMode, showVolume: boolean,
  showHighLow: boolean, maKeys: string[], dark: boolean,
): echarts.EChartsOption {
  const fg = dark ? "#c9cdd6" : "#2d3138";
  const grid = dark ? "#2a2f3a" : "#e2e5ea";
  const single = seriesData.length === 1;

  const baselines = new Map<number, number>();
  for (const s of seriesData) {
    const first = s.points.find((p) => p.average_price != null);
    if (first?.average_price) baselines.set(s.item_id, first.average_price);
  }

  const val = (itemId: number, price: number | null): number | null => {
    if (price == null) return null;
    if (mode === "percent") {
      const base = baselines.get(itemId);
      return base ? +(((price - base) / base) * 100).toFixed(3) : null;
    }
    return price;
  };

  const out: echarts.SeriesOption[] = [];
  seriesData.forEach((s, i) => {
    const color = PALETTE[i % PALETTE.length];
    out.push({
      name: s.name,
      type: "line",
      showSymbol: false,
      connectNulls: true,
      smooth: 0.15,
      lineStyle: { width: 2, color },
      itemStyle: { color },
      emphasis: { focus: "series" },
      areaStyle: single && mode === "price" ? {
        opacity: 0.12, color,
      } : undefined,
      data: s.points.map((p) => [p.timestamp * 1000, val(s.item_id, p.average_price)]),
    });
    if (single && showHighLow && mode === "price") {
      out.push({
        name: "Instant buy (high)", type: "line", showSymbol: false,
        connectNulls: true, lineStyle: { width: 1, type: "dashed", color: "#98c379" },
        itemStyle: { color: "#98c379" },
        data: s.points.map((p) => [p.timestamp * 1000, p.high_price]),
      });
      out.push({
        name: "Instant sell (low)", type: "line", showSymbol: false,
        connectNulls: true, lineStyle: { width: 1, type: "dashed", color: "#e06c75" },
        itemStyle: { color: "#e06c75" },
        data: s.points.map((p) => [p.timestamp * 1000, p.low_price]),
      });
    }
    if (single) {
      for (const [j, key] of maKeys.entries()) {
        const ma = s.moving_averages[key];
        if (!ma) continue;
        const maColor = ["#c678dd", "#61afef", "#d19a66", "#56b6c2"][j % 4];
        out.push({
          name: `MA ${key}`, type: "line", showSymbol: false,
          lineStyle: { width: 1.5, color: maColor, opacity: 0.9 },
          itemStyle: { color: maColor },
          data: ma.map((p) => [
            p.timestamp * 1000,
            mode === "percent" ? val(s.item_id, p.value) : p.value,
          ]),
        });
      }
    }
  });

  if (single && showVolume) {
    out.push({
      name: "Volume", type: "bar", xAxisIndex: 0, yAxisIndex: 1,
      itemStyle: { color: dark ? "#3d4657" : "#b9c2d0", opacity: 0.7 },
      barMaxWidth: 6,
      data: seriesData[0].points.map((p) => [p.timestamp * 1000, p.volume]),
    });
  }

  return {
    backgroundColor: "transparent",
    animation: false,
    textStyle: { color: fg },
    legend: {
      top: 0, textStyle: { color: fg }, icon: "roundRect",
      itemWidth: 14, itemHeight: 3, type: "scroll",
    },
    grid: {
      left: 70, right: showVolume && single ? 70 : 24,
      top: 40, bottom: 78,
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
      axisLabel: { color: fg, hideOverlap: true },
      splitLine: { show: false },
    },
    yAxis: [
      {
        type: "value",
        scale: true,
        // keep the price window tight around the data (never forced to 0)
        min: mode === "price"
          ? (v: { min: number; max: number }) =>
              Math.floor(Math.max(0, v.min - (v.max - v.min) * 0.06))
          : undefined,
        max: mode === "price"
          ? (v: { min: number; max: number }) =>
              Math.ceil(v.max + (v.max - v.min) * 0.06)
          : undefined,
        name: mode === "percent" ? "% change" : "GP",
        nameTextStyle: { color: fg },
        axisLabel: {
          color: fg,
          formatter: (v: number) =>
            mode === "percent" ? `${v}%` : formatGP(v),
        },
        splitLine: { lineStyle: { color: grid } },
      },
      {
        type: "value", show: showVolume && single, name: "Vol",
        nameTextStyle: { color: fg },
        axisLabel: { color: fg, formatter: (v: number) => formatGP(v) },
        splitLine: { show: false },
      },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: 0, filterMode: "none" },
      {
        type: "slider", xAxisIndex: 0, height: 26, bottom: 12,
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

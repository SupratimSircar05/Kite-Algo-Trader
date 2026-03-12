import React, { useMemo } from "react";

const OVERLAY_CONFIG = [
  { key: "ema8", label: "EMA 8", color: "#38BDF8" },
  { key: "ema21", label: "EMA 21", color: "#F59E0B" },
  { key: "ema55", label: "EMA 55", color: "#A78BFA" },
  { key: "supertrend_line", label: "Supertrend", color: "#22C55E" },
];

const formatAxisValue = (value) => {
  if (typeof value !== "number" || Number.isNaN(value)) return "--";
  return value.toFixed(2);
};

export default function CandlestickChart({ candles = [], indicators = {}, signals = [], height = 420 }) {
  const chart = useMemo(() => {
    if (!candles.length) return null;

    const width = 1200;
    const padding = { top: 24, right: 24, bottom: 52, left: 72 };
    const innerWidth = width - padding.left - padding.right;
    const innerHeight = height - padding.top - padding.bottom;
    const allPrices = candles.flatMap((candle) => [candle.high, candle.low]);

    OVERLAY_CONFIG.forEach(({ key }) => {
      const series = indicators[key] || [];
      series.forEach((value) => {
        if (typeof value === "number" && Number.isFinite(value)) {
          allPrices.push(value);
        }
      });
    });

    const minPrice = Math.min(...allPrices);
    const maxPrice = Math.max(...allPrices);
    const priceRange = maxPrice - minPrice || 1;
    const stepX = innerWidth / Math.max(candles.length, 1);
    const candleBodyWidth = Math.max(4, Math.min(10, stepX * 0.58));
    const scaleY = (price) => padding.top + ((maxPrice - price) / priceRange) * innerHeight;
    const scaleX = (index) => padding.left + index * stepX + stepX / 2;
    const axisValues = Array.from({ length: 5 }, (_, index) => maxPrice - (priceRange / 4) * index);
    const labelIndexes = Array.from({ length: Math.min(5, candles.length) }, (_, index) => {
      if (candles.length === 1) return 0;
      return Math.round((index * (candles.length - 1)) / Math.max(Math.min(5, candles.length) - 1, 1));
    });

    return {
      width,
      height,
      padding,
      innerHeight,
      axisValues,
      labelIndexes,
      scaleX,
      scaleY,
      candleBodyWidth,
    };
  }, [candles, indicators, height]);

  if (!candles.length || !chart) {
    return (
      <div
        data-testid="candlestick-chart-empty-state"
        className="flex h-[420px] items-center justify-center rounded-sm border border-dashed border-zinc-700 bg-zinc-950 text-sm font-mono text-zinc-500"
      >
        No candle data available
      </div>
    );
  }

  return (
    <div data-testid="candlestick-chart-wrapper" className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 text-[10px] font-mono text-zinc-400" data-testid="candlestick-chart-legend">
        <span className="rounded-full border border-emerald-700/70 bg-emerald-950/40 px-2 py-1 text-emerald-300">Bull Candle</span>
        <span className="rounded-full border border-rose-700/70 bg-rose-950/40 px-2 py-1 text-rose-300">Bear Candle</span>
        {OVERLAY_CONFIG.map((overlay) => (
          <span key={overlay.key} className="flex items-center gap-1.5">
            <span className="h-2 w-5 rounded-full" style={{ backgroundColor: overlay.color }} />
            {overlay.label}
          </span>
        ))}
        <span className="rounded-full border border-amber-700/70 bg-amber-950/40 px-2 py-1 text-amber-300">TrendShift Signal</span>
      </div>

      <div className="overflow-x-auto rounded-sm border border-zinc-800 bg-zinc-950/70 p-3">
        <svg
          data-testid="candlestick-chart"
          viewBox={`0 0 ${chart.width} ${chart.height}`}
          className="min-w-full"
          role="img"
          aria-label="Candlestick chart with indicator overlays"
        >
          {chart.axisValues.map((value, index) => {
            const y = chart.scaleY(value);
            return (
              <g key={value}>
                <line x1={chart.padding.left} x2={chart.width - chart.padding.right} y1={y} y2={y} stroke="#27272A" strokeDasharray="3 4" />
                <text x={16} y={y + 4} fill="#71717A" fontSize="11" fontFamily="JetBrains Mono">
                  {formatAxisValue(value)}
                </text>
              </g>
            );
          })}

          {chart.labelIndexes.map((index) => {
            const candle = candles[index];
            const x = chart.scaleX(index);
            return (
              <text
                key={`${candle.timestamp}-${index}`}
                x={x}
                y={chart.height - 16}
                fill="#71717A"
                fontSize="11"
                fontFamily="JetBrains Mono"
                textAnchor="middle"
              >
                {(candle.timestamp || "").substring(5, 10)}
              </text>
            );
          })}

          {OVERLAY_CONFIG.map((overlay) => {
            const series = indicators[overlay.key] || [];
            if (!series.length) return null;
            const path = series
              .map((value, index) => {
                if (typeof value !== "number" || Number.isNaN(value)) return null;
                const x = chart.scaleX(index);
                const y = chart.scaleY(value);
                return `${index === 0 ? "M" : "L"}${x},${y}`;
              })
              .filter(Boolean)
              .join(" ");

            if (!path) return null;
            return <path key={overlay.key} d={path} fill="none" stroke={overlay.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" opacity="0.9" />;
          })}

          {candles.map((candle, index) => {
            const x = chart.scaleX(index);
            const wickTop = chart.scaleY(candle.high);
            const wickBottom = chart.scaleY(candle.low);
            const openY = chart.scaleY(candle.open);
            const closeY = chart.scaleY(candle.close);
            const bodyTop = Math.min(openY, closeY);
            const bodyHeight = Math.max(Math.abs(openY - closeY), 2);
            const isBullish = candle.close >= candle.open;
            const fill = isBullish ? "#22C55E" : "#EF4444";

            return (
              <g key={`${candle.timestamp}-${index}`}>
                <line x1={x} x2={x} y1={wickTop} y2={wickBottom} stroke={fill} strokeWidth="1.4" opacity="0.9" />
                <rect
                  x={x - chart.candleBodyWidth / 2}
                  y={bodyTop}
                  width={chart.candleBodyWidth}
                  height={bodyHeight}
                  rx="1"
                  fill={fill}
                  fillOpacity={isBullish ? 0.88 : 0.78}
                />
              </g>
            );
          })}

          {signals.map((signal, index) => {
            const x = chart.scaleX(signal.index || 0);
            const candle = candles[signal.index || 0];
            if (!candle) return null;
            const isBuy = signal.side === "BUY";
            const y = chart.scaleY(isBuy ? candle.low : candle.high) + (isBuy ? 18 : -18);
            return (
              <g key={`${signal.id || signal.timestamp}-${index}`}>
                <circle cx={x} cy={y} r="7" fill={isBuy ? "#10B981" : "#F43F5E"} stroke="#09090B" strokeWidth="2" />
                <text x={x} y={y + 3} textAnchor="middle" fontSize="8" fontFamily="IBM Plex Sans" fill="#FFFFFF">
                  {isBuy ? "B" : "S"}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
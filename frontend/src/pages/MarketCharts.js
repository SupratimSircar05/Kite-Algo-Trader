import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Activity, CandlestickChart as CandlestickIcon, Radio, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import CandlestickChart from "@/components/CandlestickChart";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const SYMBOLS = ["RELIANCE", "INFY", "TCS", "HDFCBANK", "SBIN", "ITC"];
const TIMEFRAMES = ["day", "60m", "15m", "5m"];

function ChartMetric({ label, value, tone = "text-white", testId }) {
  return (
    <div data-testid={testId} className="metric-card min-h-[88px]">
      <div className="mb-2 text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
      <div className={`text-lg font-bold font-mono ${tone}`}>{value}</div>
    </div>
  );
}

export default function MarketCharts() {
  const [filters, setFilters] = useState({
    symbol: "RELIANCE",
    timeframe: "day",
    start_date: "2024-06-01",
    end_date: "2025-06-01",
    include_indicators: true,
    include_trendshift: true,
  });
  const [chartData, setChartData] = useState({ candles: [], indicators: {}, trendshift_signals: [], zones: {}, indicator_summary: {} });
  const [loading, setLoading] = useState(true);

  const fetchChart = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/chart/candles`, { params: { ...filters, limit: 120 } });
      setChartData(response.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to load chart data");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchChart();
  }, [fetchChart]);

  const summary = chartData.indicator_summary || {};
  const lastDirection = summary.supertrend_direction === 1 ? "Bullish" : summary.supertrend_direction === -1 ? "Bearish" : "Neutral";

  return (
    <div data-testid="market-charts-page" className="space-y-4 p-4 md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight text-white">
            <CandlestickIcon className="h-5 w-5 text-blue-500" /> Candlestick Lab
          </h1>
          <p data-testid="market-charts-subtitle" className="mt-0.5 text-xs font-mono text-zinc-500">
            Price structure, indicator overlays, and TrendShift signal zones
          </p>
        </div>
        <Button
          data-testid="market-charts-refresh-button"
          variant="outline"
          size="sm"
          onClick={fetchChart}
          className="w-fit rounded-sm border-zinc-700"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Refresh Chart
        </Button>
      </div>

      <Card className="rounded-sm border-zinc-800 bg-zinc-900">
        <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
          <CardTitle className="text-sm font-medium text-zinc-300">Chart Controls</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 p-4 lg:grid-cols-6">
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-wider text-zinc-500">Symbol</label>
            <Select value={filters.symbol} onValueChange={(value) => setFilters((prev) => ({ ...prev, symbol: value }))}>
              <SelectTrigger data-testid="market-charts-symbol-select" className="h-8 bg-zinc-800 text-xs border-zinc-700">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SYMBOLS.map((symbol) => (
                  <SelectItem key={symbol} value={symbol}>{symbol}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-wider text-zinc-500">Timeframe</label>
            <Select value={filters.timeframe} onValueChange={(value) => setFilters((prev) => ({ ...prev, timeframe: value }))}>
              <SelectTrigger data-testid="market-charts-timeframe-select" className="h-8 bg-zinc-800 text-xs border-zinc-700">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TIMEFRAMES.map((timeframe) => (
                  <SelectItem key={timeframe} value={timeframe}>{timeframe}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-wider text-zinc-500">From</label>
            <input
              data-testid="market-charts-from-date"
              type="date"
              value={filters.start_date}
              onChange={(event) => setFilters((prev) => ({ ...prev, start_date: event.target.value }))}
              className="h-8 w-full rounded-sm border border-zinc-700 bg-zinc-800 px-3 text-xs text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-wider text-zinc-500">To</label>
            <input
              data-testid="market-charts-to-date"
              type="date"
              value={filters.end_date}
              onChange={(event) => setFilters((prev) => ({ ...prev, end_date: event.target.value }))}
              className="h-8 w-full rounded-sm border border-zinc-700 bg-zinc-800 px-3 text-xs text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div className="flex items-center justify-between rounded-sm border border-zinc-800 bg-zinc-950/60 px-3 py-2">
            <div>
              <div className="text-[10px] uppercase tracking-wider text-zinc-500">Indicators</div>
              <div className="text-xs text-zinc-300">EMA, RSI, Supertrend</div>
            </div>
            <Switch
              data-testid="market-charts-indicators-switch"
              checked={filters.include_indicators}
              onCheckedChange={(checked) => setFilters((prev) => ({ ...prev, include_indicators: checked }))}
            />
          </div>
          <div className="flex items-center justify-between rounded-sm border border-zinc-800 bg-zinc-950/60 px-3 py-2">
            <div>
              <div className="text-[10px] uppercase tracking-wider text-zinc-500">TrendShift</div>
              <div className="text-xs text-zinc-300">Overlay strategy signals</div>
            </div>
            <Switch
              data-testid="market-charts-trendshift-switch"
              checked={filters.include_trendshift}
              onCheckedChange={(checked) => setFilters((prev) => ({ ...prev, include_trendshift: checked }))}
            />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
        <ChartMetric testId="market-charts-last-close" label="Last Close" value={(summary.last_close ?? 0).toFixed(2)} />
        <ChartMetric testId="market-charts-rsi" label="RSI" value={summary.rsi !== null && summary.rsi !== undefined ? Number(summary.rsi).toFixed(2) : "--"} tone="text-amber-400" />
        <ChartMetric testId="market-charts-trend-state" label="Trend State" value={lastDirection} tone={lastDirection === "Bullish" ? "text-emerald-400" : lastDirection === "Bearish" ? "text-rose-400" : "text-zinc-300"} />
        <ChartMetric testId="market-charts-volume-relative" label="Relative Volume" value={summary.volume_relative !== null && summary.volume_relative !== undefined ? `${Number(summary.volume_relative).toFixed(2)}x` : "--"} />
        <ChartMetric testId="market-charts-signal-count" label="TrendShift Signals" value={summary.signal_count ?? 0} tone="text-blue-400" />
      </div>

      <Card className="rounded-sm border-zinc-800 bg-zinc-900">
        <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
          <CardTitle className="text-sm font-medium text-zinc-300">{filters.symbol} Price Structure</CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          {loading ? (
            <div data-testid="market-charts-loading-state" className="flex h-[420px] items-center justify-center text-sm font-mono text-zinc-500">
              Loading chart data...
            </div>
          ) : (
            <CandlestickChart candles={chartData.candles} indicators={chartData.indicators} signals={chartData.trendshift_signals} />
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card className="rounded-sm border-zinc-800 bg-zinc-900">
          <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
            <CardTitle className="text-sm font-medium text-zinc-300">TrendShift Signal Tape</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 p-4">
            {(chartData.trendshift_signals || []).length === 0 ? (
              <div data-testid="market-charts-signal-empty-state" className="text-sm font-mono text-zinc-500">
                No TrendShift signals detected in the current range.
              </div>
            ) : (
              chartData.trendshift_signals.map((signal) => (
                <div
                  key={signal.id}
                  data-testid={`market-charts-signal-${signal.id}`}
                  className="rounded-sm border border-zinc-800 bg-zinc-950/60 p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 text-sm font-medium text-white">
                      <Radio className={`h-4 w-4 ${signal.side === "BUY" ? "text-emerald-400" : "text-rose-400"}`} />
                      {signal.side} · {signal.symbol}
                    </div>
                    <div className="text-xs font-mono text-zinc-500">{signal.timestamp?.substring(0, 16)}</div>
                  </div>
                  <div className="mt-2 text-xs font-mono text-zinc-400">{signal.reason}</div>
                  <div className="mt-2 flex flex-wrap gap-4 text-xs font-mono text-zinc-300">
                    <span>Confidence: {(signal.confidence * 100).toFixed(0)}%</span>
                    <span>SL: {signal.stop_loss?.toFixed(2) || "--"}</span>
                    <span>TP: {signal.take_profit?.toFixed(2) || "--"}</span>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="rounded-sm border-zinc-800 bg-zinc-900">
          <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
            <CardTitle className="text-sm font-medium text-zinc-300">Zone Map</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 p-4">
            <div>
              <div className="mb-2 flex items-center gap-2 text-xs font-mono text-emerald-400">
                <Activity className="h-4 w-4" /> Demand Zones
              </div>
              <div className="space-y-2">
                {(chartData.zones?.demand || []).length === 0 ? (
                  <div data-testid="market-charts-demand-zones-empty" className="text-sm font-mono text-zinc-500">No demand zones in current slice</div>
                ) : (
                  chartData.zones.demand.map((zone, index) => (
                    <div key={`demand-${index}`} data-testid={`market-charts-demand-zone-${index}`} className="rounded-sm border border-emerald-900/60 bg-emerald-950/20 px-3 py-2 text-xs font-mono text-zinc-300">
                      Low {zone.low?.toFixed(2)} · High {zone.high?.toFixed(2)}
                    </div>
                  ))
                )}
              </div>
            </div>
            <div>
              <div className="mb-2 flex items-center gap-2 text-xs font-mono text-rose-400">
                <Activity className="h-4 w-4" /> Supply Zones
              </div>
              <div className="space-y-2">
                {(chartData.zones?.supply || []).length === 0 ? (
                  <div data-testid="market-charts-supply-zones-empty" className="text-sm font-mono text-zinc-500">No supply zones in current slice</div>
                ) : (
                  chartData.zones.supply.map((zone, index) => (
                    <div key={`supply-${index}`} data-testid={`market-charts-supply-zone-${index}`} className="rounded-sm border border-rose-900/60 bg-rose-950/20 px-3 py-2 text-xs font-mono text-zinc-300">
                      Low {zone.low?.toFixed(2)} · High {zone.high?.toFixed(2)}
                    </div>
                  ))
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
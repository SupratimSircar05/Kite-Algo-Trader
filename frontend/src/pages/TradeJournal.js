import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { BookOpenText, Download, RefreshCw, TrendingDown, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const SYMBOLS = ["all", "RELIANCE", "INFY", "TCS", "HDFCBANK", "SBIN", "ITC"];

function JournalMetric({ label, value, tone = "text-white", testId }) {
  return (
    <div data-testid={testId} className="metric-card min-h-[88px]">
      <div className="mb-2 text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
      <div className={`text-lg font-bold font-mono ${tone}`}>{value}</div>
    </div>
  );
}

export default function TradeJournal() {
  const [journal, setJournal] = useState({ summary: {}, trades: [] });
  const [strategies, setStrategies] = useState([]);
  const [filters, setFilters] = useState({ symbol: "all", strategy: "all", status: "all", side: "all" });
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        ...(filters.symbol !== "all" ? { symbol: filters.symbol } : {}),
        ...(filters.strategy !== "all" ? { strategy: filters.strategy } : {}),
        ...(filters.status !== "all" ? { status: filters.status } : {}),
        ...(filters.side !== "all" ? { side: filters.side } : {}),
        limit: 250,
      };
      const [journalRes, strategyRes] = await Promise.all([
        axios.get(`${API}/journal`, { params }),
        axios.get(`${API}/strategies`),
      ]);
      setJournal(journalRes.data);
      setStrategies(strategyRes.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to load trade journal");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const exportJournal = (format) => {
    const params = new URLSearchParams();
    params.set("format", format);
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== "all") params.set(key, value);
    });
    window.open(`${API}/journal/export?${params.toString()}`, "_blank", "noopener,noreferrer");
  };

  const summary = journal.summary || {};
  const trades = journal.trades || [];
  const bestTradeValue = summary.best_trade?.net_pnl ?? 0;
  const worstTradeValue = summary.worst_trade?.net_pnl ?? 0;

  const strategyOptions = useMemo(() => ["all", ...strategies.map((strategy) => strategy.name)], [strategies]);

  return (
    <div data-testid="trade-journal-page" className="space-y-4 p-4 md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight text-white">
            <BookOpenText className="h-5 w-5 text-blue-500" /> Trade Journal
          </h1>
          <p data-testid="trade-journal-subtitle" className="mt-0.5 text-xs font-mono text-zinc-500">
            Auditable trade history, export tools, and performance rollups
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            data-testid="trade-journal-refresh-button"
            variant="outline"
            size="sm"
            onClick={fetchData}
            className="rounded-sm border-zinc-700"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
          <Button
            data-testid="trade-journal-export-csv-button"
            size="sm"
            onClick={() => exportJournal("csv")}
            className="rounded-sm bg-blue-600 hover:bg-blue-500"
          >
            <Download className="h-3.5 w-3.5" /> Export CSV
          </Button>
          <Button
            data-testid="trade-journal-export-json-button"
            size="sm"
            variant="outline"
            onClick={() => exportJournal("json")}
            className="rounded-sm border-zinc-700"
          >
            <Download className="h-3.5 w-3.5" /> Export JSON
          </Button>
        </div>
      </div>

      <Card className="rounded-sm border-zinc-800 bg-zinc-900">
        <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
          <CardTitle className="text-sm font-medium text-zinc-300">Filters</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 p-4 md:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-wider text-zinc-500">Symbol</label>
            <Select value={filters.symbol} onValueChange={(value) => setFilters((prev) => ({ ...prev, symbol: value }))}>
              <SelectTrigger data-testid="trade-journal-symbol-filter" className="h-8 bg-zinc-800 text-xs border-zinc-700">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SYMBOLS.map((symbol) => (
                  <SelectItem key={symbol} value={symbol}>{symbol === "all" ? "All Symbols" : symbol}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-wider text-zinc-500">Strategy</label>
            <Select value={filters.strategy} onValueChange={(value) => setFilters((prev) => ({ ...prev, strategy: value }))}>
              <SelectTrigger data-testid="trade-journal-strategy-filter" className="h-8 bg-zinc-800 text-xs border-zinc-700">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {strategyOptions.map((strategy) => (
                  <SelectItem key={strategy} value={strategy}>{strategy === "all" ? "All Strategies" : strategy}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-wider text-zinc-500">Status</label>
            <Select value={filters.status} onValueChange={(value) => setFilters((prev) => ({ ...prev, status: value }))}>
              <SelectTrigger data-testid="trade-journal-status-filter" className="h-8 bg-zinc-800 text-xs border-zinc-700">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="OPEN">Open</SelectItem>
                <SelectItem value="CLOSED">Closed</SelectItem>
                <SelectItem value="PARTIALLY_CLOSED">Partially Closed</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-wider text-zinc-500">Side</label>
            <Select value={filters.side} onValueChange={(value) => setFilters((prev) => ({ ...prev, side: value }))}>
              <SelectTrigger data-testid="trade-journal-side-filter" className="h-8 bg-zinc-800 text-xs border-zinc-700">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Both Sides</SelectItem>
                <SelectItem value="BUY">Buy</SelectItem>
                <SelectItem value="SELL">Sell</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
        <JournalMetric testId="trade-journal-total-trades" label="Total Trades" value={summary.total_trades ?? 0} />
        <JournalMetric
          testId="trade-journal-net-pnl"
          label="Net P&L"
          value={`${summary.net_pnl >= 0 ? "+" : ""}${(summary.net_pnl ?? 0).toFixed(2)}`}
          tone={(summary.net_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}
        />
        <JournalMetric testId="trade-journal-win-rate" label="Win Rate" value={`${(summary.win_rate ?? 0).toFixed(2)}%`} />
        <JournalMetric testId="trade-journal-best-strategy" label="Top Strategy" value={summary.best_strategy || "--"} />
        <JournalMetric
          testId="trade-journal-fees"
          label="Fees Paid"
          value={`${(summary.total_fees ?? 0).toFixed(2)}`}
          tone="text-amber-400"
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
        <Card className="rounded-sm border-zinc-800 bg-zinc-900">
          <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
            <CardTitle className="text-sm font-medium text-zinc-300">Trade Ledger</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="max-h-[520px] overflow-auto" data-testid="trade-journal-table-wrapper">
              <table className="w-full data-table" data-testid="trade-journal-table">
                <thead className="sticky top-0 z-10 bg-zinc-900">
                  <tr>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Strategy</th>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>Net</th>
                    <th>Fees</th>
                    <th>Status</th>
                    <th>Exit Time</th>
                  </tr>
                </thead>
                <tbody>
                  {!loading && trades.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="py-16 text-center text-sm font-mono text-zinc-600">
                        No trades matched the selected filters
                      </td>
                    </tr>
                  ) : (
                    trades.map((trade) => (
                      <tr key={trade.id} data-testid={`trade-journal-row-${trade.id}`}>
                        <td className="font-medium text-white">{trade.symbol}</td>
                        <td className={trade.side === "BUY" ? "text-emerald-400" : "text-rose-400"}>{trade.side}</td>
                        <td className="text-zinc-400">{trade.strategy_name || "manual"}</td>
                        <td className="text-zinc-300">{trade.entry_price?.toFixed(2)}</td>
                        <td className="text-zinc-300">{trade.exit_price ? trade.exit_price.toFixed(2) : "--"}</td>
                        <td className={(trade.net_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}>
                          {(trade.net_pnl ?? 0) >= 0 ? "+" : ""}{(trade.net_pnl ?? 0).toFixed(2)}
                        </td>
                        <td className="text-zinc-500">{(trade.fees ?? 0).toFixed(2)}</td>
                        <td className="text-zinc-400">{trade.status}</td>
                        <td className="text-xs text-zinc-500">{trade.exit_time?.substring(0, 16) || "--"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card className="rounded-sm border-zinc-800 bg-zinc-900">
            <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
              <CardTitle className="text-sm font-medium text-zinc-300">Performance Snapshot</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 p-4 text-sm font-mono">
              <div data-testid="trade-journal-average-net" className="flex items-center justify-between">
                <span className="text-zinc-500">Average Net / Trade</span>
                <span className={(summary.avg_net_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}>{(summary.avg_net_pnl ?? 0).toFixed(2)}</span>
              </div>
              <div data-testid="trade-journal-best-trade" className="flex items-center justify-between">
                <span className="text-zinc-500">Best Trade</span>
                <span className={bestTradeValue >= 0 ? "text-emerald-400" : "text-rose-400"}>{bestTradeValue.toFixed(2)}</span>
              </div>
              <div data-testid="trade-journal-worst-trade" className="flex items-center justify-between">
                <span className="text-zinc-500">Worst Trade</span>
                <span className={worstTradeValue >= 0 ? "text-emerald-400" : "text-rose-400"}>{worstTradeValue.toFixed(2)}</span>
              </div>
            </CardContent>
          </Card>

          <Card className="rounded-sm border-zinc-800 bg-zinc-900">
            <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
              <CardTitle className="text-sm font-medium text-zinc-300">Strategy Breakdown</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 p-4">
              {Object.keys(summary.strategy_breakdown || {}).length === 0 ? (
                <div data-testid="trade-journal-strategy-breakdown-empty" className="text-sm font-mono text-zinc-500">No strategy data yet</div>
              ) : (
                Object.entries(summary.strategy_breakdown || {}).map(([strategyName, count]) => (
                  <div key={strategyName} data-testid={`trade-journal-strategy-count-${strategyName}`} className="flex items-center justify-between rounded-sm border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-sm font-mono">
                    <span className="text-zinc-400">{strategyName}</span>
                    <span className="text-white">{count}</span>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card className="rounded-sm border-zinc-800 bg-zinc-900">
            <CardContent className="p-4 text-xs text-zinc-500">
              <div data-testid="trade-journal-export-note" className="flex items-start gap-2 font-mono">
                {(summary.net_pnl ?? 0) >= 0 ? <TrendingUp className="mt-0.5 h-4 w-4 text-emerald-400" /> : <TrendingDown className="mt-0.5 h-4 w-4 text-rose-400" />}
                <span>
                  Journal exports are generated directly from the stored trade ledger, so they remain available even when live broker credentials are not configured.
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
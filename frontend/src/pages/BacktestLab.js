import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { LineChart as LineChartIcon, Play, Clock, Activity, History } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer
} from "recharts";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function BacktestLab() {
  const [results, setResults] = useState([]);
  const [strategies, setStrategies] = useState([]);
  const [selectedResult, setSelectedResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [activeJob, setActiveJob] = useState(null);
  const [recentJobs, setRecentJobs] = useState([]);
  const [form, setForm] = useState({
    strategy_name: "sma_crossover",
    symbol: "RELIANCE",
    start_date: "2024-01-01",
    end_date: "2025-06-01",
    initial_capital: 100000,
    quantity: 10,
    timeframe: "day",
    use_ml_filter: true,
  });

  const fetchJobs = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/jobs`, { params: { kind: "backtest", limit: 8 } });
      setRecentJobs(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const fetchResults = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/backtest/results`);
      setResults(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    fetchResults();
    fetchJobs();
    const savedJobId = window.localStorage.getItem("kitealgo-backtest-job-id");
    if (savedJobId) {
      axios.get(`${API}/jobs/${savedJobId}`).then((res) => setActiveJob(res.data)).catch(() => {
        window.localStorage.removeItem("kitealgo-backtest-job-id");
      });
    }
  }, [fetchResults, fetchJobs]);

  useEffect(() => {
    axios.get(`${API}/strategies`).then((res) => setStrategies(res.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!activeJob?.id || ["completed", "failed", "cancelled"].includes(activeJob.status)) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const res = await axios.get(`${API}/jobs/${activeJob.id}`);
        const job = res.data;
        setActiveJob(job);
        if (job.status === "completed") {
          window.localStorage.removeItem("kitealgo-backtest-job-id");
          if (job.result?.result_id) {
            const detail = await axios.get(`${API}/backtest/results/${job.result.result_id}`);
            setSelectedResult(detail.data);
            toast.success("Backtest completed successfully");
            fetchResults();
            fetchJobs();
          }
        }
        if (job.status === "failed") {
          window.localStorage.removeItem("kitealgo-backtest-job-id");
          toast.error(job.error || "Backtest job failed");
          fetchJobs();
        }
      } catch (e) {
        console.error(e);
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeJob, fetchResults, fetchJobs]);

  const runBacktest = async () => {
    setRunning(true);
    try {
      const payload = {
        ...form,
        execution_mode: "queue",
        parameters: form.strategy_name === "trendshift" ? { use_ml_filter: form.use_ml_filter } : {},
      };
      delete payload.use_ml_filter;
      const res = await axios.post(`${API}/backtest/run`, payload);
      if (res.data.status === "queued") {
        setActiveJob({ id: res.data.job_id, status: "queued", progress_pct: 0, message: res.data.message });
        window.localStorage.setItem("kitealgo-backtest-job-id", res.data.job_id);
        toast.info(`Backtest queued with ${res.data.estimated_candles} candles`);
        fetchJobs();
      } else {
        setSelectedResult(res.data);
        toast.success(`Backtest complete: ${res.data.total_trades} trades`);
        fetchResults();
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Backtest failed");
    } finally {
      setRunning(false);
    }
  };

  const loadJobResult = async (job) => {
    if (!job?.result?.result_id) return;
    try {
      const detail = await axios.get(`${API}/backtest/results/${job.result.result_id}`);
      setSelectedResult(detail.data);
      setActiveJob(job);
      toast.info("Loaded queued backtest result");
    } catch (e) {
      toast.error("Failed to load queued result");
    }
  };

  const m = selectedResult;

  return (
    <div data-testid="backtest-page" className="p-4 md:p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight flex items-center gap-2">
            <LineChartIcon className="w-5 h-5 text-blue-500" /> Backtest Lab
          </h1>
          <p className="text-xs text-zinc-500 font-mono mt-0.5">
            Queue long backtests safely and resume progress after reload
          </p>
        </div>
      </div>

      {activeJob && (
        <Card data-testid="backtest-job-card" className="bg-blue-950/20 border-blue-900/50 rounded-sm">
          <CardContent className="p-4 space-y-3">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <div className="flex items-center gap-2 text-sm font-medium text-white">
                  <Activity className="h-4 w-4 text-blue-400" /> Backtest Job Status
                </div>
                <div data-testid="backtest-job-message" className="mt-1 text-xs font-mono text-zinc-400">
                  {activeJob.message || "Queued"}
                </div>
              </div>
              <div data-testid="backtest-job-state" className="text-xs font-mono text-blue-300">
                {activeJob.status?.toUpperCase()} · {(activeJob.progress_pct || 0).toFixed(0)}%
              </div>
            </div>
            <Progress data-testid="backtest-job-progress" value={activeJob.progress_pct || 0} className="h-2 bg-blue-950/40 [&>div]:bg-blue-500" />
            <div className="text-[11px] font-mono text-zinc-500">
              Uses saved strategy defaults from Strategy Editor unless you override them via API.
            </div>
          </CardContent>
        </Card>
      )}

      {/* Config Panel */}
      <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
        <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
          <CardTitle className="text-sm font-medium text-zinc-300">Backtest Configuration</CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Strategy</label>
              <Select value={form.strategy_name} onValueChange={(v) => setForm(f => ({...f, strategy_name: v}))}>
                <SelectTrigger data-testid="bt-strategy-select" className="h-8 text-xs bg-zinc-800 border-zinc-700">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    {(strategies.length ? strategies : [
                      { name: "sma_crossover", display_name: "SMA Crossover" },
                      { name: "opening_range_breakout", display_name: "ORB Strategy" },
                      { name: "trendshift", display_name: "TrendShift" },
                    ]).map((strategy) => (
                      <SelectItem key={strategy.name} value={strategy.name}>{strategy.display_name}</SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Symbol</label>
              <Select value={form.symbol} onValueChange={(v) => setForm(f => ({...f, symbol: v}))}>
                <SelectTrigger data-testid="bt-symbol-select" className="h-8 text-xs bg-zinc-800 border-zinc-700">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {["RELIANCE", "INFY", "TCS", "HDFCBANK", "SBIN", "ITC"].map(s => (
                    <SelectItem key={s} value={s}>{s}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">From</label>
              <Input data-testid="bt-from-date" type="date" value={form.start_date} onChange={(e) => setForm(f => ({...f, start_date: e.target.value}))} className="h-8 text-xs bg-zinc-800 border-zinc-700" />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">To</label>
              <Input data-testid="bt-to-date" type="date" value={form.end_date} onChange={(e) => setForm(f => ({...f, end_date: e.target.value}))} className="h-8 text-xs bg-zinc-800 border-zinc-700" />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Capital</label>
              <Input data-testid="bt-capital" type="number" value={form.initial_capital} onChange={(e) => setForm(f => ({...f, initial_capital: Number(e.target.value)}))} className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Quantity</label>
              <Input data-testid="bt-quantity" type="number" value={form.quantity} onChange={(e) => setForm(f => ({...f, quantity: Number(e.target.value)}))} className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
            </div>
            <div className="flex items-end">
              <Button
                data-testid="run-backtest-btn"
                onClick={runBacktest}
                disabled={running}
                className="w-full h-8 rounded-sm bg-blue-600 hover:bg-blue-500 text-xs gap-1.5"
              >
                {running ? <Clock className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                {running ? "Running..." : "Run Backtest"}
              </Button>
            </div>
          </div>
          {form.strategy_name === "trendshift" && (
            <div className="mt-3 flex items-center gap-3">
              <label data-testid="ml-filter-toggle" className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={form.use_ml_filter}
                  onChange={(e) => setForm(f => ({...f, use_ml_filter: e.target.checked}))}
                  className="w-3.5 h-3.5 rounded-sm bg-zinc-800 border-zinc-600 accent-amber-500"
                />
                <span className="text-xs text-zinc-400">
                  ML Regime Filter
                </span>
              </label>
              <span className="text-[10px] font-mono text-zinc-600">
                {form.use_ml_filter ? "RandomForest predictions will confirm trade direction" : "Pure indicator-based signals only"}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Results */}
      {m && (
        <>
          {/* Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2">
            <BtMetric label="Return" value={`${m.total_return_pct >= 0 ? "+" : ""}${m.total_return_pct?.toFixed(2)}%`} color={m.total_return_pct >= 0 ? "text-profit" : "text-loss"} />
            <BtMetric label="Net P&L" value={`${m.total_return?.toFixed(0)}`} color={m.total_return >= 0 ? "text-profit" : "text-loss"} />
            <BtMetric label="Trades" value={m.total_trades} />
            <BtMetric label="Win Rate" value={`${m.win_rate?.toFixed(1)}%`} />
            <BtMetric label="Max DD" value={`${m.max_drawdown_pct?.toFixed(2)}%`} color="text-loss" />
            <BtMetric label="Sharpe" value={m.sharpe_ratio?.toFixed(2)} />
            <BtMetric label="Profit Factor" value={m.profit_factor?.toFixed(2)} />
            <BtMetric label="Slip (bps)" value={m.avg_slippage_bps?.toFixed(2)} />
          </div>

          {/* Equity Curve */}
          <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
            <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
              <CardTitle className="text-sm font-medium text-zinc-300">
                Equity Curve - {m.strategy_name} on {m.symbol}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <div data-testid="backtest-equity-chart" className="h-[300px]">
                {m.equity_curve?.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={m.equity_curve}>
                      <defs>
                        <linearGradient id="btGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={m.total_return >= 0 ? "#22C55E" : "#EF4444"} stopOpacity={0.3} />
                          <stop offset="95%" stopColor={m.total_return >= 0 ? "#22C55E" : "#EF4444"} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1E1E1E" />
                      <XAxis dataKey="timestamp" hide />
                      <YAxis stroke="#3F3F46" tick={{ fill: "#71717A", fontSize: 11, fontFamily: "JetBrains Mono" }} width={70} tickFormatter={(v) => `${(v/1000).toFixed(0)}k`} />
                      <Tooltip contentStyle={{ background: "#121212", border: "1px solid #27272A", borderRadius: "2px", fontFamily: "JetBrains Mono", fontSize: "12px" }} labelStyle={{ display: "none" }} />
                      <Area type="monotone" dataKey="equity" stroke={m.total_return >= 0 ? "#22C55E" : "#EF4444"} fill="url(#btGrad)" strokeWidth={1.5} dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-zinc-600 text-sm font-mono">
                    No equity curve data
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Trades Table */}
          <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
            <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
              <CardTitle className="text-sm font-medium text-zinc-300">Backtest Trades ({m.trades?.length})</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-auto max-h-[300px]">
                <table className="w-full data-table">
                  <thead className="sticky top-0 bg-zinc-900 z-10">
                    <tr>
                      <th>#</th><th>Side</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Net</th><th>Fees</th><th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(m.trades || []).map((t, i) => (
                      <tr key={i}>
                        <td className="text-zinc-500">{i + 1}</td>
                        <td><span className={t.side === "BUY" ? "text-profit" : "text-loss"}>{t.side}</span></td>
                        <td className="text-zinc-300">{t.entry_price?.toFixed(2)}</td>
                        <td className="text-zinc-300">{t.exit_price?.toFixed(2)}</td>
                        <td className={t.pnl >= 0 ? "text-profit" : "text-loss"}>{t.pnl >= 0 ? "+" : ""}{t.pnl?.toFixed(2)}</td>
                        <td className={t.net_pnl >= 0 ? "text-profit" : "text-loss"}>{t.net_pnl >= 0 ? "+" : ""}{t.net_pnl?.toFixed(2)}</td>
                        <td className="text-zinc-500">{t.fees?.toFixed(2)}</td>
                        <td className="text-zinc-500 text-xs truncate max-w-[150px]">{t.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {recentJobs.length > 0 && (
        <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
          <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
            <CardTitle className="text-sm font-medium text-zinc-300 flex items-center gap-2">
              <History className="w-4 h-4 text-zinc-500" /> Queued Backtests
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-auto max-h-[220px]">
              <table className="w-full data-table" data-testid="backtest-jobs-table">
                <thead className="sticky top-0 bg-zinc-900 z-10">
                  <tr>
                    <th>Strategy</th><th>Symbol</th><th>Status</th><th>Progress</th><th>Queued</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {recentJobs.map((job) => (
                    <tr key={job.id} data-testid={`backtest-job-row-${job.id}`}>
                      <td className="text-white">{job.meta?.strategy_name || "--"}</td>
                      <td className="text-zinc-300">{job.meta?.symbol || "--"}</td>
                      <td className="text-zinc-400">{job.status}</td>
                      <td className="text-zinc-300">{(job.progress_pct || 0).toFixed(0)}%</td>
                      <td className="text-zinc-500 text-xs">{job.queued_at?.substring(0, 16)}</td>
                      <td>
                        <Button
                          data-testid={`backtest-job-load-${job.id}`}
                          variant="outline"
                          size="sm"
                          disabled={!job.result?.result_id}
                          onClick={() => loadJobResult(job)}
                          className="h-7 rounded-sm border-zinc-700 text-[10px]"
                        >
                          Load
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Past Results */}
      {results.length > 0 && (
        <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
          <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
            <CardTitle className="text-sm font-medium text-zinc-300">Previous Backtests</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-auto max-h-[250px]">
              <table className="w-full data-table">
                <thead className="sticky top-0 bg-zinc-900 z-10">
                  <tr>
                    <th>Strategy</th><th>Symbol</th><th>Return</th><th>Trades</th><th>Win Rate</th><th>Max DD</th><th>Sharpe</th><th>Date</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r, i) => (
                    <tr key={i} className="cursor-pointer" onClick={() => setSelectedResult(r)}>
                      <td className="text-white">{r.strategy_name}</td>
                      <td className="text-zinc-300">{r.symbol}</td>
                      <td className={r.total_return_pct >= 0 ? "text-profit" : "text-loss"}>{r.total_return_pct?.toFixed(2)}%</td>
                      <td className="text-zinc-300">{r.total_trades}</td>
                      <td className="text-zinc-300">{r.win_rate?.toFixed(1)}%</td>
                      <td className="text-loss">{r.max_drawdown_pct?.toFixed(2)}%</td>
                      <td className="text-zinc-300">{r.sharpe_ratio?.toFixed(2)}</td>
                      <td className="text-zinc-500 text-xs">{r.created_at?.substring(0, 10)}</td>
                      <td><Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400 cursor-pointer hover:text-white">View</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function BtMetric({ label, value, color = "text-white" }) {
  return (
    <div className="metric-card">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">{label}</div>
      <div className={`text-base font-mono font-bold ${color}`}>{value ?? "---"}</div>
    </div>
  );
}

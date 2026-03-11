import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  TrendingUp, TrendingDown, Activity, Zap, Target,
  ArrowUpRight, ArrowDownRight, Clock, ShieldAlert, Play, Square
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, AreaChart, Area, BarChart, Bar
} from "recharts";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [equityCurve, setEquityCurve] = useState([]);
  const [dailyPnl, setDailyPnl] = useState([]);
  const [recentSignals, setRecentSignals] = useState([]);
  const [recentTrades, setRecentTrades] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [sumRes, eqRes, pnlRes, sigRes, tradeRes] = await Promise.all([
        axios.get(`${API}/dashboard/summary`),
        axios.get(`${API}/metrics/equity-curve`),
        axios.get(`${API}/metrics/daily-pnl`),
        axios.get(`${API}/signals?limit=8`),
        axios.get(`${API}/trades?limit=8`),
      ]);
      setSummary(sumRes.data);
      setEquityCurve(eqRes.data);
      setDailyPnl(pnlRes.data);
      setRecentSignals(sigRes.data);
      setRecentTrades(tradeRes.data);
    } catch (e) {
      console.error("Dashboard fetch error:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleStartBot = async () => {
    try {
      await axios.post(`${API}/bot/start`, { strategy_name: "sma_crossover", symbols: ["RELIANCE", "INFY"], mode: "paper" });
      toast.success("Bot started in paper mode");
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to start bot");
    }
  };

  const handleStopBot = async () => {
    try {
      await axios.post(`${API}/bot/stop`, { reason: "Manual stop from dashboard" });
      toast.info("Bot stopped");
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to stop bot");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-zinc-500 font-mono text-sm">Loading dashboard...</div>
      </div>
    );
  }

  const s = summary || {};
  const isRunning = s.bot_status === "RUNNING";
  const pnlColor = s.daily_pnl >= 0 ? "text-profit" : "text-loss";
  const totalPnlColor = s.total_pnl >= 0 ? "text-profit" : "text-loss";

  return (
    <div data-testid="dashboard-page" className="p-4 md:p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight">Dashboard</h1>
          <p className="text-xs text-zinc-500 font-mono mt-0.5">
            {s.trading_mode?.toUpperCase()} MODE | Market: {s.market_status}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {s.kill_switch_active && (
            <Badge data-testid="kill-switch-badge" variant="destructive" className="pulse-danger text-xs">
              KILL SWITCH
            </Badge>
          )}
          {isRunning ? (
            <Button data-testid="stop-bot-btn" size="sm" variant="destructive" onClick={handleStopBot} className="gap-1.5 rounded-sm">
              <Square className="w-3 h-3" /> Stop
            </Button>
          ) : (
            <Button data-testid="start-bot-btn" size="sm" onClick={handleStartBot} className="gap-1.5 rounded-sm bg-emerald-600 hover:bg-emerald-500">
              <Play className="w-3 h-3" /> Start Bot
            </Button>
          )}
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
        <MetricCard testId="metric-daily-pnl" label="Daily P&L" value={`${s.daily_pnl >= 0 ? "+" : ""}${s.daily_pnl?.toFixed(2)}`} sub={`${s.daily_pnl_pct?.toFixed(2)}%`} icon={s.daily_pnl >= 0 ? TrendingUp : TrendingDown} color={pnlColor} />
        <MetricCard testId="metric-total-pnl" label="Total P&L" value={`${s.total_pnl >= 0 ? "+" : ""}${s.total_pnl?.toFixed(2)}`} icon={Activity} color={totalPnlColor} />
        <MetricCard testId="metric-positions" label="Open Positions" value={s.open_positions} icon={Target} />
        <MetricCard testId="metric-trades" label="Trades Today" value={s.total_trades_today} icon={Zap} />
        <MetricCard testId="metric-signals" label="Signals Today" value={s.total_signals_today} icon={ArrowUpRight} />
        <MetricCard testId="metric-winrate" label="Win Rate" value={`${s.win_rate?.toFixed(1)}%`} icon={Target} sub={`Strategy: ${s.active_strategy}`} />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">
        {/* Equity Curve */}
        <Card className="lg:col-span-2 bg-zinc-900 border-zinc-800 rounded-sm">
          <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
            <CardTitle className="text-sm font-medium text-zinc-300">Equity Curve</CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <div data-testid="equity-curve-chart" className="h-[240px]">
              {equityCurve.length > 1 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={equityCurve}>
                    <defs>
                      <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1E1E1E" />
                    <XAxis dataKey="timestamp" hide />
                    <YAxis stroke="#3F3F46" tick={{ fill: "#71717A", fontSize: 11, fontFamily: "JetBrains Mono" }} width={70} tickFormatter={(v) => `${(v/1000).toFixed(0)}k`} />
                    <Tooltip contentStyle={{ background: "#121212", border: "1px solid #27272A", borderRadius: "2px", fontFamily: "JetBrains Mono", fontSize: "12px" }} labelStyle={{ display: "none" }} />
                    <Area type="monotone" dataKey="equity" stroke="#3B82F6" fill="url(#eqGrad)" strokeWidth={1.5} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-zinc-600 text-sm font-mono">
                  Start the bot to see equity curve data
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Daily PnL */}
        <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
          <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
            <CardTitle className="text-sm font-medium text-zinc-300">Daily P&L</CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <div data-testid="daily-pnl-chart" className="h-[240px]">
              {dailyPnl.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dailyPnl}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1E1E1E" />
                    <XAxis dataKey="date" hide />
                    <YAxis stroke="#3F3F46" tick={{ fill: "#71717A", fontSize: 11, fontFamily: "JetBrains Mono" }} width={50} />
                    <Tooltip contentStyle={{ background: "#121212", border: "1px solid #27272A", borderRadius: "2px", fontFamily: "JetBrains Mono", fontSize: "12px" }} labelStyle={{ display: "none" }} />
                    <Bar dataKey="pnl" fill="#3B82F6" radius={[1, 1, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-zinc-600 text-sm font-mono">
                  No daily P&L data yet
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Signals & Trades */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
        {/* Recent Signals */}
        <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
          <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
            <CardTitle className="text-sm font-medium text-zinc-300">Recent Signals</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div data-testid="recent-signals-table" className="overflow-auto max-h-[280px]">
              <table className="w-full data-table">
                <thead className="sticky top-0 bg-zinc-900">
                  <tr>
                    <th>Symbol</th><th>Side</th><th>Strategy</th><th>Confidence</th><th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {recentSignals.length === 0 ? (
                    <tr><td colSpan={5} className="text-center text-zinc-600 py-8">No signals yet</td></tr>
                  ) : recentSignals.map((sig, i) => (
                    <tr key={i}>
                      <td className="text-white">{sig.symbol}</td>
                      <td><span className={sig.side === "BUY" ? "text-profit" : "text-loss"}>{sig.side}</span></td>
                      <td className="text-zinc-400">{sig.strategy_name}</td>
                      <td>
                        <div className="flex items-center gap-2">
                          <Progress value={sig.confidence * 100} className="h-1.5 w-12" />
                          <span className="text-zinc-400">{(sig.confidence * 100).toFixed(0)}%</span>
                        </div>
                      </td>
                      <td className="text-zinc-500 text-xs">{sig.timestamp?.substring(0, 16)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Recent Trades */}
        <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
          <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
            <CardTitle className="text-sm font-medium text-zinc-300">Recent Trades</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div data-testid="recent-trades-table" className="overflow-auto max-h-[280px]">
              <table className="w-full data-table">
                <thead className="sticky top-0 bg-zinc-900">
                  <tr>
                    <th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {recentTrades.length === 0 ? (
                    <tr><td colSpan={5} className="text-center text-zinc-600 py-8">No trades yet</td></tr>
                  ) : recentTrades.map((t, i) => (
                    <tr key={i}>
                      <td className="text-white">{t.symbol}</td>
                      <td><span className={t.side === "BUY" ? "text-profit" : "text-loss"}>{t.side}</span></td>
                      <td className="text-zinc-300">{t.quantity}</td>
                      <td className="text-zinc-300">{t.entry_price?.toFixed(2)}</td>
                      <td className={t.net_pnl >= 0 ? "text-profit" : "text-loss"}>
                        {t.net_pnl >= 0 ? "+" : ""}{t.net_pnl?.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function MetricCard({ testId, label, value, sub, icon: Icon, color = "text-white" }) {
  return (
    <div data-testid={testId} className="metric-card animate-fade-in">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-sans">{label}</span>
        {Icon && <Icon className={`w-3.5 h-3.5 ${color}`} strokeWidth={1.5} />}
      </div>
      <div className={`text-lg font-mono font-bold ${color}`}>{value ?? "---"}</div>
      {sub && <div className="text-[10px] text-zinc-500 mt-0.5 font-mono truncate">{sub}</div>}
    </div>
  );
}

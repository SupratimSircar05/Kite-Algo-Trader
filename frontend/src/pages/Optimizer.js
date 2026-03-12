import React, { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Grid3x3, Play, Clock, Trophy, TrendingUp, TrendingDown,
  ChevronDown, ChevronUp, Info, Crosshair, Layers, Activity, Save, History
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Progress } from "@/components/ui/progress";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DEFAULT_RANGES = {
  sma_crossover: {
    fast_period: { min: 5, max: 20, step: 1 },
    slow_period: { min: 15, max: 50, step: 5 },
  },
  opening_range_breakout: {
    opening_range_minutes: { min: 5, max: 30, step: 5 },
    breakout_buffer_pct: { min: 0.05, max: 0.5, step: 0.05 },
  },
  trendshift: {
    ema_fast: { min: 5, max: 13, step: 2 },
    ema_mid: { min: 13, max: 34, step: 3 },
    ema_slow: { min: 34, max: 89, step: 5 },
    supertrend_mult: { min: 2, max: 4, step: 0.5 },
    min_confidence: { min: 0.55, max: 0.75, step: 0.05 },
    ml_min_confidence: { min: 0.5, max: 0.7, step: 0.05 },
  },
};

const TRENDSHIFT_PRESETS = {
  safe: {
    ema_fast: { min: 6, max: 10, step: 2 },
    ema_mid: { min: 18, max: 28, step: 5 },
    ema_slow: { min: 50, max: 70, step: 10 },
    supertrend_mult: { min: 2.4, max: 3.0, step: 0.3 },
    min_confidence: { min: 0.62, max: 0.74, step: 0.06 },
    ml_min_confidence: { min: 0.56, max: 0.68, step: 0.06 },
  },
  balanced: DEFAULT_RANGES.trendshift,
  deep: {
    ema_fast: { min: 5, max: 15, step: 1 },
    ema_mid: { min: 13, max: 34, step: 3 },
    ema_slow: { min: 34, max: 89, step: 5 },
    supertrend_mult: { min: 2.0, max: 4.0, step: 0.25 },
    min_confidence: { min: 0.5, max: 0.8, step: 0.05 },
    ml_min_confidence: { min: 0.45, max: 0.75, step: 0.05 },
  },
};

export default function Optimizer() {
  const [strategies, setStrategies] = useState([]);
  const [pastResults, setPastResults] = useState([]);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState("");
  const [heatmapMetric, setHeatmapMetric] = useState("return_pct");
  const [expandedRow, setExpandedRow] = useState(null);
  const [activeJob, setActiveJob] = useState(null);
  const [recentJobs, setRecentJobs] = useState([]);
  const [savingDefaults, setSavingDefaults] = useState(false);
  const [preset, setPreset] = useState("balanced");

  const [form, setForm] = useState({
    strategy_name: "sma_crossover",
    symbol: "RELIANCE",
    start_date: "2024-01-01",
    end_date: "2025-06-01",
    initial_capital: 100000,
    quantity: 10,
    objective: "balanced",
    use_ml_filter: true,
  });
  const [paramRanges, setParamRanges] = useState(DEFAULT_RANGES.sma_crossover);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/jobs`, { params: { kind: "optimizer", limit: 8 } });
      setRecentJobs(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    axios.get(`${API}/strategies`).then(r => setStrategies(r.data)).catch(() => {});
    axios.get(`${API}/optimizer/results`).then(r => setPastResults(r.data)).catch(() => {});
    fetchJobs();
    const savedJobId = window.localStorage.getItem("kitealgo-optimizer-job-id");
    if (savedJobId) {
      axios.get(`${API}/jobs/${savedJobId}`).then((res) => setActiveJob(res.data)).catch(() => {
        window.localStorage.removeItem("kitealgo-optimizer-job-id");
      });
    }
  }, [fetchJobs]);

  useEffect(() => {
    if (!activeJob?.id || ["completed", "failed", "cancelled"].includes(activeJob.status)) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const res = await axios.get(`${API}/jobs/${activeJob.id}`);
        const job = res.data;
        setActiveJob(job);
        if (job.status === "completed") {
          window.localStorage.removeItem("kitealgo-optimizer-job-id");
          if (job.result?.result_id) {
            const detail = await axios.get(`${API}/optimizer/results/${job.result.result_id}`);
            setResult(detail.data);
            setExpandedRow(null);
            toast.success("Optimizer run completed successfully");
            axios.get(`${API}/optimizer/results`).then(r => setPastResults(r.data)).catch(() => {});
            fetchJobs();
          }
        }
        if (job.status === "failed") {
          window.localStorage.removeItem("kitealgo-optimizer-job-id");
          toast.error(job.error || "Optimizer job failed");
          fetchJobs();
        }
      } catch (e) {
        console.error(e);
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeJob, fetchJobs]);

  const onStrategyChange = (name) => {
    setForm(f => ({ ...f, strategy_name: name }));
    setParamRanges(name === "trendshift" ? TRENDSHIFT_PRESETS[preset] : (DEFAULT_RANGES[name] || {}));
  };

  const applyPreset = (value) => {
    setPreset(value);
    if (form.strategy_name === "trendshift") {
      setParamRanges(TRENDSHIFT_PRESETS[value]);
    }
  };

  const updateRange = (param, field, value) => {
    setParamRanges(prev => ({
      ...prev,
      [param]: { ...prev[param], [field]: Number(value) },
    }));
  };

  const addParam = () => {
    const name = prompt("Parameter name:");
    if (name && !paramRanges[name]) {
      setParamRanges(prev => ({ ...prev, [name]: { min: 1, max: 10, step: 1 } }));
    }
  };

  const removeParam = (name) => {
    setParamRanges(prev => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };

  const totalCombos = useMemo(() => {
    let total = 1;
    Object.values(paramRanges).forEach(r => {
      if (r.step > 0) {
        total *= Math.floor((r.max - r.min) / r.step) + 1;
      }
    });
    return total;
  }, [paramRanges]);

  const runOptimizer = async () => {
    setRunning(true);
    setProgress(`Queueing ${totalCombos} combinations...`);
    try {
      const fixed_params = form.strategy_name === "trendshift" ? { use_ml_filter: form.use_ml_filter } : {};
      const res = await axios.post(`${API}/optimizer/run`, {
        ...form,
        param_ranges: paramRanges,
        fixed_params,
        execution_mode: "queue",
      });
      if (res.data.status === "queued") {
        setActiveJob({ id: res.data.job_id, status: "queued", progress_pct: 0, message: res.data.message });
        window.localStorage.setItem("kitealgo-optimizer-job-id", res.data.job_id);
        toast.info(`Optimizer queued for ${res.data.total_combinations} valid combinations`);
        fetchJobs();
      } else {
        setResult(res.data);
        toast.success(`Optimization complete: ${res.data.total_combinations} combinations tested`);
        axios.get(`${API}/optimizer/results`).then(r => setPastResults(r.data)).catch(() => {});
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Optimization failed");
    } finally {
      setRunning(false);
      setProgress("");
    }
  };

  const loadPastResult = async (id) => {
    try {
      const res = await axios.get(`${API}/optimizer/results/${id}`);
      setResult(res.data);
      toast.info("Loaded past optimization result");
    } catch (e) {
      toast.error("Failed to load result");
    }
  };

  const applyBestDefaults = async () => {
    if (!result?.id) return;
    setSavingDefaults(true);
    try {
      await axios.post(`${API}/optimizer/results/${result.id}/apply-defaults`);
      toast.success("Best parameters saved as strategy defaults");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to save defaults");
    } finally {
      setSavingDefaults(false);
    }
  };

  const loadJobResult = async (job) => {
    if (!job?.result?.result_id) return;
    try {
      const res = await axios.get(`${API}/optimizer/results/${job.result.result_id}`);
      setResult(res.data);
      setExpandedRow(null);
      toast.info("Loaded queued optimization result");
    } catch (e) {
      toast.error("Failed to load queued optimization result");
    }
  };

  return (
    <TooltipProvider delayDuration={150}>
      <div data-testid="optimizer-page" className="p-4 md:p-6 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-white tracking-tight flex items-center gap-2">
              <Grid3x3 className="w-5 h-5 text-amber-500" /> Strategy Optimizer
            </h1>
            <p className="text-xs text-zinc-500 font-mono mt-0.5">
              Queue large searches safely, monitor progress, then save best parameters as defaults
            </p>
          </div>
        </div>

        {activeJob && (
          <Card data-testid="optimizer-job-card" className="bg-amber-950/20 border-amber-800/50 rounded-sm">
            <CardContent className="p-4 space-y-3">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-white">
                    <Activity className="h-4 w-4 text-amber-400" /> Optimizer Queue Status
                  </div>
                  <div data-testid="optimizer-job-message" className="mt-1 text-xs font-mono text-zinc-400">
                    {activeJob.message || "Queued"}
                  </div>
                </div>
                <div data-testid="optimizer-job-state" className="text-xs font-mono text-amber-300">
                  {activeJob.status?.toUpperCase()} · {(activeJob.progress_pct || 0).toFixed(0)}%
                </div>
              </div>
              <Progress data-testid="optimizer-job-progress" value={activeJob.progress_pct || 0} className="h-2 bg-amber-950/40 [&>div]:bg-amber-500" />
            </CardContent>
          </Card>
        )}

        {/* Config Panel */}
        <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
          <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
            <CardTitle className="text-sm font-medium text-zinc-300 flex items-center gap-2">
              <Crosshair className="w-3.5 h-3.5 text-zinc-500" /> Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-4">
            {/* Row 1: Strategy, Symbol, Dates, Capital, Qty */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              <div>
                <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Strategy</label>
                <Select value={form.strategy_name} onValueChange={onStrategyChange}>
                  <SelectTrigger data-testid="opt-strategy-select" className="h-8 text-xs bg-zinc-800 border-zinc-700">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sma_crossover">SMA Crossover</SelectItem>
                    <SelectItem value="opening_range_breakout">ORB Strategy</SelectItem>
                    <SelectItem value="trendshift">TrendShift</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Symbol</label>
                <Select value={form.symbol} onValueChange={(v) => setForm(f => ({ ...f, symbol: v }))}>
                  <SelectTrigger data-testid="opt-symbol-select" className="h-8 text-xs bg-zinc-800 border-zinc-700">
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
                <Input data-testid="opt-from-date" type="date" value={form.start_date} onChange={(e) => setForm(f => ({ ...f, start_date: e.target.value }))} className="h-8 text-xs bg-zinc-800 border-zinc-700" />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">To</label>
                <Input data-testid="opt-to-date" type="date" value={form.end_date} onChange={(e) => setForm(f => ({ ...f, end_date: e.target.value }))} className="h-8 text-xs bg-zinc-800 border-zinc-700" />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Capital</label>
                <Input data-testid="opt-capital" type="number" value={form.initial_capital} onChange={(e) => setForm(f => ({ ...f, initial_capital: Number(e.target.value) }))} className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Quantity</label>
                <Input data-testid="opt-quantity" type="number" value={form.quantity} onChange={(e) => setForm(f => ({ ...f, quantity: Number(e.target.value) }))} className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Optimization Objective</label>
                <Select value={form.objective} onValueChange={(value) => setForm((f) => ({ ...f, objective: value }))}>
                  <SelectTrigger data-testid="opt-objective-select" className="h-8 text-xs bg-zinc-800 border-zinc-700">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="balanced">Balanced Score</SelectItem>
                    <SelectItem value="profit">Profit First</SelectItem>
                    <SelectItem value="win_rate">Win Rate Focus</SelectItem>
                    <SelectItem value="low_slippage">Low Slippage Focus</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {form.strategy_name === "trendshift" && (
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">TrendShift Preset</label>
                  <Select value={preset} onValueChange={applyPreset}>
                    <SelectTrigger data-testid="opt-trendshift-preset-select" className="h-8 text-xs bg-zinc-800 border-zinc-700">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="safe">Safe Search</SelectItem>
                      <SelectItem value="balanced">Balanced Search</SelectItem>
                      <SelectItem value="deep">Deep Search</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
              <div className="rounded-sm border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-xs font-mono text-zinc-400 flex items-center justify-between">
                <span>Estimated combinations</span>
                <span data-testid="optimizer-combo-estimate" className="text-white">{totalCombos}</span>
              </div>
              {form.strategy_name === "trendshift" && (
                <div className="rounded-sm border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-xs flex items-center gap-2">
                  <label data-testid="opt-ml-filter-toggle" className="flex items-center gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={form.use_ml_filter}
                      onChange={(e) => setForm(f => ({...f, use_ml_filter: e.target.checked}))}
                      className="w-3.5 h-3.5 rounded-sm bg-zinc-800 border-zinc-600 accent-amber-500"
                    />
                    <span className="text-zinc-400">ML Regime Filter</span>
                  </label>
                </div>
              )}
            </div>

            {/* Parameter Ranges */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-[10px] uppercase tracking-wider text-zinc-500 flex items-center gap-1">
                  <Layers className="w-3 h-3" /> Parameter Ranges
                </label>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-zinc-500">{totalCombos} combinations</span>
                  <Button data-testid="add-param-btn" onClick={addParam} size="sm" variant="outline" className="h-6 text-[10px] rounded-sm border-zinc-700 px-2">
                    + Add Param
                  </Button>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                {Object.entries(paramRanges).map(([param, range]) => (
                  <div key={param} className="bg-[#050505] border border-zinc-800 rounded-sm p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-mono text-amber-400">{param.replace(/_/g, " ")}</span>
                      <button
                        data-testid={`remove-param-${param}`}
                        onClick={() => removeParam(param)}
                        className="text-[10px] text-zinc-600 hover:text-red-400 transition-colors"
                      >
                        remove
                      </button>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <label className="text-[9px] uppercase text-zinc-600 block mb-0.5">Min</label>
                        <Input
                          data-testid={`range-${param}-min`}
                          type="number"
                          step="any"
                          value={range.min}
                          onChange={(e) => updateRange(param, "min", e.target.value)}
                          className="h-7 text-xs bg-transparent border-0 border-b border-zinc-700 rounded-none font-mono text-emerald-400 px-0 focus:border-blue-500"
                        />
                      </div>
                      <div>
                        <label className="text-[9px] uppercase text-zinc-600 block mb-0.5">Max</label>
                        <Input
                          data-testid={`range-${param}-max`}
                          type="number"
                          step="any"
                          value={range.max}
                          onChange={(e) => updateRange(param, "max", e.target.value)}
                          className="h-7 text-xs bg-transparent border-0 border-b border-zinc-700 rounded-none font-mono text-emerald-400 px-0 focus:border-blue-500"
                        />
                      </div>
                      <div>
                        <label className="text-[9px] uppercase text-zinc-600 block mb-0.5">Step</label>
                        <Input
                          data-testid={`range-${param}-step`}
                          type="number"
                          step="any"
                          value={range.step}
                          onChange={(e) => updateRange(param, "step", e.target.value)}
                          className="h-7 text-xs bg-transparent border-0 border-b border-zinc-700 rounded-none font-mono text-emerald-400 px-0 focus:border-blue-500"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Run Button */}
            <div className="flex items-center gap-3">
              <Button
                data-testid="run-optimizer-btn"
                onClick={runOptimizer}
                disabled={running || totalCombos === 0}
                className="h-9 px-6 rounded-sm bg-amber-600 hover:bg-amber-500 text-black font-semibold text-xs gap-1.5"
              >
                {running ? <Clock className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                {running ? progress : `Queue Optimizer (${totalCombos} combos)`}
              </Button>
              {totalCombos > 500 && (
                <span className="text-[10px] text-amber-500 font-mono flex items-center gap-1">
                  <Info className="w-3 h-3" /> Large grid automatically runs in the reliable queue
                </span>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Results */}
        {result && (
          <>
            {/* Best Result Banner */}
            <Card className="bg-emerald-950/20 border-emerald-800/50 rounded-sm">
              <CardContent className="p-4">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-emerald-900/50 rounded-sm flex items-center justify-center">
                    <Trophy className="w-5 h-5 text-amber-400" />
                  </div>
                  <div className="flex-1">
                    <div className="text-xs text-zinc-400 mb-0.5">Best Parameters Found</div>
                    <div className="flex items-center gap-4 flex-wrap">
                      {result.best_params && Object.entries(result.best_params).map(([k, v]) => (
                        <span key={k} className="font-mono text-sm">
                          <span className="text-zinc-500">{k}=</span>
                          <span className="text-emerald-400 font-bold">{typeof v === "number" ? v.toFixed(v % 1 === 0 ? 0 : 2) : v}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`text-xl font-mono font-bold ${result.best_return_pct >= 0 ? "text-profit" : "text-loss"}`}>
                      {result.best_return_pct >= 0 ? "+" : ""}{result.best_return_pct?.toFixed(2)}%
                    </div>
                    <div className="text-[10px] text-zinc-500 font-mono">{result.total_combinations} tested · {result.objective}</div>
                  </div>
                  <Button
                    data-testid="optimizer-save-defaults-button"
                    onClick={applyBestDefaults}
                    disabled={savingDefaults}
                    className="rounded-sm bg-emerald-600 hover:bg-emerald-500 text-xs gap-1.5"
                  >
                    <Save className="w-3.5 h-3.5" /> {savingDefaults ? "Saving..." : "Save as Defaults"}
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Tabs defaultValue="heatmap">
              <TabsList className="bg-zinc-900 border border-zinc-800 rounded-sm">
                <TabsTrigger data-testid="tab-heatmap" value="heatmap" className="text-xs rounded-sm gap-1.5">
                  <Grid3x3 className="w-3 h-3" /> Heatmap
                </TabsTrigger>
                <TabsTrigger data-testid="tab-grid-results" value="table" className="text-xs rounded-sm gap-1.5">
                  <Layers className="w-3 h-3" /> Full Results ({result.results?.length})
                </TabsTrigger>
              </TabsList>

              <TabsContent value="heatmap">
                {result.heatmap ? (
                  <HeatmapView heatmap={result.heatmap} metric={heatmapMetric} onMetricChange={setHeatmapMetric} bestParams={result.best_params} />
                ) : (
                  <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
                    <CardContent className="p-8 text-center text-zinc-600 font-mono text-sm">
                      Need at least 2 parameters for heatmap visualization
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              <TabsContent value="table">
                <ResultsTable results={result.results || []} expandedRow={expandedRow} setExpandedRow={setExpandedRow} />
              </TabsContent>
            </Tabs>
          </>
        )}

        {/* Past Results */}
        {pastResults.length > 0 && (
          <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
            <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
              <CardTitle className="text-sm font-medium text-zinc-300">Previous Optimizations</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-auto max-h-[200px]">
                <table className="w-full data-table">
                  <thead className="sticky top-0 bg-zinc-900 z-10">
                    <tr>
                      <th>Strategy</th><th>Symbol</th><th>Best Return</th><th>Combos</th><th>Best Params</th><th>Date</th><th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {pastResults.map((r, i) => (
                      <tr key={i} className="cursor-pointer" onClick={() => loadPastResult(r.id)}>
                        <td className="text-white">{r.strategy_name}</td>
                        <td className="text-zinc-300">{r.symbol}</td>
                        <td className={r.best_return_pct >= 0 ? "text-profit" : "text-loss"}>
                          {r.best_return_pct?.toFixed(2)}%
                        </td>
                        <td className="text-zinc-400">{r.total_combinations}</td>
                        <td className="text-zinc-400 font-mono text-xs max-w-[200px] truncate">
                          {r.best_params ? Object.entries(r.best_params).map(([k, v]) => `${k}=${v}`).join(", ") : "-"}
                        </td>
                        <td className="text-zinc-500 text-xs">{r.created_at?.substring(0, 10)}</td>
                        <td>
                          <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400 hover:text-white cursor-pointer">Load</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {recentJobs.length > 0 && (
          <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
            <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
              <CardTitle className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                <History className="w-4 h-4 text-zinc-500" /> Queued Optimizer Runs
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-auto max-h-[220px]">
                <table className="w-full data-table" data-testid="optimizer-jobs-table">
                  <thead className="sticky top-0 bg-zinc-900 z-10">
                    <tr>
                      <th>Strategy</th><th>Symbol</th><th>Status</th><th>Progress</th><th>Objective</th><th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentJobs.map((job) => (
                      <tr key={job.id} data-testid={`optimizer-job-row-${job.id}`}>
                        <td className="text-white">{job.meta?.strategy_name || "--"}</td>
                        <td className="text-zinc-300">{job.meta?.symbol || "--"}</td>
                        <td className="text-zinc-400">{job.status}</td>
                        <td className="text-zinc-300">{(job.progress_pct || 0).toFixed(0)}%</td>
                        <td className="text-zinc-500">{job.meta?.objective || "balanced"}</td>
                        <td>
                          <Button
                            data-testid={`optimizer-job-load-${job.id}`}
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
      </div>
    </TooltipProvider>
  );
}

/* ================ HEATMAP COMPONENT ================ */
function HeatmapView({ heatmap, metric, onMetricChange, bestParams }) {
  const { x_param, y_param, x_values, y_values, grid } = heatmap;

  const metricKey = metric === "return_pct" ? "return_pct"
    : metric === "sharpe" ? "sharpe"
    : metric === "win_rate" ? "win_rate"
    : metric === "drawdown" ? "drawdown"
    : metric === "objective_score" ? "objective_score"
    : "return_pct";

  // Calculate min/max for color scaling
  const allVals = grid.flat().map(c => c[metricKey]);
  const minVal = Math.min(...allVals);
  const maxVal = Math.max(...allVals);
  const range = maxVal - minVal || 1;

  const getCellColor = (val) => {
    const norm = (val - minVal) / range;
    if (metricKey === "drawdown") {
      // Invert: lower drawdown = better = green
      const inv = 1 - norm;
      if (inv > 0.66) return `rgba(34, 197, 94, ${0.2 + inv * 0.6})`;
      if (inv > 0.33) return `rgba(234, 179, 8, ${0.2 + inv * 0.5})`;
      return `rgba(239, 68, 68, ${0.2 + (1 - inv) * 0.6})`;
    }
    if (norm > 0.66) return `rgba(34, 197, 94, ${0.2 + norm * 0.6})`;
    if (norm > 0.33) return `rgba(234, 179, 8, ${0.2 + norm * 0.5})`;
    return `rgba(239, 68, 68, ${0.2 + (1 - norm) * 0.6})`;
  };

  const isBest = (x, y) => {
    if (!bestParams) return false;
    return bestParams[x_param] === x && (!y_param || bestParams[y_param] === y);
  };

  const [hoveredCell, setHoveredCell] = useState(null);

  const cellSize = Math.max(32, Math.min(56, 600 / Math.max(x_values.length, y_values.length)));

  return (
    <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
      <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3 flex flex-row items-center justify-between">
        <CardTitle className="text-sm font-medium text-zinc-300">
          Parameter Heatmap
          {y_param && <span className="text-zinc-500 font-normal ml-2">({y_param} vs {x_param})</span>}
        </CardTitle>
        <Select value={metric} onValueChange={onMetricChange}>
          <SelectTrigger data-testid="heatmap-metric-select" className="w-40 h-7 text-[10px] bg-zinc-800 border-zinc-700">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="return_pct">Return %</SelectItem>
            <SelectItem value="sharpe">Sharpe Ratio</SelectItem>
            <SelectItem value="win_rate">Win Rate %</SelectItem>
            <SelectItem value="drawdown">Max Drawdown %</SelectItem>
            <SelectItem value="objective_score">Objective Score</SelectItem>
          </SelectContent>
        </Select>
      </CardHeader>
      <CardContent className="p-4">
        <div data-testid="heatmap-grid" className="overflow-auto">
          <div className="inline-block">
            {/* X-axis label */}
            <div className="flex items-end mb-1" style={{ paddingLeft: y_param ? 60 : 0 }}>
              {x_values.map((x, i) => (
                <div
                  key={i}
                  className="text-[10px] font-mono text-zinc-500 text-center"
                  style={{ width: cellSize, minWidth: cellSize }}
                >
                  {typeof x === "number" ? (x % 1 === 0 ? x : x.toFixed(2)) : x}
                </div>
              ))}
            </div>

            {/* Grid rows */}
            {grid.map((row, yi) => (
              <div key={yi} className="flex items-center">
                {/* Y-axis label */}
                {y_param && (
                  <div className="text-[10px] font-mono text-zinc-500 text-right pr-2" style={{ width: 56, minWidth: 56 }}>
                    {typeof y_values[yi] === "number" ? (y_values[yi] % 1 === 0 ? y_values[yi] : y_values[yi].toFixed(2)) : y_values[yi]}
                  </div>
                )}
                {row.map((cell, xi) => {
                  const val = cell[metricKey];
                  const best = isBest(cell.x, cell.y);
                  return (
                    <Tooltip key={xi}>
                      <TooltipTrigger asChild>
                        <div
                          data-testid={`heatmap-cell-${xi}-${yi}`}
                          className={`border border-zinc-800/50 flex items-center justify-center cursor-crosshair transition-all hover:z-10 hover:scale-110 hover:border-white/30 ${best ? "ring-2 ring-amber-400 z-20" : ""}`}
                          style={{
                            width: cellSize,
                            height: cellSize,
                            minWidth: cellSize,
                            backgroundColor: getCellColor(val),
                          }}
                          onMouseEnter={() => setHoveredCell(cell)}
                          onMouseLeave={() => setHoveredCell(null)}
                        >
                          <span className="text-[9px] font-mono text-white/80 font-medium">
                            {typeof val === "number" ? val.toFixed(1) : val}
                          </span>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="bg-zinc-900 border-zinc-700 p-2">
                        <div className="text-[10px] font-mono space-y-0.5">
                          <div className="text-zinc-400">{x_param}={cell.x}{y_param ? `, ${y_param}=${cell.y}` : ""}</div>
                          <div className={cell.return_pct >= 0 ? "text-emerald-400" : "text-red-400"}>Return: {cell.return_pct?.toFixed(2)}%</div>
                          <div className="text-zinc-300">Sharpe: {cell.sharpe?.toFixed(2)}</div>
                          <div className="text-zinc-300">Win Rate: {cell.win_rate?.toFixed(1)}%</div>
                          <div className="text-zinc-300">Trades: {cell.trades}</div>
                          <div className="text-zinc-300">Max DD: {cell.drawdown?.toFixed(2)}%</div>
                          {best && <div className="text-amber-400 font-bold">BEST</div>}
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  );
                })}
              </div>
            ))}

            {/* Axis labels */}
            <div className="mt-2 flex items-center" style={{ paddingLeft: y_param ? 60 : 0 }}>
              <span className="text-[10px] text-zinc-500 font-mono">{x_param} &rarr;</span>
            </div>
            {y_param && (
              <div className="absolute -left-2 top-1/2 -rotate-90 text-[10px] text-zinc-500 font-mono">
                {y_param} &rarr;
              </div>
            )}
          </div>
        </div>

        {/* Color legend */}
        <div className="flex items-center gap-4 mt-4 pt-3 border-t border-zinc-800">
          <span className="text-[10px] text-zinc-500">Scale:</span>
          <div className="flex items-center gap-1">
            <div className="w-4 h-3 rounded-sm" style={{ backgroundColor: "rgba(239, 68, 68, 0.6)" }} />
            <span className="text-[10px] text-zinc-500 font-mono">{metricKey === "drawdown" ? "High" : "Low"}</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-4 h-3 rounded-sm" style={{ backgroundColor: "rgba(234, 179, 8, 0.5)" }} />
            <span className="text-[10px] text-zinc-500 font-mono">Mid</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-4 h-3 rounded-sm" style={{ backgroundColor: "rgba(34, 197, 94, 0.6)" }} />
            <span className="text-[10px] text-zinc-500 font-mono">{metricKey === "drawdown" ? "Low" : "High"}</span>
          </div>
          <div className="flex items-center gap-1 ml-2">
            <div className="w-4 h-3 rounded-sm ring-2 ring-amber-400" style={{ backgroundColor: "rgba(34, 197, 94, 0.4)" }} />
            <span className="text-[10px] text-amber-400 font-mono">Best</span>
          </div>
        </div>

        {/* Hover detail */}
        {hoveredCell && (
          <div className="mt-2 p-2 bg-zinc-800/50 border border-zinc-700 rounded-sm">
            <div className="flex items-center gap-6 text-xs font-mono">
              <span className="text-zinc-500">{x_param}=<span className="text-white">{hoveredCell.x}</span></span>
              {y_param && <span className="text-zinc-500">{y_param}=<span className="text-white">{hoveredCell.y}</span></span>}
              <span className={hoveredCell.return_pct >= 0 ? "text-emerald-400" : "text-red-400"}>
                Ret: {hoveredCell.return_pct?.toFixed(2)}%
              </span>
              <span className="text-zinc-300">Sharpe: {hoveredCell.sharpe?.toFixed(2)}</span>
              <span className="text-zinc-300">WR: {hoveredCell.win_rate?.toFixed(1)}%</span>
              <span className="text-zinc-300">DD: {hoveredCell.drawdown?.toFixed(2)}%</span>
              <span className="text-zinc-300">Trades: {hoveredCell.trades}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ================ RESULTS TABLE ================ */
function ResultsTable({ results, expandedRow, setExpandedRow }) {
  const [sortKey, setSortKey] = useState("objective_score");
  const [sortDir, setSortDir] = useState("desc");

  const sorted = useMemo(() => {
    return [...results].sort((a, b) => {
      const av = a[sortKey] ?? 0;
      const bv = b[sortKey] ?? 0;
      return sortDir === "desc" ? bv - av : av - bv;
    });
  }, [results, sortKey, sortDir]);

  const toggleSort = (key) => {
    if (sortKey === key) {
      setSortDir(d => d === "desc" ? "asc" : "desc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return null;
    return sortDir === "desc" ? <ChevronDown className="w-3 h-3 inline" /> : <ChevronUp className="w-3 h-3 inline" />;
  };

  return (
    <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
      <CardContent className="p-0">
        <div className="overflow-auto max-h-[500px]">
          <table className="w-full data-table">
            <thead className="sticky top-0 bg-zinc-900 z-10">
              <tr>
                <th className="w-8">#</th>
                <th>Parameters</th>
                <th className="cursor-pointer select-none" onClick={() => toggleSort("objective_score")}>
                  Score <SortIcon col="objective_score" />
                </th>
                <th className="cursor-pointer select-none" onClick={() => toggleSort("total_return_pct")}>
                  Return % <SortIcon col="total_return_pct" />
                </th>
                <th className="cursor-pointer select-none" onClick={() => toggleSort("total_trades")}>
                  Trades <SortIcon col="total_trades" />
                </th>
                <th className="cursor-pointer select-none" onClick={() => toggleSort("win_rate")}>
                  Win Rate <SortIcon col="win_rate" />
                </th>
                <th className="cursor-pointer select-none" onClick={() => toggleSort("max_drawdown_pct")}>
                  Max DD <SortIcon col="max_drawdown_pct" />
                </th>
                <th className="cursor-pointer select-none" onClick={() => toggleSort("sharpe_ratio")}>
                  Sharpe <SortIcon col="sharpe_ratio" />
                </th>
                <th className="cursor-pointer select-none" onClick={() => toggleSort("profit_factor")}>
                  PF <SortIcon col="profit_factor" />
                </th>
                <th className="cursor-pointer select-none" onClick={() => toggleSort("expectancy")}>
                  Expect. <SortIcon col="expectancy" />
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r, i) => (
                <tr
                  key={i}
                  className={`cursor-pointer ${i === 0 && sortKey === "total_return_pct" && sortDir === "desc" ? "bg-emerald-950/20" : ""}`}
                  onClick={() => setExpandedRow(expandedRow === i ? null : i)}
                >
                  <td className="text-zinc-500">{i + 1}</td>
                  <td className="font-mono text-xs">
                    {Object.entries(r.params).map(([k, v]) => (
                      <span key={k} className="mr-2">
                        <span className="text-zinc-500">{k}=</span>
                        <span className="text-amber-400">{typeof v === "number" ? (v % 1 === 0 ? v : v.toFixed(2)) : v}</span>
                      </span>
                    ))}
                  </td>
                  <td className="text-amber-400 font-bold">{r.objective_score?.toFixed(2)}</td>
                  <td className={r.total_return_pct >= 0 ? "text-profit font-bold" : "text-loss font-bold"}>
                    {r.total_return_pct >= 0 ? "+" : ""}{r.total_return_pct?.toFixed(2)}%
                  </td>
                  <td className="text-zinc-300">{r.total_trades}</td>
                  <td className="text-zinc-300">{r.win_rate?.toFixed(1)}%</td>
                  <td className="text-loss">{r.max_drawdown_pct?.toFixed(2)}%</td>
                  <td className="text-zinc-300">{r.sharpe_ratio?.toFixed(2)}</td>
                  <td className="text-zinc-300">{r.profit_factor?.toFixed(2)}</td>
                  <td className="text-zinc-300">{r.expectancy?.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

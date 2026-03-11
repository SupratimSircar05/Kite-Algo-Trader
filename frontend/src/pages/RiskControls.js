import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ShieldAlert, AlertTriangle, Power, Save } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function RiskControls() {
  const [config, setConfig] = useState(null);
  const [saving, setSaving] = useState(false);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/risk/config`);
      setConfig(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/risk/config`, config);
      toast.success("Risk controls saved");
    } catch (e) {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  };

  const toggleKillSwitch = async () => {
    const newState = !config.kill_switch_active;
    try {
      await axios.post(`${API}/risk/kill-switch?active=${newState}&reason=${newState ? "Manual activation from dashboard" : ""}`);
      setConfig(c => ({...c, kill_switch_active: newState, kill_switch_reason: newState ? "Manual activation from dashboard" : null}));
      toast[newState ? "error" : "success"](newState ? "KILL SWITCH ACTIVATED" : "Kill switch deactivated");
    } catch (e) {
      toast.error("Failed to toggle kill switch");
    }
  };

  if (!config) {
    return <div className="flex items-center justify-center h-full text-zinc-500 font-mono text-sm">Loading risk config...</div>;
  }

  const updateField = (field, value) => setConfig(c => ({...c, [field]: value}));

  return (
    <div data-testid="risk-controls-page" className="p-4 md:p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-amber-500" /> Risk Controls
          </h1>
          <p className="text-xs text-zinc-500 font-mono mt-0.5">
            Configure safety guardrails and position limits
          </p>
        </div>
        <Button data-testid="save-risk-btn" onClick={handleSave} disabled={saving} size="sm" className="rounded-sm bg-blue-600 hover:bg-blue-500 gap-1.5">
          <Save className="w-3 h-3" /> {saving ? "Saving..." : "Save Changes"}
        </Button>
      </div>

      {/* Kill Switch */}
      <Card className={`rounded-sm border-2 transition-all ${config.kill_switch_active ? "border-red-700 bg-red-950/30 kill-switch-active" : "border-zinc-800 bg-zinc-900"}`}>
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-sm flex items-center justify-center ${config.kill_switch_active ? "bg-red-900/80" : "bg-zinc-800"}`}>
                <Power className={`w-6 h-6 ${config.kill_switch_active ? "text-red-400" : "text-zinc-400"}`} />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white tracking-tight">KILL SWITCH</h2>
                <p className="text-xs text-zinc-500 font-mono">
                  {config.kill_switch_active ? `ACTIVE: ${config.kill_switch_reason || "No reason"}` : "Emergency stop - halts all trading immediately"}
                </p>
              </div>
            </div>
            <Button
              data-testid="kill-switch-toggle"
              onClick={toggleKillSwitch}
              className={`h-10 px-6 rounded-sm font-mono uppercase tracking-widest text-xs font-bold transition-all ${
                config.kill_switch_active
                  ? "bg-zinc-700 hover:bg-zinc-600 text-white"
                  : "bg-red-700 hover:bg-red-600 text-white border-2 border-red-900 shadow-[0_0_15px_rgba(239,68,68,0.3)]"
              }`}
            >
              {config.kill_switch_active ? "DEACTIVATE" : "ACTIVATE"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Risk Limits */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Loss Limits */}
        <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
          <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
            <CardTitle className="text-sm font-medium text-zinc-300 flex items-center gap-2">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500" /> Loss Limits
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-4">
            <RiskField label="Max Daily Loss (INR)" testId="risk-max-daily-loss" value={config.max_daily_loss} onChange={(v) => updateField("max_daily_loss", Number(v))} />
            <RiskField label="Max Daily Loss (%)" testId="risk-max-daily-loss-pct" value={config.max_daily_loss_pct} onChange={(v) => updateField("max_daily_loss_pct", Number(v))} step="0.1" />
            <RiskField label="Max Consecutive Losses" testId="risk-max-consec-losses" value={config.max_consecutive_losses} onChange={(v) => updateField("max_consecutive_losses", Number(v))} />
            <RiskField label="Max Slippage (%)" testId="risk-max-slippage" value={config.max_slippage_pct} onChange={(v) => updateField("max_slippage_pct", Number(v))} step="0.1" />
          </CardContent>
        </Card>

        {/* Position Limits */}
        <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
          <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
            <CardTitle className="text-sm font-medium text-zinc-300">Position Limits</CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-4">
            <RiskField label="Max Position Size (qty)" testId="risk-max-pos-size" value={config.max_position_size} onChange={(v) => updateField("max_position_size", Number(v))} />
            <RiskField label="Max Position Value (INR)" testId="risk-max-pos-value" value={config.max_position_value} onChange={(v) => updateField("max_position_value", Number(v))} />
            <RiskField label="Max Open Positions" testId="risk-max-open-pos" value={config.max_open_positions} onChange={(v) => updateField("max_open_positions", Number(v))} />
            <RiskField label="Max Orders Per Day" testId="risk-max-orders" value={config.max_orders_per_day} onChange={(v) => updateField("max_orders_per_day", Number(v))} />
          </CardContent>
        </Card>

        {/* Safety Controls */}
        <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
          <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
            <CardTitle className="text-sm font-medium text-zinc-300">Safety Controls</CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-4">
            <RiskField label="Cooldown After Exit (sec)" testId="risk-cooldown" value={config.cooldown_seconds} onChange={(v) => updateField("cooldown_seconds", Number(v))} />
            <div className="flex items-center justify-between">
              <label className="text-[10px] uppercase tracking-wider text-zinc-500">Circuit Breaker</label>
              <Switch data-testid="risk-circuit-breaker" checked={config.enable_circuit_breaker} onCheckedChange={(v) => updateField("enable_circuit_breaker", v)} />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">No-Trade Start</label>
              <Input data-testid="risk-no-trade-start" type="time" value={config.no_trade_start || ""} onChange={(e) => updateField("no_trade_start", e.target.value)} className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">No-Trade End</label>
              <Input data-testid="risk-no-trade-end" type="time" value={config.no_trade_end || ""} onChange={(e) => updateField("no_trade_end", e.target.value)} className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Symbol Filters */}
      <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
        <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
          <CardTitle className="text-sm font-medium text-zinc-300">Symbol Filters</CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Whitelist (comma-separated, empty = all allowed)</label>
              <Input
                data-testid="risk-whitelist"
                value={(config.symbol_whitelist || []).join(", ")}
                onChange={(e) => updateField("symbol_whitelist", e.target.value.split(",").map(s => s.trim()).filter(Boolean))}
                placeholder="RELIANCE, INFY, TCS"
                className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Blacklist (comma-separated)</label>
              <Input
                data-testid="risk-blacklist"
                value={(config.symbol_blacklist || []).join(", ")}
                onChange={(e) => updateField("symbol_blacklist", e.target.value.split(",").map(s => s.trim()).filter(Boolean))}
                placeholder="ADANIENT, ADANIPORT"
                className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono"
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function RiskField({ label, testId, value, onChange, step = "1" }) {
  return (
    <div>
      <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">{label}</label>
      <Input
        data-testid={testId}
        type="number"
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono"
      />
    </div>
  );
}

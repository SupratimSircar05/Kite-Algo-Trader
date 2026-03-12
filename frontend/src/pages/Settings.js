import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Settings as SettingsIcon, Save, RefreshCw, Key, Globe, Database, Bell } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [instruments, setInstruments] = useState([]);
  const [health, setHealth] = useState(null);
  const [authStatus, setAuthStatus] = useState(null);
  const [alertStatus, setAlertStatus] = useState(null);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [setRes, instRes, healthRes] = await Promise.all([
        axios.get(`${API}/settings`),
        axios.get(`${API}/instruments`),
        axios.get(`${API}/health`),
      ]);
      setSettings(setRes.data);
      setInstruments(instRes.data);
      setHealth(healthRes.data);
      const [authRes, alertsRes] = await Promise.all([
        axios.get(`${API}/auth/zerodha/status`),
        axios.get(`${API}/alerts/status`),
      ]);
      setAuthStatus(authRes.data);
      setAlertStatus(alertsRes.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/settings`, settings);
      toast.success("Settings saved");
    } catch (e) {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await axios.post(`${API}/instruments/sync`);
      toast.success(`Synced ${res.data.synced} instruments`);
      fetchData();
    } catch (e) {
      toast.error("Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const handleInit = async () => {
    try {
      await axios.post(`${API}/init`);
      toast.success("Database initialized");
      fetchData();
    } catch (e) {
      toast.error("Init failed");
    }
  };

  const handleZerodhaConnect = async () => {
    try {
      const res = await axios.get(`${API}/auth/zerodha/start`);
      if (!res.data.configured || !res.data.login_url) {
        toast.error(res.data.reason || "Add your Zerodha API key first");
        return;
      }
      window.open(res.data.login_url, "_blank", "noopener,noreferrer");
      toast.info("Opened Zerodha login in a new tab");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to start Zerodha auth flow");
    }
  };

  const handleTestAlert = async () => {
    try {
      const res = await axios.post(`${API}/alerts/test`);
      if (res.data.status === "sent") {
        toast.success("Test alert sent");
      } else {
        toast.info(res.data.reason || "Alert skipped");
      }
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to test alerts");
    }
  };

  if (!settings) {
    return <div className="flex items-center justify-center h-full text-zinc-500 font-mono text-sm">Loading settings...</div>;
  }

  const updateField = (field, value) => setSettings(s => ({...s, [field]: value}));

  return (
    <div data-testid="settings-page" className="p-4 md:p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight flex items-center gap-2">
            <SettingsIcon className="w-5 h-5 text-zinc-400" /> Settings
          </h1>
          <p className="text-xs text-zinc-500 font-mono mt-0.5">
            Configure API credentials, trading mode, and system settings
          </p>
        </div>
        <Button data-testid="save-settings-btn" onClick={handleSave} disabled={saving} size="sm" className="rounded-sm bg-blue-600 hover:bg-blue-500 gap-1.5">
          <Save className="w-3 h-3" /> {saving ? "Saving..." : "Save All"}
        </Button>
      </div>

      <Tabs defaultValue="credentials">
        <TabsList className="bg-zinc-900 border border-zinc-800 rounded-sm">
          <TabsTrigger data-testid="settings-tab-credentials" value="credentials" className="text-xs rounded-sm gap-1.5"><Key className="w-3 h-3" /> Credentials</TabsTrigger>
          <TabsTrigger data-testid="settings-tab-trading" value="trading" className="text-xs rounded-sm gap-1.5"><Globe className="w-3 h-3" /> Trading</TabsTrigger>
          <TabsTrigger data-testid="settings-tab-system" value="system" className="text-xs rounded-sm gap-1.5"><Database className="w-3 h-3" /> System</TabsTrigger>
          <TabsTrigger data-testid="settings-tab-alerts" value="alerts" className="text-xs rounded-sm gap-1.5"><Bell className="w-3 h-3" /> Alerts</TabsTrigger>
        </TabsList>

        <TabsContent value="credentials">
          <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
            <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
              <CardTitle className="text-sm font-medium text-zinc-300">Zerodha Kite Connect Credentials</CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-4">
              <div className="bg-amber-950/30 border border-amber-800/50 rounded-sm p-3">
                <p className="text-xs text-amber-400 flex items-center gap-2">
                  <Key className="w-3.5 h-3.5" />
                  Get credentials from <a href="https://kite.trade" target="_blank" rel="noopener noreferrer" className="underline">kite.trade</a> (Kite Connect Developer Portal)
                </p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">API Key</label>
                  <Input data-testid="setting-api-key" type="password" value={settings.kite_api_key} onChange={(e) => updateField("kite_api_key", e.target.value)} placeholder="Your Kite API Key" className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">API Secret</label>
                  <Input data-testid="setting-api-secret" type="password" value={settings.kite_api_secret} onChange={(e) => updateField("kite_api_secret", e.target.value)} placeholder="Your Kite API Secret" className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Access Token</label>
                  <Input data-testid="setting-access-token" type="password" value={settings.kite_access_token} onChange={(e) => updateField("kite_access_token", e.target.value)} placeholder="Generated after login" className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Redirect URL</label>
                  <Input data-testid="setting-redirect-url" value={settings.kite_redirect_url} onChange={(e) => updateField("kite_redirect_url", e.target.value)} className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
                </div>
              </div>
              <div className="grid gap-3 lg:grid-cols-[1fr_auto] lg:items-center">
                <div className="rounded-sm border border-zinc-800 bg-zinc-950/60 p-3 text-xs font-mono text-zinc-400" data-testid="setting-zerodha-auth-status">
                  <div>API Key: {authStatus?.api_key_configured ? "configured" : "missing"}</div>
                  <div>API Secret: {authStatus?.api_secret_configured ? "configured" : "missing"}</div>
                  <div>Access Token: {authStatus?.access_token_configured ? "present" : "not generated"}</div>
                  <div>User: {authStatus?.profile?.user_id || "Not connected"}</div>
                </div>
                <Button data-testid="setting-connect-zerodha-button" onClick={handleZerodhaConnect} className="rounded-sm bg-blue-600 hover:bg-blue-500">
                  Connect Zerodha
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="trading">
          <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
            <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
              <CardTitle className="text-sm font-medium text-zinc-300">Trading Configuration</CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Trading Mode</label>
                  <Select value={settings.trading_mode} onValueChange={(v) => updateField("trading_mode", v)}>
                    <SelectTrigger data-testid="setting-trading-mode" className="h-8 text-xs bg-zinc-800 border-zinc-700">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="paper">Paper Trading</SelectItem>
                      <SelectItem value="live">Live Trading</SelectItem>
                    </SelectContent>
                  </Select>
                  {settings.trading_mode === "live" && (
                    <p className="text-[10px] text-red-400 mt-1 font-mono">WARNING: Live mode uses real money!</p>
                  )}
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Capital (INR)</label>
                  <Input data-testid="setting-capital" type="number" value={settings.capital} onChange={(e) => updateField("capital", Number(e.target.value))} className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Default Exchange</label>
                  <Select value={settings.default_exchange} onValueChange={(v) => updateField("default_exchange", v)}>
                    <SelectTrigger data-testid="setting-exchange" className="h-8 text-xs bg-zinc-800 border-zinc-700">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="NSE">NSE</SelectItem>
                      <SelectItem value="BSE">BSE</SelectItem>
                      <SelectItem value="NFO">NFO</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Auto Square Off</label>
                  <Input data-testid="setting-auto-sqoff" type="time" value={settings.auto_square_off_time} onChange={(e) => updateField("auto_square_off_time", e.target.value)} className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
                </div>
                <div className="flex items-center justify-between col-span-1">
                  <label className="text-[10px] uppercase tracking-wider text-zinc-500">Enable Live Ticks</label>
                  <Switch data-testid="setting-enable-ticks" checked={settings.enable_ticks} onCheckedChange={(v) => updateField("enable_ticks", v)} />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="system">
          <div className="space-y-4">
            {/* Health Status */}
            <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
              <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
                <CardTitle className="text-sm font-medium text-zinc-300">System Health</CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                {health && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <HealthItem label="API" status={health.status === "healthy"} />
                    <HealthItem label="Database" status={health.database === "connected"} />
                    <HealthItem label="Market" status={health.market_open} statusText={health.market_open ? "OPEN" : "CLOSED"} />
                    <HealthItem label="Bot" status={health.bot_status === "RUNNING"} statusText={health.bot_status} />
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Actions */}
            <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
              <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
                <CardTitle className="text-sm font-medium text-zinc-300">System Actions</CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <div className="flex flex-wrap gap-2">
                  <Button data-testid="btn-init-db" onClick={handleInit} variant="outline" size="sm" className="rounded-sm border-zinc-700 text-xs gap-1.5">
                    <Database className="w-3 h-3" /> Initialize DB
                  </Button>
                  <Button data-testid="btn-sync-instruments" onClick={handleSync} disabled={syncing} variant="outline" size="sm" className="rounded-sm border-zinc-700 text-xs gap-1.5">
                    <RefreshCw className={`w-3 h-3 ${syncing ? "animate-spin" : ""}`} /> Sync Instruments
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Instruments */}
            <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
              <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
                <CardTitle className="text-sm font-medium text-zinc-300">Instruments ({instruments.length})</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-auto max-h-[300px]">
                  <table className="w-full data-table">
                    <thead className="sticky top-0 bg-zinc-900 z-10">
                      <tr>
                        <th>Symbol</th><th>Name</th><th>Exchange</th><th>Type</th><th>Lot Size</th><th>Tick Size</th>
                      </tr>
                    </thead>
                    <tbody>
                      {instruments.map((inst, i) => (
                        <tr key={i}>
                          <td className="text-white font-medium font-mono">{inst.tradingsymbol}</td>
                          <td className="text-zinc-400">{inst.name}</td>
                          <td><Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">{inst.exchange}</Badge></td>
                          <td className="text-zinc-400">{inst.instrument_type || "EQ"}</td>
                          <td className="text-zinc-300 font-mono">{inst.lot_size}</td>
                          <td className="text-zinc-300 font-mono">{inst.tick_size}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="alerts">
          <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
            <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
              <CardTitle className="text-sm font-medium text-zinc-300">Alert Configuration</CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-4">
              <div className="bg-blue-950/30 border border-blue-800/50 rounded-sm p-3">
                <p className="text-xs text-blue-400">
                  Configure Telegram bot for trade alerts. Create a bot via @BotFather on Telegram and get the token.
                </p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Telegram Bot Token</label>
                  <Input data-testid="setting-telegram-token" type="password" value={settings.telegram_bot_token} onChange={(e) => updateField("telegram_bot_token", e.target.value)} placeholder="123456:ABC-DEF..." className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Telegram Chat ID</label>
                  <Input data-testid="setting-telegram-chat" value={settings.telegram_chat_id} onChange={(e) => updateField("telegram_chat_id", e.target.value)} placeholder="Your chat ID" className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
                </div>
                <div className="md:col-span-2">
                  <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Webhook URL (optional)</label>
                  <Input data-testid="setting-webhook-url" value={settings.webhook_url} onChange={(e) => updateField("webhook_url", e.target.value)} placeholder="https://your-webhook-endpoint.com/alerts" className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
                </div>
              </div>
              <div className="flex flex-col gap-3 rounded-sm border border-zinc-800 bg-zinc-950/60 p-3 text-xs font-mono text-zinc-400 lg:flex-row lg:items-center lg:justify-between">
                <div data-testid="settings-alert-channel-status">
                  Telegram: {alertStatus?.telegram_configured ? "configured" : "missing"} · Webhook: {alertStatus?.webhook_configured ? "configured" : "missing"}
                </div>
                <Button data-testid="settings-test-alert-button" variant="outline" size="sm" onClick={handleTestAlert} className="rounded-sm border-zinc-700">
                  Test Alert
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function HealthItem({ label, status, statusText }) {
  return (
    <div className="flex items-center gap-2 p-2 bg-zinc-800/50 rounded-sm">
      <div className={`w-2 h-2 rounded-full ${status ? "bg-emerald-500 pulse-live" : "bg-zinc-500"}`} />
      <span className="text-xs text-zinc-400">{label}</span>
      <span className={`text-[10px] font-mono ml-auto ${status ? "text-emerald-400" : "text-zinc-500"}`}>
        {statusText || (status ? "OK" : "DOWN")}
      </span>
    </div>
  );
}

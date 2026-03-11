import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Terminal, Save, RotateCcw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function StrategyEditor() {
  const [strategies, setStrategies] = useState([]);
  const [activeTab, setActiveTab] = useState("");
  const [editParams, setEditParams] = useState({});
  const [editSymbols, setEditSymbols] = useState("");
  const [editQuantity, setEditQuantity] = useState(1);
  const [editEnabled, setEditEnabled] = useState(false);
  const [saving, setSaving] = useState(false);

  const fetchStrategies = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/strategies`);
      setStrategies(res.data);
      if (res.data.length > 0 && !activeTab) {
        selectStrategy(res.data[0]);
      }
    } catch (e) {
      console.error(e);
    }
  }, [activeTab]);

  useEffect(() => { fetchStrategies(); }, [fetchStrategies]);

  const selectStrategy = (strat) => {
    setActiveTab(strat.name);
    setEditParams(strat.saved_params || strat.default_params || {});
    setEditSymbols((strat.symbols || []).join(", "));
    setEditQuantity(strat.quantity || 1);
    setEditEnabled(strat.enabled || false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const symbols = editSymbols.split(",").map(s => s.trim()).filter(Boolean);
      await axios.put(`${API}/strategies/${activeTab}`, {
        parameters: editParams,
        symbols,
        quantity: editQuantity,
        enabled: editEnabled,
      });
      toast.success(`Strategy '${activeTab}' saved`);
      fetchStrategies();
    } catch (e) {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    const strat = strategies.find(s => s.name === activeTab);
    if (strat) {
      setEditParams(strat.default_params);
      toast.info("Reset to defaults");
    }
  };

  const currentStrat = strategies.find(s => s.name === activeTab);

  return (
    <div data-testid="strategy-editor-page" className="p-4 md:p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight flex items-center gap-2">
            <Terminal className="w-5 h-5 text-blue-500" /> Strategy Editor
          </h1>
          <p className="text-xs text-zinc-500 font-mono mt-0.5">
            Configure strategy parameters and instruments
          </p>
        </div>
      </div>

      {strategies.length > 0 && (
        <Tabs value={activeTab} onValueChange={(v) => {
          const strat = strategies.find(s => s.name === v);
          if (strat) selectStrategy(strat);
        }}>
          <TabsList className="bg-zinc-900 border border-zinc-800 rounded-sm">
            {strategies.map(s => (
              <TabsTrigger key={s.name} data-testid={`strat-tab-${s.name}`} value={s.name} className="text-xs rounded-sm gap-1.5">
                {s.display_name}
                {s.enabled && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />}
              </TabsTrigger>
            ))}
          </TabsList>

          {strategies.map(strat => (
            <TabsContent key={strat.name} value={strat.name}>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* Strategy Info */}
                <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
                  <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
                    <CardTitle className="text-sm font-medium text-zinc-300">Strategy Info</CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 space-y-3">
                    <div>
                      <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Name</label>
                      <div className="text-sm text-white font-mono">{strat.display_name}</div>
                    </div>
                    <div>
                      <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Description</label>
                      <div className="text-xs text-zinc-400">{strat.description}</div>
                    </div>
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] uppercase tracking-wider text-zinc-500">Enabled</label>
                      <Switch data-testid="strat-enabled-switch" checked={editEnabled} onCheckedChange={setEditEnabled} />
                    </div>
                    <div>
                      <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">Quantity per Trade</label>
                      <Input data-testid="strat-quantity" type="number" value={editQuantity} onChange={(e) => setEditQuantity(Number(e.target.value))} className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono" />
                    </div>
                  </CardContent>
                </Card>

                {/* Parameters */}
                <Card className="bg-[#050505] border-zinc-800 rounded-sm">
                  <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
                    <CardTitle className="text-sm font-medium text-zinc-300">Parameters</CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 space-y-3">
                    {Object.entries(editParams).map(([key, val]) => (
                      <div key={key}>
                        <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">
                          {key.replace(/_/g, " ")}
                        </label>
                        {typeof val === "boolean" ? (
                          <Switch
                            data-testid={`param-${key}`}
                            checked={val}
                            onCheckedChange={(v) => setEditParams(p => ({...p, [key]: v}))}
                          />
                        ) : (
                          <Input
                            data-testid={`param-${key}`}
                            type="number"
                            step={typeof val === "number" && val % 1 !== 0 ? "0.1" : "1"}
                            value={val}
                            onChange={(e) => setEditParams(p => ({...p, [key]: Number(e.target.value)}))}
                            className="h-8 text-xs bg-transparent border-0 border-b border-zinc-700 rounded-none font-mono text-emerald-400 focus:border-blue-500 px-0"
                          />
                        )}
                      </div>
                    ))}
                  </CardContent>
                </Card>

                {/* Instruments */}
                <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
                  <CardHeader className="border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
                    <CardTitle className="text-sm font-medium text-zinc-300">Instruments</CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 space-y-3">
                    <div>
                      <label className="text-[10px] uppercase tracking-wider text-zinc-500 block mb-1">
                        Symbols (comma-separated)
                      </label>
                      <Input
                        data-testid="strat-symbols"
                        value={editSymbols}
                        onChange={(e) => setEditSymbols(e.target.value)}
                        placeholder="RELIANCE, INFY, TCS"
                        className="h-8 text-xs bg-zinc-800 border-zinc-700 font-mono"
                      />
                    </div>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {editSymbols.split(",").map(s => s.trim()).filter(Boolean).map(sym => (
                        <Badge key={sym} variant="outline" className="text-[10px] font-mono border-zinc-700 text-zinc-300">{sym}</Badge>
                      ))}
                    </div>
                    <div className="pt-4 space-y-2">
                      <Button data-testid="save-strategy-btn" onClick={handleSave} disabled={saving} className="w-full h-8 rounded-sm bg-blue-600 hover:bg-blue-500 text-xs gap-1.5">
                        <Save className="w-3 h-3" /> {saving ? "Saving..." : "Save Configuration"}
                      </Button>
                      <Button data-testid="reset-strategy-btn" onClick={handleReset} variant="outline" className="w-full h-8 rounded-sm border-zinc-700 text-xs gap-1.5">
                        <RotateCcw className="w-3 h-3" /> Reset to Defaults
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          ))}
        </Tabs>
      )}
    </div>
  );
}

import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ArrowRightLeft, RefreshCw, Filter } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function TradeMonitor() {
  const [orders, setOrders] = useState([]);
  const [trades, setTrades] = useState([]);
  const [positions, setPositions] = useState([]);
  const [signals, setSignals] = useState([]);
  const [activeTab, setActiveTab] = useState("orders");
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [ordRes, trRes, posRes, sigRes] = await Promise.all([
        axios.get(`${API}/orders?limit=100`),
        axios.get(`${API}/trades?limit=100`),
        axios.get(`${API}/positions`),
        axios.get(`${API}/signals?limit=100`),
      ]);
      setOrders(ordRes.data);
      setTrades(trRes.data);
      setPositions(posRes.data);
      setSignals(sigRes.data);
    } catch (e) {
      console.error("Trade monitor fetch error:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 8000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const statusBadge = (status) => {
    const map = {
      COMPLETE: "bg-emerald-900/50 text-emerald-400 border-emerald-800",
      OPEN: "bg-blue-900/50 text-blue-400 border-blue-800",
      PENDING: "bg-amber-900/50 text-amber-400 border-amber-800",
      CANCELLED: "bg-zinc-800 text-zinc-400 border-zinc-700",
      REJECTED: "bg-red-900/50 text-red-400 border-red-800",
      CLOSED: "bg-zinc-800 text-zinc-300 border-zinc-700",
      GENERATED: "bg-blue-900/50 text-blue-400 border-blue-800",
      EXECUTED: "bg-emerald-900/50 text-emerald-400 border-emerald-800",
    };
    const cls = map[status] || "bg-zinc-800 text-zinc-400 border-zinc-700";
    return <Badge variant="outline" className={`text-[10px] font-mono ${cls}`}>{status}</Badge>;
  };

  const filteredItems = (items) => {
    if (statusFilter === "all") return items;
    return items.filter(i => i.status === statusFilter);
  };

  return (
    <div data-testid="trade-monitor-page" className="p-4 md:p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight flex items-center gap-2">
            <ArrowRightLeft className="w-5 h-5 text-blue-500" /> Trade Monitor
          </h1>
          <p className="text-xs text-zinc-500 font-mono mt-0.5">
            Orders: {orders.length} | Trades: {trades.length} | Positions: {positions.length}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger data-testid="status-filter" className="w-32 h-8 text-xs bg-zinc-900 border-zinc-800">
              <Filter className="w-3 h-3 mr-1" /> <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="COMPLETE">Complete</SelectItem>
              <SelectItem value="OPEN">Open</SelectItem>
              <SelectItem value="PENDING">Pending</SelectItem>
              <SelectItem value="CANCELLED">Cancelled</SelectItem>
              <SelectItem value="CLOSED">Closed</SelectItem>
            </SelectContent>
          </Select>
          <Button data-testid="refresh-trades-btn" size="sm" variant="outline" onClick={fetchData} className="h-8 rounded-sm border-zinc-800">
            <RefreshCw className="w-3 h-3" />
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-zinc-900 border border-zinc-800 rounded-sm">
          <TabsTrigger data-testid="tab-orders" value="orders" className="text-xs rounded-sm">Orders ({orders.length})</TabsTrigger>
          <TabsTrigger data-testid="tab-trades" value="trades" className="text-xs rounded-sm">Trades ({trades.length})</TabsTrigger>
          <TabsTrigger data-testid="tab-positions" value="positions" className="text-xs rounded-sm">Positions ({positions.length})</TabsTrigger>
          <TabsTrigger data-testid="tab-signals" value="signals" className="text-xs rounded-sm">Signals ({signals.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="orders">
          <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
            <CardContent className="p-0">
              <div className="overflow-auto max-h-[calc(100vh-220px)]">
                <table className="w-full data-table">
                  <thead className="sticky top-0 bg-zinc-900 z-10">
                    <tr>
                      <th>ID</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Type</th><th>Price</th><th>Filled</th><th>Status</th><th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems(orders).length === 0 ? (
                      <tr><td colSpan={9} className="text-center text-zinc-600 py-12 font-mono">No orders found</td></tr>
                    ) : filteredItems(orders).map((o, i) => (
                      <tr key={i}>
                        <td className="text-zinc-500 text-xs">{o.id?.substring(0, 8)}</td>
                        <td className="text-white font-medium">{o.symbol}</td>
                        <td><span className={o.side === "BUY" ? "text-profit" : "text-loss"}>{o.side}</span></td>
                        <td className="text-zinc-300">{o.quantity}</td>
                        <td className="text-zinc-400">{o.order_type}</td>
                        <td className="text-zinc-300">{o.price?.toFixed(2) || "MKT"}</td>
                        <td className="text-zinc-300">{o.filled_price?.toFixed(2) || "-"}</td>
                        <td>{statusBadge(o.status)}</td>
                        <td className="text-zinc-500 text-xs">{o.created_at?.substring(0, 16)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="trades">
          <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
            <CardContent className="p-0">
              <div className="overflow-auto max-h-[calc(100vh-220px)]">
                <table className="w-full data-table">
                  <thead className="sticky top-0 bg-zinc-900 z-10">
                    <tr>
                      <th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Net P&L</th><th>Fees</th><th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems(trades).length === 0 ? (
                      <tr><td colSpan={9} className="text-center text-zinc-600 py-12 font-mono">No trades found</td></tr>
                    ) : filteredItems(trades).map((t, i) => (
                      <tr key={i}>
                        <td className="text-white font-medium">{t.symbol}</td>
                        <td><span className={t.side === "BUY" ? "text-profit" : "text-loss"}>{t.side}</span></td>
                        <td className="text-zinc-300">{t.quantity}</td>
                        <td className="text-zinc-300">{t.entry_price?.toFixed(2)}</td>
                        <td className="text-zinc-300">{t.exit_price?.toFixed(2) || "-"}</td>
                        <td className={t.pnl >= 0 ? "text-profit" : "text-loss"}>{t.pnl >= 0 ? "+" : ""}{t.pnl?.toFixed(2)}</td>
                        <td className={t.net_pnl >= 0 ? "text-profit" : "text-loss"}>{t.net_pnl >= 0 ? "+" : ""}{t.net_pnl?.toFixed(2)}</td>
                        <td className="text-zinc-500">{t.fees?.toFixed(2)}</td>
                        <td>{statusBadge(t.status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="positions">
          <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
            <CardContent className="p-0">
              <div className="overflow-auto max-h-[calc(100vh-220px)]">
                <table className="w-full data-table">
                  <thead className="sticky top-0 bg-zinc-900 z-10">
                    <tr>
                      <th>Symbol</th><th>Side</th><th>Qty</th><th>Avg Price</th><th>Current</th><th>Unrealized</th><th>Realized</th><th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.length === 0 ? (
                      <tr><td colSpan={8} className="text-center text-zinc-600 py-12 font-mono">No positions</td></tr>
                    ) : positions.map((p, i) => (
                      <tr key={i}>
                        <td className="text-white font-medium">{p.symbol}</td>
                        <td><span className={p.side === "BUY" ? "text-profit" : "text-loss"}>{p.side}</span></td>
                        <td className="text-zinc-300">{p.quantity}</td>
                        <td className="text-zinc-300">{p.avg_price?.toFixed(2)}</td>
                        <td className="text-zinc-300">{p.current_price?.toFixed(2)}</td>
                        <td className={p.unrealized_pnl >= 0 ? "text-profit" : "text-loss"}>{p.unrealized_pnl?.toFixed(2)}</td>
                        <td className={p.realized_pnl >= 0 ? "text-profit" : "text-loss"}>{p.realized_pnl?.toFixed(2)}</td>
                        <td>{statusBadge(p.status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="signals">
          <Card className="bg-zinc-900 border-zinc-800 rounded-sm">
            <CardContent className="p-0">
              <div className="overflow-auto max-h-[calc(100vh-220px)]">
                <table className="w-full data-table">
                  <thead className="sticky top-0 bg-zinc-900 z-10">
                    <tr>
                      <th>Symbol</th><th>Side</th><th>Strategy</th><th>Confidence</th><th>Reason</th><th>SL</th><th>TP</th><th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {signals.length === 0 ? (
                      <tr><td colSpan={8} className="text-center text-zinc-600 py-12 font-mono">No signals generated</td></tr>
                    ) : signals.map((sig, i) => (
                      <tr key={i}>
                        <td className="text-white font-medium">{sig.symbol}</td>
                        <td><span className={sig.side === "BUY" ? "text-profit" : "text-loss"}>{sig.side}</span></td>
                        <td className="text-zinc-400">{sig.strategy_name}</td>
                        <td className="text-zinc-300">{(sig.confidence * 100).toFixed(0)}%</td>
                        <td className="text-zinc-500 text-xs max-w-[200px] truncate">{sig.reason}</td>
                        <td className="text-zinc-400">{sig.stop_loss?.toFixed(2) || "-"}</td>
                        <td className="text-zinc-400">{sig.take_profit?.toFixed(2) || "-"}</td>
                        <td className="text-zinc-500 text-xs">{sig.timestamp?.substring(0, 16)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

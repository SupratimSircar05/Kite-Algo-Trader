import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Sidebar from "@/components/Sidebar";
import Dashboard from "@/pages/Dashboard";
import TradeMonitor from "@/pages/TradeMonitor";
import BacktestLab from "@/pages/BacktestLab";
import StrategyEditor from "@/pages/StrategyEditor";
import RiskControls from "@/pages/RiskControls";
import Settings from "@/pages/Settings";
import Optimizer from "@/pages/Optimizer";
import TradeJournal from "@/pages/TradeJournal";
import MarketCharts from "@/pages/MarketCharts";
import { Toaster } from "@/components/ui/sonner";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <div className="flex h-screen overflow-hidden bg-[#0A0A0A]">
          <Sidebar />
          <main className="flex-1 overflow-y-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/trades" element={<TradeMonitor />} />
              <Route path="/backtest" element={<BacktestLab />} />
              <Route path="/strategies" element={<StrategyEditor />} />
              <Route path="/risk" element={<RiskControls />} />
              <Route path="/optimizer" element={<Optimizer />} />
              <Route path="/journal" element={<TradeJournal />} />
              <Route path="/charts" element={<MarketCharts />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
      <Toaster position="bottom-right" theme="dark" richColors />
    </div>
  );
}

export default App;

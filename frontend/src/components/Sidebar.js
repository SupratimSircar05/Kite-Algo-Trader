import React from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard, ArrowRightLeft, LineChart, Settings,
  ShieldAlert, Terminal, Zap, Grid3x3
} from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

const navItems = [
  { path: "/", icon: LayoutDashboard, label: "Dashboard", shortcut: "D" },
  { path: "/trades", icon: ArrowRightLeft, label: "Trade Monitor", shortcut: "T" },
  { path: "/backtest", icon: LineChart, label: "Backtest Lab", shortcut: "B" },
  { path: "/strategies", icon: Terminal, label: "Strategies", shortcut: "S" },
  { path: "/risk", icon: ShieldAlert, label: "Risk Controls", shortcut: "R" },
  { path: "/optimizer", icon: Grid3x3, label: "Optimizer", shortcut: "O" },
  { path: "/settings", icon: Settings, label: "Settings", shortcut: "G" },
];

export default function Sidebar() {
  const location = useLocation();

  return (
    <TooltipProvider delayDuration={200}>
      <aside
        data-testid="sidebar-nav"
        className="w-16 lg:w-56 flex-shrink-0 bg-[#0A0A0A] border-r border-zinc-800 flex flex-col h-screen"
      >
        {/* Logo */}
        <div className="h-14 flex items-center gap-2 px-4 border-b border-zinc-800">
          <div className="w-7 h-7 bg-blue-600 flex items-center justify-center rounded-sm flex-shrink-0">
            <Zap className="w-4 h-4 text-white" strokeWidth={2.5} />
          </div>
          <span className="text-sm font-semibold text-white tracking-wide hidden lg:block">
            KITE<span className="text-blue-500">ALGO</span>
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 px-2 space-y-0.5">
          {navItems.map(({ path, icon: Icon, label, shortcut }) => {
            const isActive = location.pathname === path;
            return (
              <Tooltip key={path}>
                <TooltipTrigger asChild>
                  <NavLink
                    to={path}
                    data-testid={`nav-${label.toLowerCase().replace(/\s/g, "-")}`}
                    className={`sidebar-link ${isActive ? "active" : "text-zinc-400"}`}
                  >
                    <Icon className="w-4 h-4 flex-shrink-0" strokeWidth={isActive ? 2 : 1.5} />
                    <span className="hidden lg:block truncate">{label}</span>
                    <span className="hidden lg:block ml-auto text-[10px] text-zinc-600 font-mono">{shortcut}</span>
                  </NavLink>
                </TooltipTrigger>
                <TooltipContent side="right" className="lg:hidden">
                  {label}
                </TooltipContent>
              </Tooltip>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="px-3 py-3 border-t border-zinc-800">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500 pulse-live" />
            <span className="text-[10px] text-zinc-500 font-mono hidden lg:block">PAPER MODE</span>
          </div>
        </div>
      </aside>
    </TooltipProvider>
  );
}

import { Link, useLocation } from 'react-router-dom';
import { MessageSquare, Phone, FileCheck2, Activity, Globe } from 'lucide-react';

export default function Navbar() {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'OmniChat', icon: MessageSquare, badge: '50+ Lang' },
    { path: '/voice', label: 'OmniVoice', icon: Phone, badge: 'Duplex Live' },
    { path: '/autoform', label: 'AutoForm & Vault', icon: FileCheck2, badge: 'RAG Agent' },
    { path: '/admin', label: 'Telemetry & Admin', icon: Activity, badge: 'Breakers' },
  ];

  return (
    <header className="sticky top-0 z-50 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200/80 dark:border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand Logo */}
        <Link to="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center text-white shadow-md shadow-indigo-500/20 group-hover:scale-105 transition-transform">
            <Globe className="w-5 h-5 animate-spin-slow" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold font-headline text-lg text-slate-900 dark:text-white">
                OmniAgent X
              </span>
              <span className="text-[10px] font-semibold bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300 px-1.5 py-0.5 rounded-md">
                v2.0
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium">Multimodal Multilingual Agent</p>
          </div>
        </Link>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1 sm:gap-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/20'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span className="hidden sm:inline">{item.label}</span>
                <span className={`text-[9px] px-1.5 py-0.2 rounded font-mono hidden md:inline ${
                  isActive ? 'bg-indigo-700 text-indigo-100' : 'bg-slate-200/70 dark:bg-slate-800 text-slate-500'
                }`}>
                  {item.badge}
                </span>
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}

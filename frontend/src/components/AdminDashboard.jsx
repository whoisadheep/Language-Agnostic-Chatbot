import { useState, useEffect } from 'react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';
import { ShieldCheck, Activity, PhoneCall, Users, MessageSquare, Database, RefreshCw, AlertCircle } from 'lucide-react';
import '../index.css';

const COLORS = ['#5755a9', '#a19ff9', '#fdd2fd', '#e3e0f9', '#9492eb', '#eec4ef', '#dce4e8', '#eaeff2'];

export default function AdminDashboard() {
  const [data, setData] = useState(null);
  const [telemetry, setTelemetry] = useState([]);
  const [gridCrmTickets, setGridCrmTickets] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchDashboardData = () => {
    setIsLoading(true);
    const host = window.location.hostname || 'localhost';

    fetch(`http://${host}:8000/analytics`)
      .then(res => res.json())
      .then(json => {
        setData(json);
        if (json.telemetry) {
          setTelemetry(json.telemetry);
        }
        setIsLoading(false);
      })
      .catch(err => {
        console.error('Failed to load analytics', err);
        setIsLoading(false);
      });

    fetch(`http://${host}:8000/api/gridcrm/tickets`)
      .then(res => res.json())
      .then(json => {
        if (json.tickets) {
          setGridCrmTickets(json.tickets);
        }
      })
      .catch(err => console.error('Failed to fetch GridCRM tickets', err));
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 15000); // Polling every 15s
    return () => clearInterval(interval);
  }, []);

  if (isLoading && !data) {
    return (
      <div className="flex items-center justify-center h-screen bg-slate-50 dark:bg-slate-950">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-slate-600 dark:text-slate-400 font-semibold text-sm">Loading Telemetry & System Analytics...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-screen bg-slate-50 dark:bg-slate-950 p-4">
        <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 p-6 rounded-2xl max-w-md text-center">
          <AlertCircle className="w-10 h-10 mx-auto mb-3 text-red-500" />
          <h2 className="font-bold text-lg mb-1">Backend Analytics Offline</h2>
          <p className="text-xs text-red-600 dark:text-red-400 mb-4">Ensure FastAPI server is running on http://localhost:8000</p>
          <button
            onClick={fetchDashboardData}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-semibold"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  const pieData = (data.languages_detected || []).map(l => ({ name: (l.name || 'UNKNOWN').toUpperCase(), value: l.value }));
  const barData = (data.messages_per_hour || []).map(m => {
    const d = new Date(m.hour);
    return {
      name: d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      Messages: m.count
    };
  });

  return (
    <div className="max-w-7xl mx-auto w-full p-4 md:p-8 space-y-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-5 h-5 text-indigo-500" />
            <span className="text-xs font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
              System Telemetry & Health
            </span>
          </div>
          <h1 className="text-3xl font-bold font-headline text-slate-900 dark:text-white">
            Architecture Command Center
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time monitoring of AI Circuit Breakers, Full-Duplex Voice Logs, CRM Leads, and Multilingual Traffic.
          </p>
        </div>
        <button
          onClick={fetchDashboardData}
          className="px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-medium text-slate-700 dark:text-slate-300 flex items-center gap-2 transition-all self-start"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh Metrics
        </button>
      </div>

      {/* 4 KPI Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium">Total Messages</span>
            <MessageSquare className="w-4 h-4 text-indigo-500" />
          </div>
          <p className="text-2xl font-bold text-slate-900 dark:text-white">{data.total_messages || 0}</p>
          <p className="text-[11px] text-slate-400 mt-1">Multilingual conversations</p>
        </div>

        <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium">Voice Calls Handled</span>
            <PhoneCall className="w-4 h-4 text-emerald-500" />
          </div>
          <p className="text-2xl font-bold text-slate-900 dark:text-white">{data.total_calls || 0}</p>
          <p className="text-[11px] text-slate-400 mt-1">Full-duplex WebSockets</p>
        </div>

        <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium">Captured CRM Leads</span>
            <Users className="w-4 h-4 text-purple-500" />
          </div>
          <p className="text-2xl font-bold text-slate-900 dark:text-white">{data.total_leads || 0}</p>
          <p className="text-[11px] text-slate-400 mt-1">Dispatched to GridCRM</p>
        </div>

        <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium">RAG Memory Vault</span>
            <Database className="w-4 h-4 text-amber-500" />
          </div>
          <p className="text-2xl font-bold text-slate-900 dark:text-white">{data.total_memories || 0}</p>
          <p className="text-[11px] text-slate-400 mt-1">Grounded profile snippets</p>
        </div>
      </div>

      {/* Multi-Provider AI Circuit Breaker Telemetry Section */}
      <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800 mb-4">
          <div>
            <h3 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-indigo-500" />
              Distributed Multi-LLM Circuit Breaker Telemetry
            </h3>
            <p className="text-xs text-slate-500">
              Autonomous failover state machine across Groq, Google Gemini, and OpenRouter backup.
            </p>
          </div>
          <span className="text-xs bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 px-2.5 py-1 rounded-full font-medium">
            Failover Active
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {telemetry.map((prov, i) => (
            <div
              key={i}
              className="p-4 rounded-2xl border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-800 dark:text-slate-200">{prov.name}</span>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                  prov.state === 'CLOSED'
                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                    : prov.state === 'HALF_OPEN'
                    ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                    : 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300'
                }`}>
                  {prov.state === 'CLOSED' ? '● CLOSED (Healthy)' : prov.state === 'HALF_OPEN' ? '▲ HALF-OPEN' : '✕ OPEN (Trip)'}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-slate-400 block text-[10px]">Avg Latency</span>
                  <span className="font-bold text-slate-700 dark:text-slate-300">{prov.avg_latency_ms} ms</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px]">Total Calls</span>
                  <span className="font-bold text-slate-700 dark:text-slate-300">{prov.total_requests} reqs</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recharts Analytics Charts: Languages & Traffic */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Languages Pie */}
        <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col items-center">
          <h3 className="font-semibold text-slate-900 dark:text-white mb-2 self-start text-sm">
            🌐 Detected Language Breakdown
          </h3>
          <div className="w-full h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <RechartsTooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Hourly Traffic Bar */}
        <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <h3 className="font-semibold text-slate-900 dark:text-white mb-2 text-sm">
            📈 Message Traffic per Hour
          </h3>
          <div className="w-full h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="name" fontSize={11} />
                <YAxis fontSize={11} />
                <RechartsTooltip />
                <Bar dataKey="Messages" fill="#5755a9" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Voice Call Logs & CRM Leads Table */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Voice Call Logs */}
        <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
          <h3 className="font-semibold text-slate-900 dark:text-white text-sm flex items-center gap-2">
            <PhoneCall className="w-4 h-4 text-emerald-500" />
            Recent Voice Calls (Voicera)
          </h3>
          {data.recent_calls?.length > 0 ? (
            <div className="space-y-2">
              {data.recent_calls.map((call, idx) => (
                <div key={idx} className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 text-xs">
                  <div className="flex justify-between font-semibold text-slate-700 dark:text-slate-300">
                    <span>Call #{call.id} ({call.duration}s duration)</span>
                    <span className="text-[10px] text-slate-400 font-mono">{call.turns} turns</span>
                  </div>
                  <p className="text-slate-500 text-[11px] mt-1 line-clamp-2 italic">"{call.transcript}"</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400 py-4 text-center">No voice calls recorded yet. Test OmniVoice!</p>
          )}
        </div>

        {/* CRM Leads Table */}
        <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
          <h3 className="font-semibold text-slate-900 dark:text-white text-sm flex items-center gap-2">
            <Users className="w-4 h-4 text-purple-500" />
            Captured CRM Inquiries & Leads
          </h3>
          {data.recent_leads?.length > 0 ? (
            <div className="space-y-2">
              {data.recent_leads.map((lead, idx) => (
                <div key={idx} className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 text-xs">
                  <div className="flex justify-between font-semibold text-slate-700 dark:text-slate-300">
                    <span>{lead.name} ({lead.category})</span>
                    <span className="text-[10px] text-indigo-500 font-medium">{lead.source}</span>
                  </div>
                  <p className="text-slate-500 text-[11px] mt-1 line-clamp-2">{lead.summary}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400 py-4 text-center">No CRM leads recorded yet.</p>
          )}
        </div>
      </div>

      {/* GridCRM Cloud Real-Time Firestore Synchronization */}
      <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-indigo-600" />
            <h3 className="font-bold text-slate-900 dark:text-white text-sm">
              Live GridCRM Cloud Synchronization (Firebase Firestore)
            </h3>
          </div>
          <div className="flex items-center gap-2 text-[11px]">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 font-medium border border-emerald-200/50">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              Connected (Owner: Rudra)
            </span>
            <span className="text-slate-400 font-mono text-[10px]">grid-a4798.firebaseio.com</span>
          </div>
        </div>

        {gridCrmTickets.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-800 text-slate-400 font-semibold text-[11px]">
                  <th className="pb-2">Customer</th>
                  <th className="pb-2">Phone</th>
                  <th className="pb-2">Type</th>
                  <th className="pb-2">Priority</th>
                  <th className="pb-2">Problem Summary</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2 text-right">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 text-slate-600 dark:text-slate-300">
                {gridCrmTickets.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors">
                    <td className="py-2.5 font-semibold text-slate-900 dark:text-white">
                      {t.customer_name}
                    </td>
                    <td className="py-2.5 font-mono text-[11px] text-slate-500">
                      {t.phone || 'N/A'}
                    </td>
                    <td className="py-2.5">
                      <span className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-[10px] font-medium">
                        {t.call_type}
                      </span>
                    </td>
                    <td className="py-2.5">
                      <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold ${
                        t.priority === 'High' ? 'bg-red-50 dark:bg-red-950 text-red-600 border border-red-200/60' :
                        t.priority === 'Medium' ? 'bg-amber-50 dark:bg-amber-950 text-amber-600 border border-amber-200/60' :
                        'bg-blue-50 dark:bg-blue-950 text-blue-600'
                      }`}>
                        {t.priority}
                      </span>
                    </td>
                    <td className="py-2.5 max-w-xs truncate text-slate-500 text-[11px]">
                      {t.problem_description}
                    </td>
                    <td className="py-2.5">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        t.status === 'Resolved' ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-600' :
                        'bg-slate-100 dark:bg-slate-800 text-slate-600'
                      }`}>
                        {t.status}
                      </span>
                    </td>
                    <td className="py-2.5 text-right font-mono text-[10px] text-indigo-500">
                      {t.source}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-slate-400 py-4 text-center">
            Loading real-time Firestore tickets from GridCRM...
          </p>
        )}
      </div>
    </div>
  );
}

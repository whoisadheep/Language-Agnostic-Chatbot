import { useState, useEffect } from 'react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';
import '../index.css';

const COLORS = ['#5755a9', '#a19ff9', '#fdd2fd', '#e3e0f9', '#9492eb', '#eec4ef', '#dce4e8', '#eaeff2'];

export default function AdminDashboard() {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:8000/analytics')
      .then(res => res.json())
      .then(json => {
        setData(json);
        setIsLoading(false);
      })
      .catch(err => {
        console.error("Failed to load analytics", err);
        setIsLoading(false);
      });
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
          <p className="text-on-surface-variant font-semibold">Loading Analytics...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="bg-error-container text-on-error-container p-6 rounded-2xl max-w-md text-center">
          <span className="material-symbols-outlined text-4xl mb-4">error</span>
          <h2 className="font-headline font-bold text-lg mb-2">Analytics Unavailable</h2>
          <p className="text-sm">Could not fetch data from the backend. Make sure the server is running.</p>
        </div>
      </div>
    );
  }

  // Format charts data
  const pieData = data.languages_detected.map(l => ({ name: l.name.toUpperCase(), value: l.value }));
  const barData = data.messages_per_hour.map(m => {
    const d = new Date(m.hour);
    return {
      name: d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      Messages: m.count
    };
  });

  return (
    <div className="bg-background text-on-surface min-h-screen flex flex-col md:flex-row w-full font-body">
      
      {/* SideNavBar */}
      <aside className="w-full md:w-72 md:sticky left-0 top-0 bg-slate-50 dark:bg-slate-950 flex-col md:h-screen p-6 gap-y-2 flex z-40 border-r border-slate-200">
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-1">
            <span className="material-symbols-outlined text-indigo-500 text-3xl">language</span>
            <span className="text-xl font-bold text-indigo-900 font-headline">OmniLingua</span>
          </div>
          <p className="text-slate-500 text-xs font-semibold ml-11">Global Communication</p>
        </div>
        <nav className="flex flex-col gap-y-1">
          <a className="text-on-surface-variant hover:bg-slate-100 rounded-xl px-4 py-3 font-headline font-semibold text-sm flex items-center gap-3 transition-all" href="/">
            <span className="material-symbols-outlined">chat_bubble</span>
            All Chats
          </a>
          <a className="bg-indigo-50 text-indigo-700 rounded-xl px-4 py-3 font-headline font-semibold text-sm flex items-center gap-3 transition-all hover:translate-x-1" href="/admin">
            <span className="material-symbols-outlined">analytics</span>
            Analytics Dashboard
          </a>
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-6 md:p-10 overflow-y-auto w-full max-w-7xl mx-auto space-y-8">
        
        <header className="mb-10">
          <h1 className="text-3xl font-black font-headline text-indigo-950 tracking-tight">System Analytics</h1>
          <p className="text-on-surface-variant text-sm mt-2">Real-time performance metrics and conversation logs.</p>
        </header>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-surface-container-lowest border border-outline-variant/20 rounded-3xl p-6 shadow-sm flex flex-col justify-between hover:shadow-md transition-shadow">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <span className="material-symbols-outlined text-primary">forum</span>
              </div>
              <h3 className="font-semibold text-on-surface-variant text-sm">Total Messages</h3>
            </div>
            <p className="text-4xl font-black font-headline text-on-surface">{data.total_messages}</p>
          </div>

          <div className="bg-surface-container-lowest border border-outline-variant/20 rounded-3xl p-6 shadow-sm flex flex-col justify-between hover:shadow-md transition-shadow">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-emerald-500/10 flex items-center justify-center">
                <span className="material-symbols-outlined text-emerald-600">timer</span>
              </div>
              <h3 className="font-semibold text-on-surface-variant text-sm">Avg Global Response Time</h3>
            </div>
            <p className="text-4xl font-black font-headline text-on-surface">
              {data.avg_response_times.length > 0 
                ? `${Math.round(data.avg_response_times.reduce((acc, curr) => acc + curr.avg_ms, 0) / data.avg_response_times.length)} ms` 
                : 'N/A'}
            </p>
          </div>

          <div className="bg-surface-container-lowest border border-outline-variant/20 rounded-3xl p-6 shadow-sm flex flex-col justify-between hover:shadow-md transition-shadow">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center">
                <span className="material-symbols-outlined text-amber-600">translate</span>
              </div>
              <h3 className="font-semibold text-on-surface-variant text-sm">Unique Languages</h3>
            </div>
            <p className="text-4xl font-black font-headline text-on-surface">{data.languages_detected.length}</p>
          </div>
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          
          <div className="bg-surface-container-lowest border border-outline-variant/20 rounded-3xl p-8 shadow-sm">
            <h3 className="font-headline font-bold text-lg mb-6">Language Distribution</h3>
            <div className="h-64">
              {pieData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <RechartsTooltip 
                      contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                      itemStyle={{ fontWeight: 'bold' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-slate-400 text-sm">No data available</div>
              )}
            </div>
            <div className="flex flex-wrap gap-4 justify-center mt-4">
              {pieData.map((entry, index) => (
                <div key={index} className="flex items-center gap-2 text-xs font-semibold text-on-surface-variant">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }}></div>
                  {entry.name}
                </div>
              ))}
            </div>
          </div>

          <div className="bg-surface-container-lowest border border-outline-variant/20 rounded-3xl p-8 shadow-sm">
            <h3 className="font-headline font-bold text-lg mb-6">Message Volume (Hourly)</h3>
            <div className="h-64">
              {barData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e3e9ed" />
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#596064' }} dy={10} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#596064' }} />
                    <RechartsTooltip 
                      cursor={{ fill: '#f0f4f7' }}
                      contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                    />
                    <Bar dataKey="Messages" fill="#5755a9" radius={[4, 4, 0, 0]} maxBarSize={40} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-slate-400 text-sm">No data available</div>
              )}
            </div>
          </div>

        </div>

        {/* Live Feed Row */}
        <div className="bg-surface-container-lowest border border-outline-variant/20 rounded-3xl p-8 shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <h3 className="font-headline font-bold text-lg">Live Message Feed</h3>
            <span className="flex items-center gap-2 text-xs font-bold text-emerald-600 bg-emerald-50 px-3 py-1.5 rounded-full">
              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
              LIVE
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-outline-variant/20 text-on-surface-variant">
                  <th className="pb-3 font-semibold w-24">Time</th>
                  <th className="pb-3 font-semibold w-24">Language</th>
                  <th className="pb-3 font-semibold">User Message</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_messages.map((msg) => (
                  <tr key={msg.id} className="border-b border-outline-variant/10 last:border-0 hover:bg-slate-50 transition-colors">
                    <td className="py-4 text-xs font-medium text-slate-500 whitespace-nowrap">
                      {new Date(msg.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </td>
                    <td className="py-4">
                      <span className="bg-indigo-50 text-indigo-700 px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider">
                        {msg.language}
                      </span>
                    </td>
                    <td className="py-4 text-on-surface truncate max-w-md">
                      {msg.message}
                    </td>
                  </tr>
                ))}
                {data.recent_messages.length === 0 && (
                  <tr>
                    <td colSpan="3" className="py-8 text-center text-slate-400 italic">No messages recorded yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

      </main>
    </div>
  );
}

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import ChatView from './components/ChatView';
import VoiceView from './components/VoiceView';
import AutoFormView from './components/AutoFormView';
import AdminDashboard from './components/AdminDashboard';
import './index.css';

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col font-body">
        <Navbar />
        <main className="flex-1 flex flex-col">
          <Routes>
            <Route path="/" element={<ChatView />} />
            <Route path="/voice" element={<VoiceView />} />
            <Route path="/autoform" element={<AutoFormView />} />
            <Route path="/admin" element={<AdminDashboard />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import ChatView from './components/ChatView';
import AdminDashboard from './components/AdminDashboard';
import './index.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatView />} />
        <Route path="/admin" element={<AdminDashboard />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;

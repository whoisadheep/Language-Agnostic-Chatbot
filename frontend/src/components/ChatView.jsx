import { useState, useRef, useEffect } from 'react';
import '../index.css';

const LANGUAGES = [
  { value: "", label: "Auto-detect" },
  { value: "en", label: "English" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "hi", label: "Hindi" },
  { value: "bn", label: "Bengali" },
  { value: "zh-cn", label: "Chinese" },
  { value: "ja", label: "Japanese" },
  { value: "ar", label: "Arabic" },
  { value: "ru", label: "Russian" }
];

export default function ChatView() {
  const [messages, setMessages] = useState(() => {
    const saved = localStorage.getItem('chatHistory');
    return saved ? JSON.parse(saved) : [];
  });
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [overrideLang, setOverrideLang] = useState('');
  const [welcomeText, setWelcomeText] = useState("Welcome to OmniLingua! Type a message in any language.");
  const [toasts, setToasts] = useState([]);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    localStorage.setItem('chatHistory', JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    if (messages.length === 0) {
      const browserLang = navigator.language.split('-')[0];
      fetch(`http://localhost:8000/welcome?lang=${browserLang}`)
        .then(res => res.json())
        .then(data => {
          if (data.message) {
            setWelcomeText(data.message);
          }
        })
        .catch(err => console.error("Failed to fetch welcome message:", err));
    }
  }, [messages.length]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const clearChat = () => {
    if (window.confirm("Are you sure you want to clear the chat history?")) {
      setMessages([]);
      localStorage.removeItem('chatHistory');
    }
  };

  const addToast = (message, type = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 5000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || input.length > 500) return;

    const userText = input.trim();
    setInput('');
    
    const now = new Date();
    const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const newUserMessage = { 
      role: 'user', 
      text: userText, 
      lang: overrideLang || 'auto', 
      time: timeString 
    };
    setMessages(prev => [...prev, newUserMessage]);
    setIsLoading(true);

    try {
      const payload = { message: userText };
      if (overrideLang) {
        payload.override_language = overrideLang;
      }

      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (response.status === 429) {
        addToast("Rate limit exceeded (Max 20 requests/min). Please wait.", "error");
        throw new Error("429 Too Many Requests");
      }
      
      if (response.status === 422) {
        addToast("Validation Error: Message too long or invalid format.", "error");
        throw new Error("422 Validation Error");
      }

      if (!response.ok) {
        throw new Error(`Error: ${response.status}`);
      }

      const data = await response.json();
      
      if (data.warning === "language_detection_failed") {
        addToast("Could not detect language. Defaulting to English.", "warning");
      } else if (data.warning === "translation_api_down") {
        addToast("Translation service is currently down. Responding in English.", "warning");
      }
      
      const botTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const botMessage = { 
        role: 'bot', 
        text: data.response, 
        lang: data.detected_language || 'unknown',
        time: botTime
      };
      
      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      const botTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const errorMessage = { 
        role: 'bot', 
        text: "Sorry, I couldn't reach the server or an error occurred. Make sure your API key is set.", 
        lang: 'error',
        time: botTime
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const langStats = messages.reduce((acc, msg) => {
    if (msg.lang && msg.lang !== 'error' && msg.lang !== 'auto') {
      const langName = LANGUAGES.find(l => l.value === msg.lang)?.label || msg.lang.toUpperCase();
      acc[langName] = (acc[langName] || 0) + 1;
    }
    return acc;
  }, {});

  return (
    <div className="bg-background text-on-surface overflow-hidden h-screen flex w-full relative">
      
      {/* Toast Notifications */}
      <div className="absolute top-20 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2 pointer-events-none w-full max-w-sm px-4">
        {toasts.map(toast => (
          <div key={toast.id} className={`p-4 rounded-xl shadow-lg font-semibold text-sm flex items-center gap-3 animate-fade-in-up pointer-events-auto transition-all ${
            toast.type === 'error' ? 'bg-error-container text-on-error-container' :
            toast.type === 'warning' ? 'bg-amber-100 text-amber-900 border border-amber-200' :
            'bg-surface-container-highest text-on-surface'
          }`}>
            <span className="material-symbols-outlined">
              {toast.type === 'error' ? 'error' : toast.type === 'warning' ? 'warning' : 'info'}
            </span>
            {toast.message}
          </div>
        ))}
      </div>

      {/* SideNavBar (Desktop) */}
      <aside className="w-72 sticky left-0 top-0 bg-slate-50 dark:bg-slate-950 flex-col h-full p-6 gap-y-2 hidden md:flex z-40 justify-between">
        <div>
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-1">
              <span className="material-symbols-outlined text-indigo-500 text-3xl">language</span>
              <span className="text-xl font-bold text-indigo-900 font-headline">OmniLingua</span>
            </div>
            <p className="text-slate-500 text-xs font-semibold ml-11">Global Communication</p>
          </div>
          <button onClick={clearChat} className="mb-6 bg-gradient-to-br from-primary to-primary-dim text-on-primary py-3 px-4 rounded-xl font-headline font-bold flex w-full items-center justify-center gap-2 shadow-sm active:scale-95 transition-all">
            <span className="material-symbols-outlined" style={{fontVariationSettings: "'wght' 500"}}>delete</span>
            Clear Chat
          </button>
          <nav className="flex flex-col gap-y-1">
            <a className="bg-indigo-50 text-indigo-700 rounded-xl px-4 py-3 font-headline font-semibold text-sm flex items-center gap-3 transition-all hover:translate-x-1" href="/">
              <span className="material-symbols-outlined">chat_bubble</span>
              All Chats
            </a>
            <a className="text-on-surface-variant hover:bg-slate-100 rounded-xl px-4 py-3 font-headline font-semibold text-sm flex items-center gap-3 transition-all" href="/admin">
              <span className="material-symbols-outlined">analytics</span>
              Analytics Dashboard
            </a>
          </nav>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 relative h-screen">
        {/* TopAppBar */}
        <header className="fixed top-0 w-full z-30 bg-white/80 backdrop-blur-xl shadow-sm md:w-[calc(100%-18rem)] lg:w-[calc(100%-38rem)] xl:w-[calc(100%-38rem)]">
          <div className="flex justify-between items-center w-full px-6 py-3 max-w-[1920px] mx-auto">
            <div className="flex items-center gap-4">
              <button className="md:hidden p-2 text-on-surface">
                <span className="material-symbols-outlined">menu</span>
              </button>
              <span className="text-indigo-900 font-black text-2xl tracking-tighter font-headline md:hidden">OmniLingua</span>
              <span className="hidden md:block text-indigo-900 font-bold text-xl font-headline">Conversation</span>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={clearChat} className="md:hidden p-2 text-error hover:bg-slate-100 rounded-lg transition-colors active:scale-95">
                <span className="material-symbols-outlined">delete</span>
              </button>
              <div className="hidden lg:flex items-center bg-slate-50 px-3 py-1.5 rounded-full mr-4">
                <span className="w-2 h-2 bg-emerald-500 rounded-full mr-2"></span>
                <span className="text-xs font-semibold text-slate-600">Status: Active</span>
              </div>
            </div>
          </div>
        </header>

        {/* Chat Main Area */}
        <main className="flex-1 mt-16 overflow-y-auto no-scrollbar p-6 pb-40 flex flex-col space-y-8 max-w-5xl mx-auto w-full">
          <div className="flex justify-center">
            <span className="px-4 py-1 bg-surface-container-high text-on-surface-variant text-[10px] font-bold tracking-widest uppercase rounded-full">Today</span>
          </div>

          {messages.length === 0 && (
             <div className="flex justify-center my-10 animate-fade-in-up">
                <div className="bg-surface-container-highest text-on-surface p-6 rounded-xl text-center max-w-md shadow-sm">
                  <span className="material-symbols-outlined text-4xl text-indigo-500 mb-4">forum</span>
                  <h3 className="font-headline font-bold text-lg mb-2">Welcome to OmniLingua</h3>
                  <p className="text-sm text-on-surface-variant">{welcomeText}</p>
                </div>
             </div>
          )}

          {messages.map((msg, index) => {
            const langName = LANGUAGES.find(l => l.value === msg.lang)?.label || msg.lang.toUpperCase();
            if (msg.role === 'bot') {
              return (
                <div key={index} className="flex items-end gap-3 group animate-fade-in-up">
                  <div className="w-8 h-8 rounded-lg bg-surface-container-highest flex-shrink-0 flex items-center justify-center">
                    <span className="material-symbols-outlined text-indigo-500 text-lg">smart_toy</span>
                  </div>
                  <div className="flex flex-col gap-1.5 max-w-[80%] md:max-w-[70%]">
                    <div className="bg-surface-container-highest text-on-surface p-4 rounded-xl chat-bubble-inbound shadow-sm">
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                    </div>
                    <div className="flex items-center gap-2 ml-1">
                      {msg.lang && msg.lang !== 'error' && (
                        <span className="bg-surface-container-high text-on-tertiary-fixed-variant px-1.5 py-0.5 rounded-sm text-[9px] font-bold tracking-wider uppercase">
                          {langName}
                        </span>
                      )}
                      <span className="text-[10px] text-on-surface-variant opacity-60">{msg.time}</span>
                    </div>
                  </div>
                </div>
              );
            } else {
              return (
                <div key={index} className="flex items-end justify-end gap-3 animate-fade-in-up">
                  <div className="flex flex-col items-end gap-1.5 max-w-[80%] md:max-w-[70%]">
                    <div className="bg-gradient-to-br from-primary to-primary-dim text-on-primary p-4 rounded-xl chat-bubble-outbound shadow-lg">
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                    </div>
                    <div className="flex items-center gap-2 mr-1">
                      <span className="text-[10px] text-on-surface-variant opacity-60">{msg.time}</span>
                      {msg.lang && msg.lang !== 'auto' && (
                        <span className="bg-primary-container/30 text-primary-dim px-1.5 py-0.5 rounded-sm text-[9px] font-bold tracking-wider uppercase">
                           Override: {langName}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="w-8 h-8 rounded-lg bg-indigo-100 flex-shrink-0 flex items-center justify-center">
                    <span className="material-symbols-outlined text-indigo-700 text-lg">person</span>
                  </div>
                </div>
              );
            }
          })}

          {/* Typing Indicator */}
          {isLoading && (
            <div className="flex items-end gap-3 animate-fade-in-up">
              <div className="w-8 h-8 rounded-lg bg-surface-container-highest flex-shrink-0 flex items-center justify-center">
                <span className="material-symbols-outlined text-indigo-500 text-lg">smart_toy</span>
              </div>
              <div className="flex flex-col gap-1.5">
                <div className="bg-surface-container-highest/60 backdrop-blur-sm px-4 py-3 rounded-xl chat-bubble-inbound flex gap-1 items-center h-10">
                  <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{animationDelay: '-0.3s'}}></div>
                  <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{animationDelay: '-0.15s'}}></div>
                  <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce"></div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </main>

        {/* Chat Input Bar */}
        <footer className="absolute bottom-0 w-full p-6 bg-transparent pointer-events-none">
          <form onSubmit={handleSubmit} className="max-w-4xl mx-auto relative group pointer-events-auto flex flex-col gap-2">
            
            <div className="flex justify-end pr-2">
               <select 
                  value={overrideLang} 
                  onChange={(e) => setOverrideLang(e.target.value)}
                  className="bg-surface-container-lowest text-xs text-on-surface-variant border border-outline-variant/20 rounded-full px-3 py-1 shadow-sm outline-none focus:ring-1 focus:ring-primary/50"
                  disabled={isLoading}
               >
                  {LANGUAGES.map(l => (
                    <option key={l.value} value={l.value}>{l.label}</option>
                  ))}
               </select>
            </div>

            <div className="relative">
              <div className="absolute -inset-1 bg-gradient-to-r from-primary/10 to-indigo-500/10 rounded-full blur opacity-25 group-focus-within:opacity-100 transition duration-1000 group-focus-within:duration-200"></div>
              <div className="relative flex flex-col bg-surface-container-lowest border border-outline-variant/10 rounded-3xl p-2 pr-3 shadow-xl backdrop-blur-md">
                <div className="flex items-center">
                  <input 
                    className="flex-1 bg-transparent border-none focus:ring-0 text-sm px-4 text-on-surface placeholder:text-on-surface-variant/50 outline-none" 
                    placeholder="Type your message in any language..." 
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    maxLength={500}
                    disabled={isLoading}
                  />
                  <div className="flex items-center gap-3">
                    <span className={`text-[10px] font-bold ${input.length >= 500 ? 'text-error' : 'text-on-surface-variant/50'}`}>
                      {input.length}/500
                    </span>
                    <button 
                      type="submit" 
                      disabled={isLoading || !input.trim() || input.length > 500}
                      className="bg-primary hover:bg-primary-dim disabled:opacity-50 text-on-primary w-10 h-10 rounded-full flex items-center justify-center shadow-lg transition-all active:scale-90"
                    >
                      <span className="material-symbols-outlined" style={{fontVariationSettings: "'FILL' 1"}}>send</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </form>
          <p className="text-center mt-3 text-[10px] text-on-surface-variant/80 font-medium tracking-wide">AI-POWERED REAL-TIME TRANSLATION</p>
        </footer>
      </div>

      {/* Right Side Information Panel */}
      <aside className="hidden xl:flex w-80 bg-slate-50 h-screen flex-col p-6 border-l border-slate-100 z-40 relative">
        <div className="mb-8">
          <h3 className="font-headline font-bold text-lg mb-6">Conversation Context</h3>
          <div className="space-y-4">
            <div className="bg-white p-4 rounded-2xl shadow-sm">
              <p className="text-xs text-on-surface-variant font-bold uppercase tracking-wider mb-2">Language Stats</p>
              <div className="flex flex-col gap-2">
                {Object.entries(langStats).length > 0 ? (
                  Object.entries(langStats)
                    .sort((a, b) => b[1] - a[1]) // sort by count descending
                    .map(([lang, count], idx) => (
                    <div key={idx} className="flex justify-between items-center bg-indigo-50/50 px-2 py-1.5 rounded-lg">
                      <span className="text-indigo-700 text-[11px] font-bold">{lang}</span>
                      <span className="text-indigo-400 text-[10px] font-semibold">{count} time{count !== 1 ? 's' : ''}</span>
                    </div>
                  ))
                ) : (
                  <span className="text-xs text-slate-400 italic">No messages yet</span>
                )}
              </div>
            </div>
            <div className="bg-white p-4 rounded-2xl shadow-sm">
              <p className="text-xs text-on-surface-variant font-bold uppercase tracking-wider mb-2">Participants</p>
              <div className="flex items-center gap-3 mb-3">
                <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center">
                  <span className="material-symbols-outlined text-sm">smart_toy</span>
                </div>
                <div className="text-xs">
                  <p className="font-bold">OmniLingua AI</p>
                  <p className="text-on-surface-variant opacity-60">System Bot</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center">
                  <span className="material-symbols-outlined text-sm">person</span>
                </div>
                <div className="text-xs">
                  <p className="font-bold">You</p>
                  <p className="text-on-surface-variant opacity-60">Verified User</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}

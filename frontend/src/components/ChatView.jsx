import { useState, useRef, useEffect } from 'react';
import { Volume2, Sparkles, Trash2, Send, Bot, User, ArrowRight, ShieldCheck, Mic, MicOff } from 'lucide-react';
import { Link } from 'react-router-dom';
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
  const [welcomeText, setWelcomeText] = useState("Welcome to OmniAgent X! Type a message in any language, and the AI will auto-detect and respond seamlessly.");
  const [toasts, setToasts] = useState([]);
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef(null);
  const messagesEndRef = useRef(null);

  const toggleSpeechRecognition = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      addToast("Speech recognition is not supported in this browser. Please use Chrome or Edge.", "warning");
      return;
    }

    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      
      const langMap = {
        en: 'en-US', hi: 'hi-IN', es: 'es-ES', fr: 'fr-FR',
        de: 'de-DE', ja: 'ja-JP', ru: 'ru-RU', ar: 'ar-SA',
        bn: 'bn-IN', zh: 'zh-CN', 'zh-cn': 'zh-CN'
      };
      recognition.lang = langMap[overrideLang] || navigator.language || 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event) => {
        const text = event.results[0][0].transcript;
        if (text) {
          setInput(prev => (prev ? prev + ' ' + text : text));
        }
      };

      recognition.onerror = (e) => {
        console.error("SpeechRecognition error:", e);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.error("Failed to start speech recognition:", err);
      setIsListening(false);
    }
  };

  useEffect(() => {
    localStorage.setItem('chatHistory', JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    if (messages.length === 0) {
      const browserLang = navigator.language.split('-')[0];
      const host = window.location.hostname || 'localhost';
      fetch(`http://${host}:8000/welcome?lang=${browserLang}`)
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
    if (window.confirm("Are you sure you want to clear chat history?")) {
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

  const speakText = (text, lang = 'en') => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      const codeMap = {
        en: 'en-US',
        hi: 'hi-IN',
        es: 'es-ES',
        fr: 'fr-FR',
        de: 'de-DE',
        ja: 'ja-JP',
        ru: 'ru-RU',
        ar: 'ar-SA',
        bn: 'bn-IN',
        zh: 'zh-CN',
        'zh-cn': 'zh-CN'
      };
      utterance.lang = codeMap[lang] || 'en-US';
      window.speechSynthesis.speak(utterance);
    }
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
      const payload = {
        message: userText,
        history: messages.slice(-8).map(m => ({
          role: m.role === 'bot' ? 'assistant' : 'user',
          content: m.text
        }))
      };
      if (overrideLang) {
        payload.override_language = overrideLang;
      }

      const host = window.location.hostname || 'localhost';
      const response = await fetch(`http://${host}:8000/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (response.status === 429) {
        addToast("Rate limit exceeded (Max 40 req/min). Please wait a moment.", "error");
        throw new Error("429 Too Many Requests");
      }

      if (!response.ok) {
        throw new Error(`Error: ${response.status}`);
      }

      const data = await response.json();
      if (data.warning === "language_detection_failed") {
        addToast("Could not detect language. Defaulting to English.", "warning");
      }

      const botTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const botMessage = {
        role: 'bot',
        text: data.response,
        lang: data.detected_language || 'unknown',
        confidence: data.confidence,
        provider: data.provider,
        latency_ms: data.latency_ms,
        time: botTime
      };

      setMessages(prev => {
        if (prev.length > 0 && (!overrideLang || prev[prev.length - 1].lang === 'auto')) {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            lang: data.detected_language || updated[updated.length - 1].lang,
            confidence: data.confidence
          };
          return [...updated, botMessage];
        }
        return [...prev, botMessage];
      });
    } catch (error) {
      console.error('Failed to send message:', error);
      const botTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      setMessages(prev => [...prev, {
        role: 'bot',
        text: "I am having trouble connecting to the backend. Please ensure the server is active on port 8000.",
        lang: 'error',
        time: botTime
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col max-w-6xl mx-auto w-full p-4 md:p-6 h-[calc(100vh-4rem)] relative">
      {/* Toast Notifications */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2 pointer-events-none w-full max-w-sm px-4">
        {toasts.map(toast => (
          <div key={toast.id} className={`p-4 rounded-xl shadow-lg font-semibold text-xs flex items-center gap-3 animate-fade-in-up pointer-events-auto transition-all ${
            toast.type === 'error' ? 'bg-red-50 text-red-900 border border-red-200' :
            toast.type === 'warning' ? 'bg-amber-50 text-amber-900 border border-amber-200' :
            'bg-slate-900 text-white'
          }`}>
            <span>{toast.message}</span>
          </div>
        ))}
      </div>

      {/* Top Banner with Quick Actions */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800 mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-indigo-500" />
          <h2 className="font-bold font-headline text-slate-900 dark:text-white text-base">
            OmniChat Multilingual Hub
          </h2>
          <span className="hidden sm:inline-block text-[10px] bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 font-semibold px-2 py-0.5 rounded-full border border-indigo-200/50">
            Resilient Failover Protected
          </span>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/voice"
            className="text-xs text-indigo-600 hover:text-indigo-700 font-semibold hidden md:flex items-center gap-1 bg-indigo-50 dark:bg-indigo-950 px-3 py-1.5 rounded-xl border border-indigo-200/60"
          >
            <span>Launch OmniVoice</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
          <button
            onClick={clearChat}
            className="text-xs text-slate-400 hover:text-red-500 flex items-center gap-1 transition-colors px-2 py-1"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear
          </button>
        </div>
      </div>

      {/* Chat Messages Area */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2 pb-24">
        {messages.length === 0 && (
          <div className="flex justify-center my-12">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-3xl text-center max-w-md shadow-sm space-y-3">
              <div className="w-12 h-12 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 rounded-2xl flex items-center justify-center mx-auto">
                <Bot className="w-6 h-6" />
              </div>
              <h3 className="font-bold text-slate-900 dark:text-white text-base">
                Welcome to OmniAgent X
              </h3>
              <p className="text-xs text-slate-500 leading-relaxed">{welcomeText}</p>
              <div className="flex flex-wrap gap-2 justify-center pt-2">
                <span className="text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 px-2 py-1 rounded-lg">
                  हिंदी (Hindi)
                </span>
                <span className="text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 px-2 py-1 rounded-lg">
                  Español
                </span>
                <span className="text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 px-2 py-1 rounded-lg">
                  Français
                </span>
                <span className="text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 px-2 py-1 rounded-lg">
                  English
                </span>
              </div>
            </div>
          </div>
        )}

        {messages.map((msg, index) => {
          const isBot = msg.role === 'bot';
          const langLabel = LANGUAGES.find(l => l.value === msg.lang)?.label || msg.lang?.toUpperCase();

          return (
            <div
              key={index}
              className={`flex items-end gap-3 ${isBot ? 'justify-start' : 'justify-end'}`}
            >
              {isBot && (
                <div className="w-8 h-8 rounded-xl bg-indigo-100 dark:bg-indigo-950/80 text-indigo-600 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4" />
                </div>
              )}

              <div className={`flex flex-col gap-1 max-w-[85%] md:max-w-[75%] ${isBot ? 'items-start' : 'items-end'}`}>
                <div
                  className={`p-4 rounded-2xl text-xs md:text-sm leading-relaxed shadow-sm ${
                    isBot
                      ? 'bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 text-slate-800 dark:text-slate-100 rounded-bl-none'
                      : 'bg-indigo-600 text-white rounded-br-none shadow-indigo-500/20 shadow-md'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.text}</p>
                </div>

                {/* Metadata & Actions */}
                <div className="flex items-center gap-2 px-1 text-[10px] text-slate-400">
                  <span>{msg.time}</span>
                  {msg.lang && msg.lang !== 'error' && (
                    <span className="inline-flex items-center gap-1.5 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2 py-0.5 rounded font-semibold text-[10px]">
                      <span className="uppercase">{langLabel}</span>
                      {msg.confidence && (
                        <span className="font-mono text-emerald-600 dark:text-emerald-400 font-bold border-l border-slate-300 dark:border-slate-700 pl-1.5 tracking-tight">
                          {msg.confidence}%
                        </span>
                      )}
                    </span>
                  )}
                  {msg.provider && (
                    <span className="text-indigo-600 dark:text-indigo-400 font-mono font-medium">
                      via {msg.provider} ({msg.latency_ms}ms)
                    </span>
                  )}
                  {isBot && msg.text && (
                    <button
                      onClick={() => speakText(msg.text, msg.lang)}
                      className="hover:text-indigo-500 p-0.5 rounded transition-colors"
                      title="Listen with Text-to-Speech"
                    >
                      <Volume2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>

              {!isBot && (
                <div className="w-8 h-8 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 flex items-center justify-center flex-shrink-0">
                  <User className="w-4 h-4" />
                </div>
              )}
            </div>
          );
        })}

        {isLoading && (
          <div className="flex items-end gap-3">
            <div className="w-8 h-8 rounded-xl bg-indigo-100 dark:bg-indigo-950/80 text-indigo-600 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-4 py-3 rounded-2xl rounded-bl-none flex items-center gap-1.5 shadow-sm">
              <div className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '-0.3s' }} />
              <div className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '-0.15s' }} />
              <div className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="absolute bottom-4 left-4 right-4 max-w-6xl mx-auto">
        <form onSubmit={handleSubmit} className="flex flex-col gap-2">
          <div className="flex justify-end pr-2">
            <select
              value={overrideLang}
              onChange={(e) => setOverrideLang(e.target.value)}
              className="bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 text-xs border border-slate-200 dark:border-slate-800 rounded-full px-3 py-1 shadow-sm outline-none focus:ring-1 focus:ring-indigo-500"
              disabled={isLoading}
            >
              {LANGUAGES.map(l => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </div>

          <div className="relative flex items-center bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-2 pr-3 shadow-lg">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type in any language (e.g. 'Hello', 'नमस्ते', 'Bonjour', '¿Cómo estás?')..."
              maxLength={500}
              disabled={isLoading}
              className="flex-1 bg-transparent border-none text-xs md:text-sm px-4 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 outline-none"
            />
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-400 font-mono hidden sm:inline">
                {input.length}/500
              </span>
              <button
                type="button"
                onClick={toggleSpeechRecognition}
                className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all ${
                  isListening
                    ? 'bg-rose-500 text-white animate-pulse shadow-rose-500/30 shadow-md ring-2 ring-rose-400'
                    : 'bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300'
                }`}
                title={isListening ? "Listening... click to stop" : "Click to speak into text box"}
              >
                {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </button>
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="w-9 h-9 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white flex items-center justify-center shadow-md transition-all active:scale-95"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

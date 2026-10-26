import { useState, useRef, useEffect } from 'react';
import { Phone, PhoneOff, Mic, MicOff, Volume2, Sparkles, Trash2, Clock, Radio } from 'lucide-react';

export default function VoiceView() {
  const [isCalling, setIsCalling] = useState(false);
  const [callState, setCallState] = useState('idle'); // 'idle' | 'listening' | 'speaking' | 'connecting'
  const [isMuted, setIsMuted] = useState(false);
  const [duration, setDuration] = useState(0);
  const [dialogue, setDialogue] = useState([
    { role: 'assistant', text: 'Hello! I am OmniAgent Voice. How can I assist you today? You can speak in English, Hindi, or any language.', time: 'Initial' }
  ]);
  const [volumeLevel, setVolumeLevel] = useState([8, 12, 18, 14, 10]);

  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const micStreamRef = useRef(null);
  const processorRef = useRef(null);
  const timerRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isPlayingRef = useRef(false);
  const animFrameRef = useRef(null);
  const dialogueEndRef = useRef(null);
  const lastVisualizerUpdateRef = useRef(0);

  const isMutedRef = useRef(false);
  useEffect(() => {
    isMutedRef.current = isMuted;
  }, [isMuted]);

  useEffect(() => {
    dialogueEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [dialogue]);

  useEffect(() => {
    if (isCalling) {
      timerRef.current = setInterval(() => {
        setDuration(prev => prev + 1);
      }, 1000);
    } else {
      clearInterval(timerRef.current);
      setDuration(0);
    }
    return () => clearInterval(timerRef.current);
  }, [isCalling]);

  // Audio downsampling helper
  const downsample = (buffer, fromRate, toRate) => {
    if (fromRate === toRate) return buffer;
    const ratio = fromRate / toRate;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;
    while (offsetResult < result.length) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
      let accum = 0, count = 0;
      for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
        accum += buffer[i];
        count++;
      }
      result[offsetResult] = count > 0 ? accum / count : 0;
      offsetResult++;
      offsetBuffer = nextOffsetBuffer;
    }
    return result;
  };

  const floatTo16BitPCM = (float32Array) => {
    const buffer = new ArrayBuffer(float32Array.length * 2);
    const view = new DataView(buffer);
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]));
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return new Uint8Array(buffer);
  };

  const arrayBufferToBase64 = (buffer) => {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
  };

  const nextPlayTimeRef = useRef(0);
  const activeSourcesRef = useRef([]);

  const clearPlaybackQueue = () => {
    if ('speechSynthesis' in window) {
      try { window.speechSynthesis.cancel(); } catch (e) {}
    }
    activeSourcesRef.current.forEach(s => {
      try {
        s.stop();
        s.disconnect();
      } catch (e) {}
    });
    activeSourcesRef.current = [];
    if (audioCtxRef.current) {
      nextPlayTimeRef.current = audioCtxRef.current.currentTime;
    }
    setCallState('listening');
  };

  const playAudioChunk = (base64Payload) => {
    if (!audioCtxRef.current) return;
    const ctx = audioCtxRef.current;
    try {
      const binaryString = window.atob(base64Payload);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      const numSamples = Math.floor(bytes.byteLength / 2);
      if (numSamples === 0) return;
      const int16 = new Int16Array(bytes.buffer, bytes.byteOffset, numSamples);
      const float32 = new Float32Array(int16.length);
      for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768.0;
      }

      const audioBuffer = ctx.createBuffer(1, float32.length, 16000);
      audioBuffer.copyToChannel(float32, 0);

      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(ctx.destination);
      activeSourcesRef.current.push(source);

      source.onended = () => {
        const idx = activeSourcesRef.current.indexOf(source);
        if (idx > -1) activeSourcesRef.current.splice(idx, 1);
        if (activeSourcesRef.current.length === 0) {
          setCallState('listening');
        }
      };

      const now = ctx.currentTime;
      if (nextPlayTimeRef.current < now) {
        nextPlayTimeRef.current = now + 0.03;
      }
      source.start(nextPlayTimeRef.current);
      nextPlayTimeRef.current += audioBuffer.duration;

      setCallState('speaking');
    } catch (err) {
      console.error('Audio chunk decoding error:', err);
    }
  };

  const startCall = async () => {
    try {
      setCallState('connecting');
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioContextClass();
      if (audioCtx.state === 'suspended') {
        await audioCtx.resume();
      }
      audioCtxRef.current = audioCtx;
      nextPlayTimeRef.current = audioCtx.currentTime;

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      });
      micStreamRef.current = stream;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.hostname || 'localhost';
      const wsUrl = `${protocol}//${host}:8000/ws/voice`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsCalling(true);
        setCallState('listening');

        // Trigger initial greeting from backend
        ws.send(JSON.stringify({ event: 'start' }));

        // Setup microphone ScriptProcessor with zero-gain node to avoid acoustic loopback to speakers
        const micSource = audioCtx.createMediaStreamSource(stream);
        const bufferSize = 2048;
        const processor = audioCtx.createScriptProcessor(bufferSize, 1, 1);
        processorRef.current = processor;

        const muteGain = audioCtx.createGain();
        muteGain.gain.value = 0;
        micSource.connect(processor);
        processor.connect(muteGain);
        muteGain.connect(audioCtx.destination);

        processor.onaudioprocess = (e) => {
          if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
          if (isMutedRef.current) return;

          const inputData = e.inputBuffer.getChannelData(0);
          
          // Throttled visualizer update with high dynamic sensitivity
          const now = performance.now();
          if (now - lastVisualizerUpdateRef.current >= 60) {
            lastVisualizerUpdateRef.current = now;
            let sum = 0;
            for (let i = 0; i < inputData.length; i++) sum += inputData[i] * inputData[i];
            const rms = Math.sqrt(sum / inputData.length);
            if (rms < 0.005) {
              setVolumeLevel([6, 8, 10, 8, 6]);
            } else {
              const scaledH = Math.min(48, Math.max(12, Math.round(rms * 450)));
              setVolumeLevel([
                Math.max(6, Math.round(scaledH * 0.6)),
                Math.max(10, Math.round(scaledH * 0.9)),
                Math.max(14, scaledH),
                Math.max(8, Math.round(scaledH * 0.8)),
                Math.max(6, Math.round(scaledH * 0.5))
              ]);
            }
          }

          const downsampled = downsample(inputData, audioCtx.sampleRate, 16000);
          const pcm16 = floatTo16BitPCM(downsampled);
          const b64 = arrayBufferToBase64(pcm16.buffer);

          ws.send(JSON.stringify({
            event: 'media',
            media: { payload: b64 }
          }));
        };
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.event === 'media' && msg.media?.payload) {
            playAudioChunk(msg.media.payload);
          } else if (msg.event === 'clear') {
            clearPlaybackQueue();
            setCallState('listening');
          } else if (msg.event === 'transcript') {
            const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            setDialogue(prev => [...prev, {
              role: msg.role,
              text: msg.text,
              provider: msg.provider,
              lang: msg.lang,
              time: now
            }]);
          } else if (msg.event === 'speak_client') {
            // Client-side Web Speech API fallback with correct accent/language
            if ('speechSynthesis' in window) {
              setCallState('speaking');
              try { window.speechSynthesis.cancel(); } catch (e) {}
              const utterance = new SpeechSynthesisUtterance(msg.text);
              const langCodeMap = {
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
              if (msg.lang && langCodeMap[msg.lang]) {
                utterance.lang = langCodeMap[msg.lang];
              }
              utterance.onend = () => setCallState('listening');
              utterance.onerror = () => setCallState('listening');
              window.speechSynthesis.speak(utterance);
            }
          }
        } catch (e) {
          console.error('WebSocket parse error:', e);
        }
      };

      ws.onerror = (err) => {
        console.error('Voice WebSocket error:', err);
        endCall();
      };

      ws.onclose = () => {
        endCall();
      };

    } catch (err) {
      console.error('Failed to start call:', err);
      alert('Microphone access is required for OmniVoice: ' + err.message);
      setCallState('idle');
    }
  };

  const endCall = () => {
    setIsCalling(false);
    setCallState('idle');
    clearPlaybackQueue();
    setVolumeLevel([8, 12, 18, 14, 10]);

    if (wsRef.current) {
      try {
        if (wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ event: 'stop' }));
          wsRef.current.close();
        }
      } catch (e) {}
      wsRef.current = null;
    }

    if (processorRef.current) {
      try { processorRef.current.disconnect(); } catch (e) {}
      processorRef.current = null;
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach(t => t.stop());
      micStreamRef.current = null;
    }
    if (audioCtxRef.current) {
      try { audioCtxRef.current.close(); } catch (e) {}
      audioCtxRef.current = null;
    }
  };

  const formatTime = (secs) => {
    const mins = Math.floor(secs / 60);
    const rem = secs % 60;
    return `${mins.toString().padStart(2, '0')}:${rem.toString().padStart(2, '0')}`;
  };

  return (
    <div className="flex-1 flex flex-col md:flex-row gap-6 p-4 md:p-8 max-w-6xl mx-auto w-full">
      {/* Left: Phone Interface Terminal */}
      <div className="w-full md:w-96 flex flex-col items-center bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-xl relative overflow-hidden">
        {/* Glow Header */}
        <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex items-center gap-2 mb-2">
          <Radio className={`w-4 h-4 ${isCalling ? 'text-emerald-500 animate-pulse' : 'text-slate-400'}`} />
          <span className="text-xs font-semibold tracking-wider uppercase text-slate-500 dark:text-slate-400">
            {isCalling ? 'Voicera Duplex Live' : 'Voice Terminal Idle'}
          </span>
        </div>

        <h2 className="text-2xl font-bold font-headline text-slate-900 dark:text-white">OmniVoice</h2>
        <p className="text-xs text-slate-500 text-center mt-1 mb-6">
          Full-duplex 16kHz audio with custom RMS VAD & real-time conversational barge-in
        </p>

        {/* Status Call Avatar & Visualizer */}
        <div className="relative my-4 flex flex-col items-center justify-center">
          <div className={`w-36 h-36 rounded-full flex items-center justify-center transition-all duration-500 ${
            callState === 'speaking'
              ? 'bg-gradient-to-tr from-indigo-500 to-purple-600 shadow-lg shadow-indigo-500/30 scale-105'
              : callState === 'listening'
              ? 'bg-gradient-to-tr from-emerald-500 to-teal-600 shadow-lg shadow-emerald-500/30'
              : 'bg-slate-100 dark:bg-slate-800 border-2 border-dashed border-slate-300 dark:border-slate-700'
          }`}>
            <Volume2 className={`w-14 h-14 ${isCalling ? 'text-white animate-pulse' : 'text-slate-400'}`} />
          </div>

          {/* Animated Waveform Visualizer Bars */}
          <div className="flex items-center gap-2 h-14 mt-6">
            {volumeLevel.map((height, i) => (
              <div
                key={i}
                style={{ height: `${height}px` }}
                className={`w-2.5 rounded-full transition-all duration-75 ${
                  callState === 'speaking'
                    ? 'bg-indigo-500'
                    : callState === 'listening'
                    ? 'bg-emerald-500'
                    : 'bg-slate-300 dark:bg-slate-700'
                }`}
              />
            ))}
          </div>
        </div>

        {/* State Badge & Timer */}
        <div className="flex flex-col items-center gap-1 my-3">
          <span className={`text-xs px-3 py-1 rounded-full font-medium ${
            callState === 'speaking'
              ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300'
              : callState === 'listening'
              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
              : callState === 'connecting'
              ? 'bg-amber-100 text-amber-700 animate-pulse'
              : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
          }`}>
            {callState === 'speaking' && '🗣️ Agent Speaking...'}
            {callState === 'listening' && '👂 Listening (Barge-in active)'}
            {callState === 'connecting' && '⚡ Connecting WebSocket...'}
            {callState === 'idle' && 'Ready to Connect'}
          </span>
          <div className="flex items-center gap-1 text-slate-500 text-sm font-mono mt-1">
            <Clock className="w-3.5 h-3.5" />
            <span>{formatTime(duration)}</span>
          </div>
        </div>

        {/* Call Controls */}
        <div className="flex items-center justify-center gap-4 mt-6 w-full">
          {isCalling ? (
            <>
              <button
                onClick={() => setIsMuted(!isMuted)}
                className={`p-4 rounded-full border transition-all ${
                  isMuted
                    ? 'bg-amber-500 text-white border-amber-600 shadow-md'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-slate-200'
                }`}
                title={isMuted ? 'Unmute Mic' : 'Mute Mic'}
              >
                {isMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
              </button>
              <button
                onClick={endCall}
                className="px-6 py-4 rounded-full bg-red-600 hover:bg-red-700 text-white font-semibold flex items-center gap-2 shadow-lg shadow-red-500/25 transition-all hover:scale-105"
              >
                <PhoneOff className="w-5 h-5" />
                <span>End Call</span>
              </button>
            </>
          ) : (
            <button
              onClick={startCall}
              className="w-full py-4 rounded-2xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold flex items-center justify-center gap-3 shadow-xl shadow-indigo-500/20 transition-all hover:scale-[1.02]"
            >
              <Phone className="w-5 h-5" />
              <span>Start Voice Call</span>
            </button>
          )}
        </div>
      </div>

      {/* Right: Live Dialogue Transcript */}
      <div className="flex-1 flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-xl h-[600px]">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800 mb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-500" />
            <h3 className="font-semibold text-slate-900 dark:text-white">Live Voice Transcript</h3>
            <span className="text-xs bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded text-slate-500">
              STT: Sarvam AI Saaras:v3
            </span>
          </div>
          <button
            onClick={() => setDialogue([])}
            className="text-xs text-slate-400 hover:text-red-500 flex items-center gap-1 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear
          </button>
        </div>

        {/* Scrollable Chat Bubbles */}
        <div className="flex-1 overflow-y-auto space-y-4 pr-2">
          {dialogue.map((msg, i) => (
            <div
              key={i}
              className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div className="flex items-center gap-1.5 mb-1 px-1">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
                  {msg.role === 'user' ? 'You (Caller)' : 'OmniVoice Agent'}
                </span>
                <span className="text-[10px] text-slate-400 font-mono">{msg.time}</span>
              </div>
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
                  msg.role === 'user'
                    ? 'bg-indigo-600 text-white rounded-tr-none'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-100 rounded-tl-none border border-slate-200/60 dark:border-slate-700/60'
                }`}
              >
                <p className="leading-relaxed">{msg.text}</p>
                {msg.provider && (
                  <span className="inline-block mt-1 text-[10px] opacity-75 font-mono">
                    via {msg.provider}
                  </span>
                )}
              </div>
            </div>
          ))}
          <div ref={dialogueEndRef} />
        </div>

        {/* Live status bar at bottom */}
        <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <span>Interruption handling: <strong>Barge-in Enabled</strong></span>
          <span>Sample Rate: <strong>16,000 Hz</strong></span>
        </div>
      </div>
    </div>
  );
}

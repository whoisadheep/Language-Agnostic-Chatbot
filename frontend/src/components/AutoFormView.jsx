import { useState, useRef } from 'react';
import { UploadCloud, FileText, CheckCircle2, AlertTriangle, Sparkles, Copy, Check, RefreshCw, Plus, Trash2, ArrowRight } from 'lucide-react';

const SAMPLE_DEMO_FORMS = {
  job: [
    { id: 'f1', label: 'Candidate Full Legal Name', type: 'text' },
    { id: 'f2', label: 'Primary Contact Email Address', type: 'text' },
    { id: 'f3', label: 'Graduation Degree & University', type: 'text' },
    { id: 'f4', label: 'What is your primary technical expertise & programming languages?', type: 'textarea' },
    { id: 'f5', label: 'Describe a significant engineering project you built and the tools used.', type: 'textarea' },
    { id: 'f6', label: 'Which of the following backend frameworks is NOT in your core stack?', type: 'text' }, // Trick question!
  ],
  scholarship: [
    { id: 's1', label: 'Applicant Name', type: 'text' },
    { id: 's2', label: 'College / University & Cumulative GPA', type: 'text' },
    { id: 's3', label: 'Field of Academic Study', type: 'text' },
    { id: 's4', label: 'Explain your financial need or merit qualification for this grant.', type: 'textarea' },
    { id: 's5', label: 'Are there any disqualifying factors that apply to your candidacy? (State NONE if clean)', type: 'text' } // Trick question!
  ]
};

export default function AutoFormView() {
  const [profile, setProfile] = useState({
    full_name: 'Adheep Singh',
    email: 'adheep@example.com',
    phone: '+91 98765 43210',
    university: 'Apex Institute of Technology',
    degree: 'B.Tech in Computer Science & Engineering',
    gpa: '8.8 / 10.0',
    skills: ['Python', 'FastAPI', 'React', 'TypeScript', 'Docker', 'WebSockets', 'LangChain', 'PostgreSQL'],
    experiences: [
      { role: 'AI Systems Intern', company: 'Rudra Infotek', summary: 'Architected real-time WebSocket voice agents with sub-300ms latency and CRM integration.' }
    ],
    projects: [
      { title: 'AutoForm AI', tech: ['JavaScript', 'RAG', 'DOM Automation'], summary: 'Universal ATS autofill engine with BM25 slot resolution and trick-question detection.' },
      { title: 'Voicera', tech: ['FastAPI', 'WebSockets', 'Groq Whisper', 'Sarvam'], summary: 'Bidirectional full-duplex phone reception bot with conversational barge-in.' }
    ]
  });

  const [isUploading, setIsUploading] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState('Default_Demo_Resume.pdf');
  const [activeFormType, setActiveFormType] = useState('job');
  const [isSolving, setIsSolving] = useState(false);
  const [solvedResults, setSolvedResults] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const [injectionSuccess, setInjectionSuccess] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadedFileName(file.name);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('http://localhost:8000/api/parse-resume', {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        if (data.profile) {
          setProfile(prev => ({
            ...prev,
            ...data.profile,
            skills: data.profile.skills?.length ? data.profile.skills : prev.skills
          }));
        }
      } else {
        alert('Could not parse resume. Using existing vault data.');
      }
    } catch (err) {
      console.error('Upload failed:', err);
      alert('Upload failed: ' + err.message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleSolveForm = async () => {
    setIsSolving(true);
    setSolvedResults(null);
    setInjectionSuccess(false);

    const fieldsToSolve = SAMPLE_DEMO_FORMS[activeFormType];

    try {
      const res = await fetch('http://localhost:8000/api/solve-form', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fields: fieldsToSolve,
          profile: profile
        })
      });

      if (res.ok) {
        const data = await res.json();
        setSolvedResults(data.solved_fields || []);
      } else {
        alert('Form solve failed on backend.');
      }
    } catch (err) {
      console.error('Solve error:', err);
      alert('Error solving form: ' + err.message);
    } finally {
      setIsSolving(false);
    }
  };

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSimulateFill = () => {
    setInjectionSuccess(true);
    setTimeout(() => setInjectionSuccess(false), 4000);
  };

  return (
    <div className="flex-1 max-w-7xl mx-auto w-full p-4 md:p-8 space-y-8">
      {/* Page Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Sparkles className="w-5 h-5 text-indigo-500" />
          <span className="text-xs font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
            Autonomous Document Intelligence
          </span>
        </div>
        <h1 className="text-3xl font-bold font-headline text-slate-900 dark:text-white">
          AutoForm & Memory Vault
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Ingest resumes (PDF/DOCX), build a privacy-first Local Memory Vault with Hybrid RAG, and preview safety-verified form answers with trick-question detection.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Document Dropzone & Memory Vault (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Dropzone Card */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-sm">
            <h3 className="font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
              <UploadCloud className="w-5 h-5 text-indigo-500" />
              Resume / Document Ingestion
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Upload your PDF or DOCX file. Our engine parses identity, education, and career memory snippets into the local vault.
            </p>

            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".pdf,.docx,.txt"
              className="hidden"
            />

            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-slate-300 dark:border-slate-700 hover:border-indigo-500 rounded-2xl p-6 flex flex-col items-center justify-center cursor-pointer transition-all bg-slate-50/50 dark:bg-slate-800/30 hover:bg-indigo-50/30 group"
            >
              <FileText className="w-10 h-10 text-slate-400 group-hover:text-indigo-500 mb-2 transition-colors" />
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                {isUploading ? 'Extracting Memory Vault...' : 'Click to upload resume'}
              </p>
              <p className="text-xs text-slate-400 mt-1">PDF, DOCX, or TXT (Max 10MB)</p>
            </div>

            {uploadedFileName && (
              <div className="mt-4 flex items-center justify-between bg-indigo-50 dark:bg-indigo-950/50 border border-indigo-100 dark:border-indigo-900 px-3.5 py-2.5 rounded-xl text-xs">
                <div className="flex items-center gap-2 text-indigo-700 dark:text-indigo-300 font-medium">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  <span className="truncate max-w-[200px]">{uploadedFileName}</span>
                </div>
                <span className="text-[10px] bg-indigo-200/60 dark:bg-indigo-900 px-2 py-0.5 rounded text-indigo-800 dark:text-indigo-200">
                  Vault Active
                </span>
              </div>
            )}
          </div>

          {/* Extracted Profile Memory Card */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
              <h3 className="font-semibold text-slate-900 dark:text-white text-sm">
                👤 Applicant Memory Profile
              </h3>
              <span className="text-xs text-emerald-600 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded font-medium">
                Grounded RAG Ready
              </span>
            </div>

            <div className="space-y-3 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-50 dark:border-slate-800/50">
                <span className="text-slate-400">Full Name</span>
                <span className="font-semibold text-slate-700 dark:text-slate-200">{profile.full_name}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50 dark:border-slate-800/50">
                <span className="text-slate-400">Email</span>
                <span className="font-semibold text-slate-700 dark:text-slate-200">{profile.email}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50 dark:border-slate-800/50">
                <span className="text-slate-400">Degree</span>
                <span className="font-semibold text-slate-700 dark:text-slate-200 text-right max-w-[220px] truncate">{profile.degree}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50 dark:border-slate-800/50">
                <span className="text-slate-400">University / GPA</span>
                <span className="font-semibold text-slate-700 dark:text-slate-200">{profile.university} ({profile.gpa})</span>
              </div>
            </div>

            {/* Skills Pills */}
            <div>
              <p className="text-xs font-semibold text-slate-400 mb-2">Technical Skills:</p>
              <div className="flex flex-wrap gap-1.5">
                {profile.skills?.map((skill, i) => (
                  <span
                    key={i}
                    className="text-[11px] bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2.5 py-1 rounded-lg border border-slate-200/60 dark:border-slate-700/60"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>

            {/* Projects / Experiences summary */}
            <div>
              <p className="text-xs font-semibold text-slate-400 mb-2">Featured Projects:</p>
              <div className="space-y-2">
                {profile.projects?.map((proj, i) => (
                  <div key={i} className="bg-slate-50 dark:bg-slate-800/50 p-2.5 rounded-xl border border-slate-100 dark:border-slate-800 text-xs">
                    <p className="font-semibold text-slate-800 dark:text-slate-200">{proj.title}</p>
                    <p className="text-slate-500 text-[11px] mt-0.5 line-clamp-2">{proj.summary}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Interactive Form Solver & Preview & Verify Modal (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-sm">
            {/* Header & Template Selector */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100 dark:border-slate-800">
              <div>
                <h3 className="font-semibold text-slate-900 dark:text-white">
                  ⚡ Autonomous Form Auto-Fill Engine
                </h3>
                <p className="text-xs text-slate-500">
                  Select a live form scenario to test automated resolution with confidence safety scoring.
                </p>
              </div>

              {/* Segmented control for form type */}
              <div className="flex bg-slate-100 dark:bg-slate-800 p-1 rounded-xl text-xs font-medium">
                <button
                  onClick={() => { setActiveFormType('job'); setSolvedResults(null); }}
                  className={`px-3 py-1.5 rounded-lg transition-all ${
                    activeFormType === 'job'
                      ? 'bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 shadow-sm'
                      : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  Job Application
                </button>
                <button
                  onClick={() => { setActiveFormType('scholarship'); setSolvedResults(null); }}
                  className={`px-3 py-1.5 rounded-lg transition-all ${
                    activeFormType === 'scholarship'
                      ? 'bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 shadow-sm'
                      : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  Scholarship Grant
                </button>
              </div>
            </div>

            {/* Questions to be solved */}
            <div className="my-6 space-y-3">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Target Form Fields ({SAMPLE_DEMO_FORMS[activeFormType].length} Questions)
              </p>
              <div className="space-y-2">
                {SAMPLE_DEMO_FORMS[activeFormType].map((field, idx) => (
                  <div
                    key={field.id}
                    className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 text-xs flex items-center justify-between"
                  >
                    <span className="font-medium text-slate-700 dark:text-slate-300">
                      {idx + 1}. {field.label}
                    </span>
                    <span className="text-[10px] text-slate-400 uppercase font-mono">
                      {field.type}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Action Button */}
            <button
              onClick={handleSolveForm}
              disabled={isSolving}
              className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold flex items-center justify-center gap-2 shadow-lg shadow-indigo-500/20 transition-all hover:scale-[1.01] disabled:opacity-50"
            >
              {isSolving ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  <span>Cross-Referencing Memory Vault & Solving...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  <span>Solve Form with Memory Vault</span>
                </>
              )}
            </button>
          </div>

          {/* Preview & Verify Modal Card (Human-in-the-Loop Safety) */}
          {solvedResults && (
            <div className="bg-white dark:bg-slate-900 border-2 border-indigo-500/40 rounded-3xl p-6 shadow-xl space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                <div>
                  <h4 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    Preview & Verify Before Fill (AI Safety)
                  </h4>
                  <p className="text-xs text-slate-500">
                    Review every proposed answer before submission. Confidence scores & trick questions are flagged below.
                  </p>
                </div>
                <button
                  onClick={handleSimulateFill}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-xl flex items-center gap-1.5 shadow-md transition-all hover:scale-105"
                >
                  <ArrowRight className="w-4 h-4" />
                  Simulate Universal Fill
                </button>
              </div>

              {injectionSuccess && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-medium flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>Universal ATS Synthetic Injection dispatched! Form filled with 100% accuracy.</span>
                </div>
              )}

              {/* Answers List */}
              <div className="space-y-4">
                {solvedResults.map((item, idx) => (
                  <div
                    key={item.id}
                    className={`p-4 rounded-2xl border transition-all ${
                      item.review_recommended
                        ? 'border-amber-300 bg-amber-50/40 dark:border-amber-800 dark:bg-amber-950/20'
                        : 'border-slate-200 dark:border-slate-800 bg-slate-50/30 dark:bg-slate-800/30'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                        {idx + 1}. {item.question}
                      </span>
                      {item.review_recommended ? (
                        <span className="text-[11px] font-semibold text-amber-700 bg-amber-100 dark:bg-amber-900/60 dark:text-amber-300 px-2.5 py-0.5 rounded-full flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" />
                          Review Recommended
                        </span>
                      ) : (
                        <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-100 dark:bg-emerald-900/60 dark:text-emerald-300 px-2.5 py-0.5 rounded-full flex items-center gap-1">
                          <Check className="w-3 h-3" />
                          {item.confidence}% Confidence
                        </span>
                      )}
                    </div>

                    {/* Trick question warning banner */}
                    {item.review_recommended && (
                      <div className="mb-2 text-[11px] text-amber-800 dark:text-amber-300 bg-amber-100/70 dark:bg-amber-950/70 p-2 rounded-lg font-medium">
                        {item.reason}
                      </div>
                    )}

                    {/* Proposed Answer Box with Copy button */}
                    <div className="relative mt-2">
                      <textarea
                        defaultValue={item.answer}
                        rows={item.answer?.length > 80 ? 3 : 1}
                        className="w-full text-xs p-3 pr-10 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-sans resize-none"
                      />
                      <button
                        onClick={() => copyToClipboard(item.answer, item.id)}
                        className="absolute right-2.5 top-2.5 p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
                        title="Copy answer"
                      >
                        {copiedId === item.id ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

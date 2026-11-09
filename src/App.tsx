import React, { useState } from 'react';
import {
  Download,
  FolderTree,
  Terminal,
  ShieldCheck,
  CheckCircle2,
  Copy,
  Cpu,
  Layers,
  HardDrive,
  Play,
  FileCode,
  FileText,
  AlertCircle
} from 'lucide-react';

export default function App() {
  const [copiedCmd, setCopiedCmd] = useState(false);
  const [selectedTab, setSelectedTab] = useState<'layout' | 'builder' | 'params' | 'dependencies'>('layout');
  const [downloading, setDownloading] = useState(false);

  // Contributor API Parameters for live preview
  const [threads, setThreads] = useState(4);
  const [hashMb, setHashMb] = useState(1024);
  const [jobs, setJobs] = useState(1);
  const [cpuMode, setCpuMode] = useState<'Adaptive' | 'Balanced' | 'Maximum' | 'Custom'>('Adaptive');
  const [noFetchSyzygy, setNoFetchSyzygy] = useState(true);
  const [solve, setSolve] = useState(false);
  const [noAutoUpdate, setNoAutoUpdate] = useState(false);
  const [noEngineUpdate, setNoEngineUpdate] = useState(false);
  const [engineUpdateMin, setEngineUpdateMin] = useState(15.0);
  const [once, setOnce] = useState(false);
  const [customEngine, setCustomEngine] = useState('');
  const [customSyzygy, setCustomSyzygy] = useState('');

  const serverUrl = 'https://belzedar.duckdns.org';

  // Compute live command string (credentials hidden from UI)
  const commandPreview = [
    'AtomicDB.exe',
    '--exec-worker',
    `-S ${serverUrl}`,
    `-T ${threads}`,
    `--hash ${hashMb}`,
    jobs > 1 ? `--jobs ${jobs}` : '',
    customEngine ? `--engine "${customEngine}"` : '',
    customSyzygy ? `--syzygy "${customSyzygy}"` : '',
    noFetchSyzygy ? '--no-fetch-syzygy' : '',
    solve ? '--solve' : '',
    noAutoUpdate ? '--no-auto-update' : '',
    noEngineUpdate ? '--no-engine-update' : '',
    engineUpdateMin !== 15 ? `--engine-update-minutes ${engineUpdateMin}` : '',
    once ? '--once' : ''
  ].filter(Boolean).join(' ');

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCmd(true);
    setTimeout(() => setCopiedCmd(false), 2000);
  };

  const handleDownloadZip = () => {
    setDownloading(true);
    window.location.href = '/api/download-usb-package';
    setTimeout(() => setDownloading(false), 3000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-slate-950">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-cyan-600/20 text-cyan-400 rounded-xl border border-cyan-500/30 shadow-inner">
              <HardDrive className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold tracking-tight text-white">AtomicDB Portable</h1>
                <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Standalone • Zero-Server Required
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Self-Contained Windows x64 Client for OpenBench / Atomic Chess Distributed Analysis
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleDownloadZip}
              disabled={downloading}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white transition-colors shadow-md shadow-cyan-950 disabled:opacity-50"
            >
              <Download className="w-4 h-4" />
              {downloading ? 'Preparing Package...' : 'Download USB Package (.zip)'}
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8 space-y-8">
        
        {/* Top Highlights Banner */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-start gap-3">
            <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 shrink-0">
              <FolderTree className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Reimagined Easy-to-Find Layout</h3>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                Compiled binary placed directly in root as <code className="text-cyan-300 font-mono">AtomicDB.exe</code> and in <code className="text-cyan-300 font-mono">READY_TO_RUN_EXE/</code>.
              </p>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-start gap-3">
            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20 shrink-0">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Adaptive Hardware Control</h3>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                Dynamically regulates thread execution based on host CPU activity, keeping machines completely responsive.
              </p>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-start gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Zero Host Footprint (No C: Trace)</h3>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                <code className="text-emerald-300 font-mono">--no-fetch-syzygy</code> always enabled. Engines, logs, and temp write strictly to USB device.
              </p>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-800 gap-2 overflow-x-auto">
          <button
            onClick={() => setSelectedTab('layout')}
            className={`pb-3 px-4 text-sm font-medium border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
              selectedTab === 'layout'
                ? 'border-cyan-500 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <FolderTree className="w-4 h-4" />
            <span>Folder Layout & Quick Run</span>
          </button>

          <button
            onClick={() => setSelectedTab('builder')}
            className={`pb-3 px-4 text-sm font-medium border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
              selectedTab === 'builder'
                ? 'border-cyan-500 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Terminal className="w-4 h-4" />
            <span>1-Click .EXE Builder</span>
          </button>

          <button
            onClick={() => setSelectedTab('params')}
            className={`pb-3 px-4 text-sm font-medium border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
              selectedTab === 'params'
                ? 'border-cyan-500 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Cpu className="w-4 h-4" />
            <span>OpenBench Contributor Variables</span>
          </button>

          <button
            onClick={() => setSelectedTab('dependencies')}
            className={`pb-3 px-4 text-sm font-medium border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
              selectedTab === 'dependencies'
                ? 'border-cyan-500 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Offline Engine Pre-Downloader</span>
          </button>
        </div>

        {/* Tab 1: Folder Layout & Quick Run */}
        {selectedTab === 'layout' && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-2">
                <FolderTree className="w-5 h-5 text-cyan-400" />
                <span>Reimagined Folder Structure</span>
              </h2>
              <p className="text-sm text-slate-400 mb-6">
                The layout has been structured so you never have to search through build subdirectories. Your compiled executable is placed right in the root and in the dedicated USB folder.
              </p>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Visual Tree */}
                <div className="bg-slate-950 rounded-xl p-5 border border-slate-850 font-mono text-xs text-slate-300 leading-relaxed shadow-inner">
                  <div className="text-slate-500 pb-2 border-b border-slate-800 font-sans font-semibold text-xs flex items-center justify-between">
                    <span>EXPLORER DIRECTORY TREE</span>
                    <span className="text-cyan-400">USB Root</span>
                  </div>
                  <div className="mt-3 space-y-1.5">
                    <div className="text-slate-400">AtomicDBPortable/</div>
                    <div className="pl-4 flex items-center gap-2 text-cyan-300 font-bold bg-cyan-950/40 py-1 px-2 rounded border border-cyan-800/40">
                      <span>├── AtomicDB.exe</span>
                      <span className="text-[10px] bg-cyan-500/20 text-cyan-300 px-1.5 py-0.5 rounded ml-auto font-sans">
                        ★ Ready to Run (In Root!)
                      </span>
                    </div>
                    <div className="pl-4 flex items-center gap-2 text-emerald-300 py-0.5">
                      <span>├── RUN_ATOMICDB.bat</span>
                      <span className="text-[10px] text-emerald-400 font-sans ml-auto">
                        1-Click Launcher
                      </span>
                    </div>
                    <div className="pl-4 text-slate-300">├── build.bat</div>
                    <div className="pl-4 text-slate-400">├── download_dependencies.bat</div>
                    <div className="pl-4 flex items-center gap-2 text-cyan-400 py-0.5">
                      <span>├── READY_TO_RUN_EXE/</span>
                      <span className="text-[10px] text-cyan-400 font-sans ml-auto">
                        Standalone USB Folder
                      </span>
                    </div>
                    <div className="pl-8 text-cyan-200">├── AtomicDB.exe</div>
                    <div className="pl-8 text-slate-400">├── START_HERE.bat</div>
                    <div className="pl-8 text-slate-400">├── config/settings.json</div>
                    <div className="pl-8 text-slate-400">└── README_USB.txt</div>
                    <div className="pl-4 text-slate-400">├── config/</div>
                    <div className="pl-4 text-slate-400">├── worker/atomicdb_worker.py</div>
                    <div className="pl-4 text-slate-400">└── src/</div>
                  </div>
                </div>

                {/* 3-Step Quick Run Guide */}
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex items-start gap-4">
                    <div className="w-8 h-8 rounded-full bg-cyan-500/10 text-cyan-400 flex items-center justify-center font-bold text-sm border border-cyan-500/30 shrink-0">
                      1
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-white">Double-Click AtomicDB.exe</h4>
                      <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                        Located right in the project root folder (or use <code className="text-slate-300 font-mono">RUN_ATOMICDB.bat</code>). Zero installation or admin rights required.
                      </p>
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex items-start gap-4">
                    <div className="w-8 h-8 rounded-full bg-cyan-500/10 text-cyan-400 flex items-center justify-center font-bold text-sm border border-cyan-500/30 shrink-0">
                      2
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-white">Select Your CPU Profile</h4>
                      <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                        Adaptive mode automatically calibrates threads and transposition hash to your host machine's hardware.
                      </p>
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex items-start gap-4">
                    <div className="w-8 h-8 rounded-full bg-cyan-500/10 text-cyan-400 flex items-center justify-center font-bold text-sm border border-cyan-500/30 shrink-0">
                      3
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-white">Click "Start Contributing"</h4>
                      <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                        The supervisor launches the official worker process, monitors host CPU/RAM safely, and streams live analysis nodes directly to the console.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: 1-Click .EXE Builder */}
        {selectedTab === 'builder' && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-2">
                <Terminal className="w-5 h-5 text-cyan-400" />
                <span>1-Click Windows x64 .EXE Generator</span>
              </h2>
              <p className="text-sm text-slate-400 mb-6">
                How to compile your own standalone single-file binary using PyInstaller on Windows.
              </p>

              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider font-mono">
                      RECOMMENDED 1-CLICK GENERATOR
                    </span>
                    <span className="text-xs text-cyan-400 font-mono">build.bat</span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed mb-3">
                    Simply double-click <strong>build.bat</strong> in the project directory. It verifies Python 64-bit, installs PyInstaller, executes <code className="text-cyan-300 font-mono">AtomicDBPortable.spec</code>, and automatically copies <code className="text-cyan-300 font-mono">AtomicDB.exe</code> into the root folder!
                  </p>
                  <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 font-mono text-xs text-cyan-300 flex items-center justify-between">
                    <span>build.bat</span>
                    <button
                      onClick={() => copyToClipboard('build.bat')}
                      className="text-slate-400 hover:text-white"
                      title="Copy"
                    >
                      <Copy className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider font-mono">
                      MANUAL TERMINAL COMMAND
                    </span>
                    <span className="text-xs text-slate-500 font-mono">CMD / PowerShell</span>
                  </div>
                  <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 font-mono text-xs text-slate-300 flex items-center justify-between">
                    <span>python build_exe.py</span>
                    <button
                      onClick={() => copyToClipboard('python build_exe.py')}
                      className="text-slate-400 hover:text-white"
                      title="Copy"
                    >
                      <Copy className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: OpenBench Contributor Variables */}
        {selectedTab === 'params' && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-2">
                <Cpu className="w-5 h-5 text-cyan-400" />
                <span>OpenBench Contributor API Variables</span>
              </h2>
              <p className="text-sm text-slate-400 mb-6">
                All 14 variables supported by the official upstream worker are configurable via GUI inputs, number spinners, and switches.
              </p>


              {/* Live Parameter Controls */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Threads (-T)</label>
                  <input
                    type="number"
                    min="1"
                    max="64"
                    value={threads}
                    onChange={(e) => setThreads(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-sm font-mono text-cyan-300 focus:outline-none focus:border-cyan-500"
                  />
                  <span className="text-[11px] text-slate-500 mt-1 block">Total threads promised</span>
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Hash MB (--hash)</label>
                  <input
                    type="number"
                    min="64"
                    max="65536"
                    step="128"
                    value={hashMb}
                    onChange={(e) => setHashMb(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-sm font-mono text-cyan-300 focus:outline-none focus:border-cyan-500"
                  />
                  <span className="text-[11px] text-slate-500 mt-1 block">Transposition table memory</span>
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Jobs (--jobs)</label>
                  <input
                    type="number"
                    min="1"
                    max="32"
                    value={jobs}
                    onChange={(e) => setJobs(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-sm font-mono text-cyan-300 focus:outline-none focus:border-cyan-500"
                  />
                  <span className="text-[11px] text-slate-500 mt-1 block">Split -T across jobs</span>
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Engine Check Min</label>
                  <input
                    type="number"
                    min="1"
                    max="1440"
                    value={engineUpdateMin}
                    onChange={(e) => setEngineUpdateMin(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-sm font-mono text-cyan-300 focus:outline-none focus:border-cyan-500"
                  />
                  <span className="text-[11px] text-slate-500 mt-1 block">--engine-update-minutes</span>
                </div>
              </div>

              {/* Boolean Toggles */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 mb-6">
                <label className="flex items-center gap-2 p-3 rounded-lg bg-slate-950 border border-slate-800 cursor-pointer hover:bg-slate-900">
                  <input
                    type="checkbox"
                    checked={noFetchSyzygy}
                    onChange={(e) => setNoFetchSyzygy(e.target.checked)}
                    className="rounded border-slate-700 text-cyan-600 focus:ring-cyan-500"
                  />
                  <span className="text-xs font-medium text-slate-300">No Tablebase (--no-fetch-syzygy)</span>
                </label>

                <label className="flex items-center gap-2 p-3 rounded-lg bg-slate-950 border border-slate-800 cursor-pointer hover:bg-slate-900">
                  <input
                    type="checkbox"
                    checked={solve}
                    onChange={(e) => setSolve(e.target.checked)}
                    className="rounded border-slate-700 text-cyan-600 focus:ring-cyan-500"
                  />
                  <span className="text-xs font-medium text-slate-300">Solve Proofs (--solve)</span>
                </label>

                <label className="flex items-center gap-2 p-3 rounded-lg bg-slate-950 border border-slate-800 cursor-pointer hover:bg-slate-900">
                  <input
                    type="checkbox"
                    checked={noAutoUpdate}
                    onChange={(e) => setNoAutoUpdate(e.target.checked)}
                    className="rounded border-slate-700 text-cyan-600 focus:ring-cyan-500"
                  />
                  <span className="text-xs font-medium text-slate-300">No Self-Update (--no-auto-update)</span>
                </label>

                <label className="flex items-center gap-2 p-3 rounded-lg bg-slate-950 border border-slate-800 cursor-pointer hover:bg-slate-900">
                  <input
                    type="checkbox"
                    checked={noEngineUpdate}
                    onChange={(e) => setNoEngineUpdate(e.target.checked)}
                    className="rounded border-slate-700 text-cyan-600 focus:ring-cyan-500"
                  />
                  <span className="text-xs font-medium text-slate-300">No Engine Swap (--no-engine-update)</span>
                </label>

                <label className="flex items-center gap-2 p-3 rounded-lg bg-slate-950 border border-slate-800 cursor-pointer hover:bg-slate-900">
                  <input
                    type="checkbox"
                    checked={once}
                    onChange={(e) => setOnce(e.target.checked)}
                    className="rounded border-slate-700 text-cyan-600 focus:ring-cyan-500"
                  />
                  <span className="text-xs font-medium text-slate-300">Run Single Task (--once)</span>
                </label>
              </div>

              {/* Real-time Command Preview */}
              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-400 font-mono">SUPERVISOR INVOCATION PREVIEW</span>
                  <button
                    onClick={() => copyToClipboard(commandPreview)}
                    className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-mono"
                  >
                    {copiedCmd ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copiedCmd ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>
                <div className="font-mono text-xs text-cyan-300 p-3 bg-slate-900 rounded-lg border border-slate-800 overflow-x-auto whitespace-pre">
                  {commandPreview}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Offline Engine Pre-Downloader */}
        {selectedTab === 'dependencies' && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-2">
                <Layers className="w-5 h-5 text-cyan-400" />
                <span>Offline Engine Pre-Downloader</span>
              </h2>
              <p className="text-sm text-slate-400 mb-6">
                When preparing a USB drive to run on computers with restricted internet access, you can pre-fetch the verified engine directly onto the USB storage before departure.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <h4 className="text-sm font-semibold text-white mb-2">download_dependencies.bat</h4>
                  <p className="text-xs text-slate-400 mb-4 leading-relaxed">
                    Double-click this batch script directly on your USB drive. It queries the official AtomicDB manifest, downloads the matching prebuilt engine for Windows x86_64, and validates its SHA256 integrity hash.
                  </p>
                  <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 font-mono text-xs text-slate-300 flex items-center justify-between">
                    <span>download_dependencies.bat</span>
                    <button
                      onClick={() => copyToClipboard('download_dependencies.bat')}
                      className="text-slate-400 hover:text-white"
                      title="Copy"
                    >
                      <Copy className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <h4 className="text-sm font-semibold text-white mb-2">Zero-Trace Verification</h4>
                  <p className="text-xs text-slate-400 mb-4 leading-relaxed">
                    Downloaded binaries are stored strictly in <code className="text-cyan-300 font-mono">Engines/</code> relative to the executable root directory. Nothing touches the host computer's C: drive.
                  </p>
                  <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 text-xs text-emerald-400 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                    <span>Host C: AppData/Local/Temp completely bypassed</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="border-t border-slate-850 bg-slate-900/50 py-6 text-center text-xs text-slate-500">
        <p>AtomicDB Portable • Standalone Computing Client • Zero Administrative Rights Required</p>
      </footer>
    </div>
  );
}

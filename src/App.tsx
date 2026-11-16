import React, { useState, useEffect, useRef } from 'react';
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
  FileCode,
  FileText,
  AlertCircle,
  Activity,
  LineChart,
  BarChart2,
  Clock,
  Zap,
  Database,
  RefreshCw
} from 'lucide-react';

export default function App() {
  const [copiedCmd, setCopiedCmd] = useState(false);
  const [selectedTab, setSelectedTab] = useState<'layout' | 'builder' | 'params' | 'analytics' | 'dependencies'>('analytics');
  const [downloading, setDownloading] = useState(false);
  const [showLifetimeReport, setShowLifetimeReport] = useState(false);

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

  // Diagnostic Data & Real-Time Telemetry States
  const [sessionUptimeSec, setSessionUptimeSec] = useState(148);
  const [sessionTasks, setSessionTasks] = useState(6);
  const [sessionNodes, setSessionNodes] = useState(48000000);
  const [currentNps, setCurrentNps] = useState(3850000);
  const [sessionAvgNps, setSessionAvgNps] = useState(3620000);

  // Current Task
  const [currentTaskId, setCurrentTaskId] = useState('7115');
  const [currentTaskNodes, setCurrentTaskNodes] = useState(8000000);
  const [currentTaskNodesDone, setCurrentTaskNodesDone] = useState(3600000);
  const [currentTaskLine, setCurrentTaskLine] = useState('pv: e4 e5 Nf3 Nc6 Bc4 Nf6 d3 Bc5 c3 d6 O-O a6');
  const [currentTaskEtaSeconds, setCurrentTaskEtaSeconds] = useState<number>(2);

  // Lifetime Statistics
  const [lifetimeTasks, setLifetimeTasks] = useState(1248);
  const [lifetimeNodes, setLifetimeNodes] = useState(9984000000);
  const [lifetimeAvgNps, setLifetimeAvgNps] = useState(3850210);
  const [lifetimeRuntimeStr, setLifetimeRuntimeStr] = useState('18h 42m 15s');
  const [lifetimeCpuHours, setLifetimeCpuHours] = useState(149.60);
  const [lifetimeSessions, setLifetimeSessions] = useState(14);
  const [lifetimeReportText, setLifetimeReportText] = useState(
`===================================================================
   ATOMICDB PORTABLE — LIFETIME STATISTICS (PERMANENT USB LOG)     
===================================================================
Last Updated:             2026-11-11 16:45:00
Total Tasks Completed:    1,248
Total Lifetime Nodes:     9,984,000,000 (9.98 B)
Lifetime Average NPS:     3,850,210 nodes/sec (3.85 M/s)
Total Accumulated Time:   18h 42m 15s (67,335 seconds)
Total CPU Hours:          149.60 CPU hours
Total Number of Sessions: 14 sessions
===================================================================
NOTICE: This log records all historical analysis performed from
this portable drive. Logs and metrics are preserved permanently.
===================================================================`
  );

  const TIMEFRAME_DIALS = [
    { label: '1.5 mins', seconds: 90 },
    { label: '5 mins', seconds: 300 },
    { label: '10 mins', seconds: 600 },
  ] as const;

  const [graphTimeframeIdx, setGraphTimeframeIdx] = useState<number>(1); // Default: 5 mins

  const initNow = useRef(Date.now()).current;
  const formatClock = (ms: number) => {
    const d = new Date(ms);
    return d.toTimeString().slice(0, 8);
  };

  // Graphs time-series (this session with timestamps across trailing 10 mins)
  const [cpuSeries, setCpuSeries] = useState<{ t: string; tsMs: number; sys: number; wrk: number }[]>([
    { tsMs: initNow - 570_000, t: formatClock(initNow - 570_000), sys: 22, wrk: 16 },
    { tsMs: initNow - 480_000, t: formatClock(initNow - 480_000), sys: 25, wrk: 19 },
    { tsMs: initNow - 390_000, t: formatClock(initNow - 390_000), sys: 31, wrk: 24 },
    { tsMs: initNow - 270_000, t: formatClock(initNow - 270_000), sys: 28, wrk: 22 },
    { tsMs: initNow - 210_000, t: formatClock(initNow - 210_000), sys: 33, wrk: 26 },
    { tsMs: initNow - 150_000, t: formatClock(initNow - 150_000), sys: 29, wrk: 23 },
    { tsMs: initNow - 80_000, t: formatClock(initNow - 80_000), sys: 35, wrk: 28 },
    { tsMs: initNow - 45_000, t: formatClock(initNow - 45_000), sys: 30, wrk: 25 },
    { tsMs: initNow - 15_000, t: formatClock(initNow - 15_000), sys: 27, wrk: 22 }
  ]);

  const [ramSeries, setRamSeries] = useState<{ t: string; tsMs: number; wrk: number; avail: number }[]>([
    { tsMs: initNow - 570_000, t: formatClock(initNow - 570_000), wrk: 175, avail: 6820 },
    { tsMs: initNow - 480_000, t: formatClock(initNow - 480_000), wrk: 185, avail: 6800 },
    { tsMs: initNow - 390_000, t: formatClock(initNow - 390_000), wrk: 205, avail: 6740 },
    { tsMs: initNow - 270_000, t: formatClock(initNow - 270_000), wrk: 220, avail: 6700 },
    { tsMs: initNow - 210_000, t: formatClock(initNow - 210_000), wrk: 215, avail: 6710 },
    { tsMs: initNow - 150_000, t: formatClock(initNow - 150_000), wrk: 235, avail: 6680 },
    { tsMs: initNow - 80_000, t: formatClock(initNow - 80_000), wrk: 240, avail: 6650 },
    { tsMs: initNow - 45_000, t: formatClock(initNow - 45_000), wrk: 245, avail: 6640 },
    { tsMs: initNow - 15_000, t: formatClock(initNow - 15_000), wrk: 242, avail: 6650 }
  ]);

  const [npsSeries, setNpsSeries] = useState<{ taskId: string; nps: number; t: string; tsMs: number }[]>([
    { taskId: '#7109', nps: 3420000, tsMs: initNow - 540_000, t: formatClock(initNow - 540_000) },
    { taskId: '#7110', nps: 3650000, tsMs: initNow - 420_000, t: formatClock(initNow - 420_000) },
    { taskId: '#7111', nps: 3810000, tsMs: initNow - 280_000, t: formatClock(initNow - 280_000) },
    { taskId: '#7112', nps: 3550000, tsMs: initNow - 180_000, t: formatClock(initNow - 180_000) },
    { taskId: '#7113', nps: 3920000, tsMs: initNow - 80_000, t: formatClock(initNow - 80_000) },
    { taskId: '#7114', nps: 3740000, tsMs: initNow - 40_000, t: formatClock(initNow - 40_000) },
    { taskId: '#7115', nps: 3850000, tsMs: initNow - 10_000, t: formatClock(initNow - 10_000) }
  ]);

  const [recentTasks, setRecentTasks] = useState<any[]>([
    { id: '7114', type: 'ENGINE', nodes: 128000000, nps: 3740000, time: '2.14s', result: 'score cp 32 pv e4 e5 Nf3', ts: '16:46:12' },
    { id: '7113', type: 'ENGINE', nodes: 512000000, nps: 3920000, time: '2.04s', result: 'score cp -15 pv d4 d5 c4', ts: '16:44:08' },
    { id: '7112', type: 'TABLEBASE', nodes: 0, nps: 0, time: '0.01s', result: 'wdl=1 dtz=3 -> mate 4', ts: '16:42:01' },
    { id: '7111', type: 'SOLVE', nodes: 2000000000, nps: 3810000, time: '3.15s', result: 'PROVEN_WIN: 1. e4', ts: '16:40:19' }
  ]);

  const activeTaskIdRef = useRef<string | null>(null);

  // Live session timer & ETA countdown (reduces strictly by whole 1s steps, supports negative integers)
  useEffect(() => {
    const timer = setInterval(() => {
      setSessionUptimeSec(prev => prev + 1);
      setCurrentTaskEtaSeconds(prev => (prev !== null ? Math.round(prev) - 1 : -1));
    }, 1000);

    const fetchAnalytics = async () => {
      try {
        const res = await fetch('/api/analytics');
        if (res.ok) {
          const data = await res.json();
          if (data && data.analytics) {
            const an = data.analytics;
            if (an.lifetime_tasks_completed) setLifetimeTasks(an.lifetime_tasks_completed);
            if (an.lifetime_total_nodes) setLifetimeNodes(an.lifetime_total_nodes);
            if (an.lifetime_average_nps) setLifetimeAvgNps(an.lifetime_average_nps);
            if (an.lifetime_cpu_hours !== undefined) setLifetimeCpuHours(an.lifetime_cpu_hours);
            if (an.lifetime_total_sessions) setLifetimeSessions(an.lifetime_total_sessions);
            if (an.lifetime_total_runtime_seconds) {
              const s = Math.floor(an.lifetime_total_runtime_seconds);
              const h = Math.floor(s / 3600);
              const m = Math.floor((s % 3600) / 60);
              setLifetimeRuntimeStr(`${h}h ${m}m ${s % 60}s`);
            }
            if (an.session_tasks_completed !== undefined) setSessionTasks(an.session_tasks_completed);
            if (an.session_total_nodes !== undefined) setSessionNodes(an.session_total_nodes);
            if (an.current_nps !== undefined) setCurrentNps(an.current_nps);
            if (an.session_average_nps !== undefined) setSessionAvgNps(an.session_average_nps);
            if (an.session_uptime_seconds !== undefined) setSessionUptimeSec(Math.floor(an.session_uptime_seconds));

            const nextTaskId = an.current_task_id || null;
            const taskChanged = nextTaskId !== activeTaskIdRef.current;
            if (nextTaskId) {
              setCurrentTaskId(nextTaskId);
              activeTaskIdRef.current = nextTaskId;
            }
            if (an.current_task_nodes) setCurrentTaskNodes(an.current_task_nodes);
            if (an.current_task_nodes_done !== undefined) setCurrentTaskNodesDone(an.current_task_nodes_done);
            if (an.current_task_line) setCurrentTaskLine(an.current_task_line);
            if (an.current_task_eta_seconds !== undefined && an.current_task_eta_seconds !== null) {
              const roundedServerEta = Math.round(an.current_task_eta_seconds);
              setCurrentTaskEtaSeconds(prev => {
                if (taskChanged || prev === null || Math.abs(prev - roundedServerEta) > 2) {
                  return roundedServerEta;
                }
                return prev;
              });
            }

            if (an.cpu_history && Array.isArray(an.cpu_history) && an.cpu_history.length > 0) {
              setCpuSeries(an.cpu_history.map((pt: any) => ({
                t: pt.timestamp || '',
                tsMs: pt.time ? pt.time * 1000 : Date.now(),
                sys: pt.system_cpu || 0,
                wrk: pt.worker_cpu || 0
              })));
            }
            if (an.ram_history && Array.isArray(an.ram_history) && an.ram_history.length > 0) {
              setRamSeries(an.ram_history.map((pt: any) => ({
                t: pt.timestamp || '',
                tsMs: pt.time ? pt.time * 1000 : Date.now(),
                wrk: pt.worker_ram || 0,
                avail: pt.available_ram || 4096
              })));
            }
            if (an.nps_task_history && Array.isArray(an.nps_task_history) && an.nps_task_history.length > 0) {
              setNpsSeries(an.nps_task_history.map((pt: any) => ({
                taskId: `#${pt.task_id}`,
                nps: pt.nps || 0,
                tsMs: pt.time ? pt.time * 1000 : Date.now(),
                t: pt.timestamp || ''
              })));
            }
          }
          if (data.lifetimeReport) {
            setLifetimeReportText(data.lifetimeReport);
          }
          if (data.recentTasks && data.recentTasks.length > 0) {
            setRecentTasks(data.recentTasks.slice().reverse());
          }
        }
      } catch (err) {
        // Fallback gracefully to live simulator
      }
    };

    fetchAnalytics();
    const pollInterval = setInterval(fetchAnalytics, 3000);

    return () => {
      clearInterval(timer);
      clearInterval(pollInterval);
    };
  }, []);

  const formatEta = (sec: number | null) => {
    if (sec === null || isNaN(sec)) return 'Calculating...';
    const whole = Math.round(sec);
    if (whole === 0) return '0s';
    if (whole > 0) {
      if (whole < 60) return `${whole}s`;
      const m = Math.floor(whole / 60);
      const s = whole % 60;
      return `${m}m ${s.toString().padStart(2, '0')}s`;
    } else {
      const abs = Math.abs(whole);
      if (abs < 60) return `-${abs}s`;
      const m = Math.floor(abs / 60);
      const s = abs % 60;
      return `-${m}m ${s.toString().padStart(2, '0')}s`;
    }
  };

  const formatUptimeDigital = (sec: number) => {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const formatNodes = (n: number) => {
    const clean = (val: number) => Number(val.toFixed(2)).toString();
    if (n >= 1_000_000_000) return `${clean(n / 1_000_000_000)}b`;
    if (n >= 1_000_000) return `${clean(n / 1_000_000)}m`;
    if (n >= 1_000) return `${clean(n / 1_000)}k`;
    return n.toLocaleString();
  };

  const activeDial = TIMEFRAME_DIALS[graphTimeframeIdx] || TIMEFRAME_DIALS[1];
  const filterByDial = <T extends { tsMs?: number }>(arr: T[]): T[] => {
    if (!arr.length) return [];
    const latestMs = Math.max(Date.now(), arr[arr.length - 1]?.tsMs ?? Date.now());
    const cutoff = latestMs - activeDial.seconds * 1000;
    const filtered = arr.filter(pt => (pt.tsMs ?? latestMs) >= cutoff);
    return filtered;
  };
  const filteredCpuSeries = filterByDial(cpuSeries);
  const filteredRamSeries = filterByDial(ramSeries);
  const filteredNpsSeries = filterByDial(npsSeries);

  const formatNps = (n: number) => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)} M/s`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)} k/s`;
    return `${n.toLocaleString()} /s`;
  };

  // Compute live command string
  const commandPreview = [
    'AtomicDB.exe',
    '--exec-worker',
    `-T ${threads}`,
    `--hash ${hashMb}`,
    jobs > 1 ? `--jobs ${jobs}` : '',
    customEngine ? `--engine "${customEngine}"` : '',
    customSyzygy ? `--syzygy "${customSyzygy}"` : '',
    noFetchSyzygy ? '--no-fetch-syzygy' : '--fetch-syzygy',
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
                  Live Telemetry • Zero Trace on C:
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Self-Contained Windows x64 Client with Real-Time Session Graphs & Permanent Lifetime Logs
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
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Live Diagnostic Dashboard</h3>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                Tracks session stats, current calculating line, task ETA based on last 3 tasks, and 0.8s real-time telemetry graphs.
              </p>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-start gap-3">
            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20 shrink-0">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Adaptive Mode & 0.8s Telemetry</h3>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                Leaves 50% of cores off (checks every 20s) with ultra-smooth 0.8s CPU & RAM monitor and flexible splitter controls.
              </p>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-start gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Permanent Logs & Zero C: Trace</h3>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                Lifetime stats saved in <code className="text-emerald-300 font-mono">logs/lifetime_statistics.txt</code> on USB drive — preserved permanently and never cleared.
              </p>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-800 gap-2 overflow-x-auto">
          <button
            onClick={() => setSelectedTab('analytics')}
            className={`pb-3 px-4 text-sm font-medium border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
              selectedTab === 'analytics'
                ? 'border-cyan-500 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Activity className="w-4 h-4" />
            <span>Diagnostic Dashboard & Graphs</span>
          </button>

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

        {/* Tab: Diagnostic Data Dashboard & Real-Time Graphs */}
        {selectedTab === 'analytics' && (
          <div className="space-y-6">
            
            {/* 1. CURRENT TASK MONITOR */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-2 mb-5">
                <div className="flex items-center gap-2">
                  <Zap className="w-5 h-5 text-amber-400" />
                  <h3 className="text-base font-semibold text-white">Current Task (Active Execution)</h3>
                </div>
                <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  <span>Saved in <code className="text-amber-300">logs/current_task.log</code> & <code className="text-amber-300">activity.log</code></span>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
                <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">Task ID</span>
                  <div className="text-xl font-bold font-mono text-cyan-400">#{currentTaskId}</div>
                  <span className="text-[10px] text-slate-500">Active worker slot</span>
                </div>

                <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">Nodes in Task</span>
                  <div className="text-xl font-bold text-emerald-400">{formatNodes(currentTaskNodes)}</div>
                  <span className="text-[10px] text-slate-500">Target budget</span>
                </div>

                <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">Est. Time Remaining</span>
                  <div className={`text-xl font-bold font-mono ${currentTaskEtaSeconds < 0 ? 'text-rose-400' : 'text-amber-400'}`}>
                    {formatEta(currentTaskEtaSeconds)}
                  </div>
                  <span className="text-[10px] text-slate-500">Calculated before task (1s/s)</span>
                </div>

                <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">Current NPS</span>
                  <div className="text-xl font-bold text-purple-400">{formatNps(currentNps)}</div>
                  <span className="text-[10px] text-slate-500">Live throughput</span>
                </div>
              </div>

              {/* Calculating Line */}
              <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 mb-1.5">
                  <span className="uppercase font-semibold">The line the current task is calculating:</span>
                  <span className="text-cyan-400">Engine PV / Candidate Variation</span>
                </div>
                <div className="p-2.5 bg-slate-900 rounded border border-slate-850 font-mono text-xs text-cyan-300 overflow-x-auto whitespace-pre">
                  {currentTaskLine}
                </div>
              </div>
            </div>

            {/* 2. SESSION STATISTICS */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-2 mb-5">
                <div className="flex items-center gap-2">
                  <Clock className="w-5 h-5 text-cyan-400" />
                  <h3 className="text-base font-semibold text-white">Session Statistics (This Session)</h3>
                </div>
                <span className="text-xs font-mono text-slate-400">
                  Recorded in <code className="text-cyan-300">logs/session_statistics.log</code>
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
                <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">Tasks Completed</span>
                  <div className="text-xl font-bold text-cyan-400">{sessionTasks}</div>
                  <span className="text-[10px] text-slate-500">This session</span>
                </div>

                <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">Total Nodes</span>
                  <div className="text-xl font-bold text-emerald-400">{formatNodes(sessionNodes)}</div>
                  <span className="text-[10px] text-slate-500">{sessionNodes.toLocaleString()} nodes</span>
                </div>

                <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">Current NPS</span>
                  <div className="text-xl font-bold text-cyan-300">{formatNps(currentNps)}</div>
                  <span className="text-[10px] text-slate-500">Live rate</span>
                </div>

                <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">Average NPS</span>
                  <div className="text-xl font-bold text-purple-400">{formatNps(sessionAvgNps)}</div>
                  <span className="text-[10px] text-slate-500">Session average</span>
                </div>

                <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">Session Uptime</span>
                  <div className="text-xl font-bold font-mono text-rose-400">{formatUptimeDigital(sessionUptimeSec)}</div>
                  <span className="text-[10px] text-slate-500">Active client runtime</span>
                </div>
              </div>
            </div>

            {/* 3. LIFETIME STATISTICS */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-2 mb-5">
                <div className="flex items-center gap-2">
                  <Database className="w-5 h-5 text-emerald-400" />
                  <h3 className="text-base font-semibold text-white">Lifetime Statistics (Permanent USB Report)</h3>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/40">
                    Preserved permanently • Never cleared
                  </span>
                  <button
                    onClick={() => setShowLifetimeReport(!showLifetimeReport)}
                    className="text-xs px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-cyan-300 rounded border border-slate-700 font-mono transition-colors"
                  >
                    {showLifetimeReport ? 'Hide TXT Report' : 'View lifetime_statistics.txt'}
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-4">
                <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">Total Tasks</span>
                  <div className="text-xl font-bold text-cyan-400">{lifetimeTasks.toLocaleString()}</div>
                  <span className="text-[10px] text-slate-500">All sessions</span>
                </div>

                <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">Lifetime Nodes</span>
                  <div className="text-xl font-bold text-emerald-400">{formatNodes(lifetimeNodes)}</div>
                  <span className="text-[10px] text-slate-500">Cumulative search</span>
                </div>

                <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">Lifetime Avg NPS</span>
                  <div className="text-xl font-bold text-amber-400">{formatNps(lifetimeAvgNps)}</div>
                  <span className="text-[10px] text-slate-500">Lifetime speed</span>
                </div>

                <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">Accumulated Runtime</span>
                  <div className="text-base font-bold text-purple-400 pt-1">{lifetimeRuntimeStr}</div>
                  <span className="text-[10px] text-slate-500">Total hours</span>
                </div>

                <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">Total CPU Hours</span>
                  <div className="text-xl font-bold text-rose-400">{lifetimeCpuHours.toFixed(2)}</div>
                  <span className="text-[10px] text-slate-500">Core compute-hours</span>
                </div>

                <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">Total Sessions</span>
                  <div className="text-xl font-bold text-cyan-300">{lifetimeSessions}</div>
                  <span className="text-[10px] text-slate-500">Distinct client runs</span>
                </div>
              </div>

              {/* Expandable Lifetime Text Report Preview */}
              {showLifetimeReport && (
                <div className="mt-4 p-4 bg-slate-950 rounded-lg border border-slate-800 font-mono text-xs text-slate-300 leading-relaxed shadow-inner">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-800 text-slate-400 mb-2 font-sans font-semibold text-xs">
                    <span>RAW USB LOG: /logs/lifetime_statistics.txt</span>
                    <button
                      onClick={() => copyToClipboard(lifetimeReportText)}
                      className="text-cyan-400 hover:text-white flex items-center gap-1 font-mono text-[11px]"
                    >
                      <Copy className="w-3.5 h-3.5" />
                      <span>{copiedCmd ? 'Copied!' : 'Copy TXT'}</span>
                    </button>
                  </div>
                  <pre className="overflow-x-auto whitespace-pre text-emerald-300">
                    {lifetimeReportText}
                  </pre>
                </div>
              )}
            </div>

            {/* 4. REAL-TIME SESSION GRAPHS (0.8s TELEMETRY + TIMEFRAME SLIDER) */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-800 gap-4 mb-5">
                <div className="flex items-center gap-2">
                  <LineChart className="w-5 h-5 text-cyan-400" />
                  <h3 className="text-base font-semibold text-white">Graphs (This Session • 0.8s Refresh)</h3>
                </div>

                {/* Graph Timeframe Slider with Set Dials (1.5 mins, 5 mins, 10 mins) */}
                <div className="flex flex-wrap items-center gap-3 bg-slate-950 px-3.5 py-2 rounded-lg border border-slate-800">
                  <span className="text-[11px] font-mono uppercase text-slate-400 font-semibold">Timeframe:</span>
                  <input
                    type="range"
                    min={0}
                    max={TIMEFRAME_DIALS.length - 1}
                    step={1}
                    value={graphTimeframeIdx}
                    onChange={(e) => setGraphTimeframeIdx(Number(e.target.value))}
                    aria-label="Graph Timeframe Slider"
                    className="w-28 accent-cyan-400 cursor-pointer"
                  />
                  <div className="flex items-center gap-1.5">
                    {TIMEFRAME_DIALS.map((dial, idx) => (
                      <button
                        key={dial.label}
                        type="button"
                        onClick={() => setGraphTimeframeIdx(idx)}
                        className={`px-2.5 py-1 rounded text-[11px] font-mono font-semibold transition-colors ${
                          graphTimeframeIdx === idx
                            ? 'bg-cyan-600 text-white border border-cyan-400 shadow-sm'
                            : 'bg-slate-900 text-slate-300 border border-slate-700 hover:bg-slate-800'
                        }`}
                      >
                        {dial.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* Graph 1: CPU Usage Over Time */}
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-mono font-semibold text-slate-300 uppercase">CPU Usage Over Time (%)</span>
                      <span className="text-[11px] font-mono text-cyan-400">
                        Sys: {filteredCpuSeries[filteredCpuSeries.length - 1]?.sys ?? 0}% | Wrk: {filteredCpuSeries[filteredCpuSeries.length - 1]?.wrk ?? 0}%
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-[10px] text-slate-400 mb-3">
                      <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-amber-400"></span> System CPU</span>
                      <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-cyan-400"></span> Worker CPU</span>
                    </div>
                  </div>

                  {/* SVG Chart */}
                  <div className="h-32 w-full pt-2">
                    <svg className="w-full h-full overflow-visible" viewBox="0 0 280 100">
                      {/* Grid lines */}
                      <line x1="0" y1="25" x2="280" y2="25" stroke="#1e293b" strokeDasharray="3 3" />
                      <line x1="0" y1="50" x2="280" y2="50" stroke="#1e293b" strokeDasharray="3 3" />
                      <line x1="0" y1="75" x2="280" y2="75" stroke="#1e293b" strokeDasharray="3 3" />
                      
                      {/* System CPU Polyline (Amber) */}
                      {filteredCpuSeries.length >= 2 && (
                        <polyline
                          fill="none"
                          stroke="#fbbf24"
                          strokeWidth="2"
                          points={filteredCpuSeries.map((d, i) => `${(i / Math.max(1, filteredCpuSeries.length - 1)) * 280},${100 - (Math.min(100, Math.max(0, d.sys)) / 100) * 100}`).join(' ')}
                        />
                      )}
                      {/* Worker CPU Polyline (Cyan) */}
                      {filteredCpuSeries.length >= 2 && (
                        <polyline
                          fill="none"
                          stroke="#38bdf8"
                          strokeWidth="2.5"
                          points={filteredCpuSeries.map((d, i) => `${(i / Math.max(1, filteredCpuSeries.length - 1)) * 280},${100 - (Math.min(100, Math.max(0, d.wrk)) / 100) * 100}`).join(' ')}
                        />
                      )}
                    </svg>
                  </div>
                  <div className="flex justify-between text-[10px] font-mono text-slate-400 mt-2 border-t border-slate-900 pt-1">
                    <span>{filteredCpuSeries[0]?.t || '--:--:--'}</span>
                    <span>{filteredCpuSeries[Math.floor(filteredCpuSeries.length / 2)]?.t || '--:--:--'}</span>
                    <span>{filteredCpuSeries[filteredCpuSeries.length - 1]?.t || '--:--:--'}</span>
                  </div>
                </div>

                {/* Graph 2: RAM Usage Over Time */}
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-mono font-semibold text-slate-300 uppercase">RAM Usage Over Time (MB)</span>
                      <span className="text-[11px] font-mono text-purple-400">
                        RSS: {filteredRamSeries[filteredRamSeries.length - 1]?.wrk ?? 0} MB
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-[10px] text-slate-400 mb-3">
                      <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-purple-400"></span> Worker RSS</span>
                      <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-emerald-400"></span> Host Avail</span>
                    </div>
                  </div>

                  {/* SVG Chart */}
                  <div className="h-32 w-full pt-2">
                    <svg className="w-full h-full overflow-visible" viewBox="0 0 280 100">
                      <line x1="0" y1="33" x2="280" y2="33" stroke="#1e293b" strokeDasharray="3 3" />
                      <line x1="0" y1="66" x2="280" y2="66" stroke="#1e293b" strokeDasharray="3 3" />
                      
                      {/* Worker RAM Polyline */}
                      {filteredRamSeries.length >= 2 && (
                        <polyline
                          fill="none"
                          stroke="#a78bfa"
                          strokeWidth="2.5"
                          points={filteredRamSeries.map((d, i) => `${(i / Math.max(1, filteredRamSeries.length - 1)) * 280},${100 - (Math.min(512, Math.max(0, d.wrk)) / 512) * 100}`).join(' ')}
                        />
                      )}
                    </svg>
                  </div>
                  <div className="flex justify-between text-[10px] font-mono text-slate-400 mt-2 border-t border-slate-900 pt-1">
                    <span>{filteredRamSeries[0]?.t || '--:--:--'}</span>
                    <span>{filteredRamSeries[Math.floor(filteredRamSeries.length / 2)]?.t || '--:--:--'}</span>
                    <span>{filteredRamSeries[filteredRamSeries.length - 1]?.t || '--:--:--'}</span>
                  </div>
                </div>

                {/* Graph 3: NPS Per Task */}
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-mono font-semibold text-slate-300 uppercase">NPS Per Task (Speed Trend)</span>
                      <span className="text-[11px] font-mono text-emerald-400">
                        Latest: {formatNps(filteredNpsSeries[filteredNpsSeries.length - 1]?.nps ?? 0)}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-[10px] text-slate-400 mb-3">
                      <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-cyan-400"></span> Completed Task Speed</span>
                      <span className="text-slate-500 font-mono">Window: {activeDial.label}</span>
                    </div>
                  </div>

                  {/* SVG Bar Chart */}
                  <div className="h-32 w-full pt-2">
                    <svg className="w-full h-full overflow-visible" viewBox="0 0 280 100">
                      <line x1="0" y1="50" x2="280" y2="50" stroke="#1e293b" strokeDasharray="3 3" />
                      {filteredNpsSeries.map((d, i) => {
                        const barW = Math.min(22, Math.max(8, 220 / Math.max(1, filteredNpsSeries.length)));
                        const spacing = 280 / Math.max(1, filteredNpsSeries.length);
                        const x = i * spacing + (spacing - barW) / 2;
                        const bh = (d.nps / 5000000) * 90;
                        const y = 100 - bh;
                        return (
                          <rect
                            key={i}
                            x={x}
                            y={y}
                            width={barW}
                            height={bh}
                            fill="#38bdf8"
                            rx="3"
                          />
                        );
                      })}
                    </svg>
                  </div>
                  <div className="flex justify-between text-[10px] font-mono text-slate-400 mt-2 border-t border-slate-900 pt-1">
                    {filteredNpsSeries.map((d, i) => (
                      <div key={i} className="flex flex-col items-center">
                        <span className="text-cyan-300 font-semibold">{d.taskId}</span>
                        <span className="text-[9px] text-slate-500">{d.t || ''}</span>
                      </div>
                    ))}
                  </div>
                </div>

              </div>
            </div>

            {/* 5. PERSISTENT TASK EXECUTION HISTORY TABLE */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-2 mb-4">
                <div className="flex items-center gap-2">
                  <FileText className="w-5 h-5 text-cyan-400" />
                  <h3 className="text-base font-semibold text-white">Persistent Task Execution History</h3>
                </div>
                <span className="text-xs font-mono text-slate-400">
                  Loaded from <code className="text-cyan-300">logs/history.json</code>
                </span>
              </div>

              <div className="overflow-x-auto rounded-lg border border-slate-800">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-950 text-cyan-400 border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3">Time</th>
                      <th className="py-2.5 px-3">Task ID</th>
                      <th className="py-2.5 px-3">Type</th>
                      <th className="py-2.5 px-3">Nodes</th>
                      <th className="py-2.5 px-3">NPS</th>
                      <th className="py-2.5 px-3">Duration</th>
                      <th className="py-2.5 px-3">Result / Score</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 bg-slate-900/60">
                    {recentTasks.map((t, i) => (
                      <tr key={i} className="hover:bg-slate-800/40 transition-colors">
                        <td className="py-2 px-3 text-slate-400">{t.ts || t.timestamp || 'Now'}</td>
                        <td className="py-2 px-3 text-cyan-300 font-bold">{t.id || t.task_id}</td>
                        <td className="py-2 px-3">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-sans font-semibold ${
                            (t.type || '').toUpperCase() === 'SOLVE'
                              ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                              : (t.type || '').toUpperCase() === 'TABLEBASE'
                              ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                              : 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                          }`}>
                            {t.type || 'ENGINE'}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-emerald-400">{t.nodes ? formatNodes(t.nodes) : '-'}</td>
                        <td className="py-2 px-3 text-purple-300">{t.nps ? formatNps(t.nps) : '-'}</td>
                        <td className="py-2 px-3 text-slate-300">{t.time || (t.elapsed_sec ? `${t.elapsed_sec}s` : '-')}</td>
                        <td className="py-2 px-3 text-slate-200 truncate max-w-xs">{t.result || t.summary}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        )}

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
                    <div className="pl-4 text-slate-400">├── logs/</div>
                    <div className="pl-8 text-emerald-300">├── lifetime_statistics.txt</div>
                    <div className="pl-8 text-cyan-300">├── session_statistics.log</div>
                    <div className="pl-8 text-amber-300">├── current_task.log</div>
                    <div className="pl-8 text-slate-400">└── history.json</div>
                    <div className="pl-4 text-slate-400">├── worker/atomicdb_worker.py</div>
                    <div className="pl-4 text-slate-400">└── src/</div>
                  </div>
                </div>

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
                      <h4 className="text-sm font-semibold text-white">Adaptive Hardware Control (50% Off)</h4>
                      <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                        Adaptive mode automatically calibrates threads leaving 50% of cores off for responsive host multitasking, updating every 20s.
                      </p>
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex items-start gap-4">
                    <div className="w-8 h-8 rounded-full bg-cyan-500/10 text-cyan-400 flex items-center justify-center font-bold text-sm border border-cyan-500/30 shrink-0">
                      3
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-white">Real-Time Diagnostic Dashboard</h4>
                      <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                        Track live calculation variations, task ETA, session uptime, permanent lifetime statistics in <code className="text-cyan-300 font-mono">lifetime_statistics.txt</code>, and 0.8s time-series graphs.
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
                <span>1-Click Windows x64 .EXE Generator with Post-Build Cleanup</span>
              </h2>
              <p className="text-sm text-slate-400 mb-6">
                How to compile your own standalone single-file binary using PyInstaller on Windows. All intermediate files are automatically cleaned up!
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
                    Simply double-click <strong>build.bat</strong> in the project directory. It verifies Python 64-bit, installs PyInstaller, executes <code className="text-cyan-300 font-mono">AtomicDBPortable.spec</code>, copies <code className="text-cyan-300 font-mono">AtomicDB.exe</code> into the root folder, and deletes all excess build/dist and bytecode cache files!
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
                All runtime parameters are configurable via GUI inputs, number spinners, and switches. Contributor credentials and server URL are unadjustable and hidden for zero-configuration contributor deployment.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Threads (-T)</label>
                  <input
                    type="number"
                    min="1"
                    max="64"
                    value={threads}
                    onChange={(e) => setThreads(parseInt(e.target.value) || 1)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-cyan-400 font-mono"
                  />
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Hash MB (--hash)</label>
                  <input
                    type="number"
                    min="64"
                    step="128"
                    value={hashMb}
                    onChange={(e) => setHashMb(parseInt(e.target.value) || 64)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-cyan-400 font-mono"
                  />
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Jobs (--jobs)</label>
                  <input
                    type="number"
                    min="1"
                    max="64"
                    value={jobs}
                    onChange={(e) => setJobs(parseInt(e.target.value) || 1)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-cyan-400 font-mono"
                  />
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <label className="text-xs font-semibold text-slate-300 block mb-1">CPU Allocation Mode</label>
                  <select
                    value={cpuMode}
                    onChange={(e) => setCpuMode(e.target.value as any)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-cyan-400 font-mono"
                  >
                    <option value="Adaptive">Adaptive (50% Cores Off)</option>
                    <option value="Balanced">Balanced (~50%)</option>
                    <option value="Maximum">Maximum (N - 1)</option>
                    <option value="Custom">Custom</option>
                  </select>
                </div>
              </div>

              {/* Live Preview Bar */}
              <div className="p-4 bg-slate-950 rounded-xl border border-slate-800">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono font-semibold text-slate-400 uppercase">
                    LIVE COMMAND LINE INVOCATION
                  </span>
                  <button
                    onClick={() => copyToClipboard(commandPreview)}
                    className="text-xs text-cyan-400 hover:text-white flex items-center gap-1 font-mono"
                  >
                    <Copy className="w-3.5 h-3.5" />
                    <span>{copiedCmd ? 'Copied' : 'Copy Command'}</span>
                  </button>
                </div>
                <div className="font-mono text-xs text-cyan-300 p-3 bg-slate-900 rounded-lg border border-slate-800 overflow-x-auto whitespace-pre">
                  {commandPreview}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 5: Offline Engine Pre-Downloader */}
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

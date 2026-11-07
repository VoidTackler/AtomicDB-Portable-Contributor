import React, { useState, useEffect, useMemo } from 'react';
import {
  Cpu,
  Server,
  Shield,
  Key,
  Play,
  Pause,
  RefreshCw,
  Sliders,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Copy,
  Terminal,
  Usb,
  Search,
  Lock,
  Unlock,
  Radio,
  BarChart3,
  ListOrdered,
  Clock,
  Layers,
  Zap,
  Globe
} from 'lucide-react';

interface Device {
  id: string;
  name: string;
  ipAddress?: string;
  enrolledAt: string;
  lastSeen: string;
  uptimeSeconds: number;
  totalTasksCompleted: number;
  totalNodesAnalyzed: number;
  status: 'ACTIVE' | 'PAUSED' | 'THROTTLED' | 'OFFLINE' | 'REVOKED' | 'LOCAL_STOP' | 'TERMINATED';
  localStopActive: boolean;
  cpuMode: 'Adaptive' | 'Maximum' | 'Balanced' | 'Custom';
  hardware: {
    cpuModel: string;
    physicalCores: number;
    logicalCores: number;
    ramTotalMb: number;
    instructions: string[];
  };
  metrics: {
    systemCpuPct: number;
    workerCpuPct: number;
    ramUsedMb: number;
    threadsAllocated: number;
    hashAllocatedMb: number;
    taskSpeedNps: number;
  };
  versions: {
    worker: string;
    engine: string;
    python: string;
  };
  currentTask?: {
    taskName: string;
    fenSnippet: string;
    depth: number;
    nodesAnalyzed: number;
  };
  lastNonce: number;
}

interface FleetStats {
  totalDevices: number;
  activeNodes: number;
  pausedNodes: number;
  throttledNodes: number;
  offlineNodes: number;
  terminatedNodes: number;
  totalCores: number;
  activeThreads: number;
  totalHashAllocatedMb: number;
  aggregateNps: number;
  totalTasksCompleted: number;
  auditLogsCount: number;
  openBenchTarget: string;
}

interface TaskRecord {
  id: string;
  deviceId: string;
  deviceName: string;
  taskName: string;
  fenSnippet: string;
  depth: number;
  scoreCp: number;
  nodesAnalyzed: number;
  durationSec: number;
  nps: number;
  completedAt: string;
}

interface AnalyticsData {
  totalCompletedTasks: number;
  totalFleetUptimeHours: number;
  totalFleetUptimeDays: number;
  totalFleetNodesEvaluated: number;
  averageDeviceNps: number;
  peakFleetNps: number;
  deviceBreakdowns: Array<{
    deviceId: string;
    deviceName: string;
    uptimeHours: number;
    tasksCount: number;
    nodesEvaluated: number;
    currentNps: number;
    hardware: string;
    status: string;
  }>;
}

interface AuditLog {
  id: string;
  timestamp: string;
  action: string;
  actor: 'ADMIN' | 'MASTER' | 'DEVICE' | 'SYSTEM';
  target?: string;
  status: 'SUCCESS' | 'WARNING' | 'ERROR';
  details: string;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'fleet' | 'master' | 'tasks' | 'analytics' | 'simulator' | 'tokens' | 'audit' | 'usb'>('fleet');
  const [nodes, setNodes] = useState<Device[]>([]);
  const [stats, setStats] = useState<FleetStats | null>(null);
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  
  // Master Password Auth State
  const [isMasterAuthenticated, setIsMasterAuthenticated] = useState(false);
  const [masterPasswordInput, setMasterPasswordInput] = useState('');
  const [masterToken, setMasterToken] = useState<string | null>(localStorage.getItem('atomicdb_master_token'));
  const [masterAuthError, setMasterAuthError] = useState<string | null>(null);

  // Filters & State
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [taskDeviceFilter, setTaskDeviceFilter] = useState<string>('ALL');
  const [taskSearchQuery, setTaskSearchQuery] = useState('');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Command Modal State
  const [isCommandModalOpen, setIsCommandModalOpen] = useState(false);
  const [commandTarget, setCommandTarget] = useState<Device | null>(null);
  const [commandType, setCommandType] = useState<'PAUSE' | 'RESUME' | 'UPDATE_CONFIG' | 'REVOKE' | 'TERMINATE'>('UPDATE_CONFIG');
  const [configThreads, setConfigThreads] = useState(4);
  const [configHash, setConfigHash] = useState(1024);
  const [configJobs, setConfigJobs] = useState(1);
  const [configEngineUpdateMin, setConfigEngineUpdateMin] = useState(15.0);
  const [configEngine, setConfigEngine] = useState('');
  const [configSyzygy, setConfigSyzygy] = useState('');
  const [configNoFetchSyzygy, setConfigNoFetchSyzygy] = useState(true); // User requirement: always enabled by default
  const [configSolve, setConfigSolve] = useState(false);
  const [configNoAutoUpdate, setConfigNoAutoUpdate] = useState(false);
  const [configNoEngineUpdate, setConfigNoEngineUpdate] = useState(false);
  const [configOnce, setConfigOnce] = useState(false);
  const [configCpuMode, setConfigCpuMode] = useState<'Adaptive' | 'Maximum' | 'Balanced' | 'Custom'>('Adaptive');

  // Token Modal State
  const [isTokenModalOpen, setIsTokenModalOpen] = useState(false);
  const [tokenMaxThreads, setTokenMaxThreads] = useState<number>(8);
  const [tokenMaxHash, setTokenMaxHash] = useState<number>(2048);
  const [tokenTtlMinutes, setTokenTtlMinutes] = useState<number>(120);
  const [generatedToken, setGeneratedToken] = useState<string | null>(null);

  // Live Simulator Contributor API State (All 14 Upstream Variables)
  const [simServer, setSimServer] = useState('https://belzedar.duckdns.org');
  const [simUser, setSimUser] = useState('Void');
  const [simPass, setSimPass] = useState('Pineapple2357');
  const [simShowPass, setSimShowPass] = useState(false);
  const [simThreads, setSimThreads] = useState(4);
  const [simJobs, setSimJobs] = useState(1);
  const [simHash, setSimHash] = useState(1024);
  const [simEngine, setSimEngine] = useState('');
  const [simSyzygy, setSimSyzygy] = useState('');
  const [simNoFetchSyzygy, setSimNoFetchSyzygy] = useState(true); // User requirement: always enabled by default
  const [simSolve, setSimSolve] = useState(false);
  const [simNoAutoUpdate, setSimNoAutoUpdate] = useState(false);
  const [simNoEngineUpdate, setSimNoEngineUpdate] = useState(false);
  const [simEngineUpdateMin, setSimEngineUpdateMin] = useState(15.0);
  const [simOnce, setSimOnce] = useState(false);
  const [simCpuMode, setSimCpuMode] = useState<'Adaptive' | 'Maximum' | 'Balanced' | 'Custom'>('Adaptive');

  // Live Simulator State
  const [simCpuSpike, setSimCpuSpike] = useState(false);
  const [simLocalStop, setSimLocalStop] = useState(false);
  const [simConsoleLogs, setSimConsoleLogs] = useState<string[]>([
    '[INIT] Standalone --onefile AtomicDBPortable.exe runtime loaded.',
    '[PORTABLE ROOT] USB storage root detected (E:\\AtomicDB_USB). Host C: writes blocked.',
    '[SAFETY] Tablebase download disabled (--no-fetch-syzygy enabled by default). Zero C: drive trace.',
    '[WORKER] Spawning atomicdb_worker via internal --exec-worker dispatch...',
    '[ANALYSIS] Connected to https://belzedar.duckdns.org (Threads: 4, Hash: 1024MB)'
  ]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const fetchFleetData = async () => {
    try {
      const headers: Record<string, string> = {};
      if (masterToken) {
        headers['Authorization'] = `Bearer ${masterToken}`;
      }

      const [nodesRes, statsRes, tasksRes, analyticsRes, logsRes] = await Promise.all([
        fetch('/api/admin/nodes', { headers }),
        fetch('/api/admin/stats', { headers }),
        fetch('/api/admin/tasks?limit=150', { headers }),
        fetch('/api/admin/analytics', { headers }),
        fetch('/api/admin/audit-logs', { headers })
      ]);

      if (nodesRes.ok) setNodes(await nodesRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
      if (tasksRes.ok) {
        const data = await tasksRes.json();
        setTasks(data.tasks || []);
      }
      if (analyticsRes.ok) setAnalytics(await analyticsRes.json());
      if (logsRes.ok) setAuditLogs(await logsRes.json());
    } catch (err) {
      console.error('Data fetch error:', err);
    }
  };

  // Check Master Token Status on load
  useEffect(() => {
    if (masterToken) {
      fetch('/api/admin/auth-status', {
        headers: { Authorization: `Bearer ${masterToken}` }
      })
        .then(res => res.json())
        .then(data => {
          setIsMasterAuthenticated(!!data.isMaster);
          if (!data.isMaster) {
            localStorage.removeItem('atomicdb_master_token');
            setMasterToken(null);
          }
        })
        .catch(() => setIsMasterAuthenticated(false));
    }
  }, [masterToken]);

  useEffect(() => {
    fetchFleetData();
    const interval = setInterval(fetchFleetData, 3500);
    return () => clearInterval(interval);
  }, [masterToken]);

  const handleMasterLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setMasterAuthError(null);
    try {
      const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: masterPasswordInput })
      });

      if (res.ok) {
        const data = await res.json();
        setMasterToken(data.token);
        localStorage.setItem('atomicdb_master_token', data.token);
        setIsMasterAuthenticated(true);
        setMasterPasswordInput('');
        showToast('Master Control authenticated successfully');
        fetchFleetData();
      } else {
        const err = await res.json();
        setMasterAuthError(err.error || 'Incorrect Master Password');
      }
    } catch (err) {
      setMasterAuthError('Connection error contacting server');
    }
  };

  const handleMasterLogout = async () => {
    if (masterToken) {
      fetch('/api/admin/logout', {
        method: 'POST',
        headers: { Authorization: `Bearer ${masterToken}` }
      }).catch(console.error);
    }
    localStorage.removeItem('atomicdb_master_token');
    setMasterToken(null);
    setIsMasterAuthenticated(false);
    showToast('Master Control session locked');
  };

  const handleTerminateNode = async (nodeId: string, nodeName: string) => {
    if (!confirm(`CRITICAL WARNING: This will immediately TERMINATE the running executable on ${nodeName} from your server. Are you sure?`)) {
      return;
    }
    try {
      const res = await fetch('/api/admin/command', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(masterToken ? { Authorization: `Bearer ${masterToken}` } : {})
        },
        body: JSON.stringify({
          deviceId: nodeId,
          commandType: 'TERMINATE',
          payload: { reason: 'Master Remote Kill' }
        })
      });

      if (res.ok) {
        showToast(`Sent immediate TERMINATE signal to ${nodeName}. Process will exit.`);
        fetchFleetData();
      }
    } catch (err) {
      showToast('Failed to terminate device');
    }
  };

  const handleEmergencyFleetHalt = async () => {
    if (!confirm('DANGER: This will invoke the Emergency Kill Switch and TERMINATE ALL connected devices across the entire network. Confirm fleet shutdown?')) {
      return;
    }
    try {
      const res = await fetch('/api/admin/terminate-fleet', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${masterToken}`
        }
      });

      if (res.ok) {
        const data = await res.json();
        showToast(data.message || 'Emergency Fleet Kill Switch executed.');
        fetchFleetData();
      } else {
        const err = await res.json();
        showToast(`Error: ${err.error || 'Failed'}`);
      }
    } catch (err) {
      showToast('Network error during emergency kill switch');
    }
  };

  const handleSendCommand = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commandTarget) return;

    setIsLoading(true);
    try {
      const payload: Record<string, any> = {};
      if (commandType === 'UPDATE_CONFIG') {
        payload.threads = Number(configThreads);
        payload.hash = Number(configHash);
        payload.jobs = Number(configJobs);
        payload.cpuMode = configCpuMode;
        payload.engine = configEngine.trim();
        payload.syzygy = configSyzygy.trim();
        payload.noFetchSyzygy = Boolean(configNoFetchSyzygy);
        payload.solve = Boolean(configSolve);
        payload.noAutoUpdate = Boolean(configNoAutoUpdate);
        payload.noEngineUpdate = Boolean(configNoEngineUpdate);
        payload.engineUpdateMinutes = Number(configEngineUpdateMin);
        payload.once = Boolean(configOnce);
      }

      const res = await fetch('/api/admin/command', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(masterToken ? { Authorization: `Bearer ${masterToken}` } : {})
        },
        body: JSON.stringify({
          deviceId: commandTarget.id,
          commandType,
          payload
        })
      });

      if (res.ok) {
        showToast(`Dispatched ${commandType} to ${commandTarget.name}`);
        setIsCommandModalOpen(false);
        fetchFleetData();
      } else {
        const err = await res.json();
        showToast(`Error: ${err.error || 'Failed to dispatch'}`);
      }
    } catch (err) {
      showToast('Network error while dispatching command');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerateToken = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/admin/enroll-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          maxThreads: tokenMaxThreads,
          maxHashMb: tokenMaxHash,
          validityMinutes: tokenTtlMinutes
        })
      });

      if (res.ok) {
        const data = await res.json();
        setGeneratedToken(data.token);
        showToast('Issued signed single-use enrollment token');
        fetchFleetData();
      }
    } catch (err) {
      showToast('Failed to generate token');
    }
  };

  const handleSimulatorStep = async (spike: boolean, localStop: boolean) => {
    try {
      const res = await fetch('/api/simulator/simulate-step', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          deviceId: 'node-win11-ryzen9',
          cpuSpike: spike,
          triggerLocalStop: localStop,
          completeNewTask: true
        })
      });

      if (res.ok) {
        const data = await res.json();
        const updated = data.device;
        if (localStop) {
          setSimConsoleLogs(prev => [
            `[${new Date().toLocaleTimeString()}] [LOCAL STOP] Operator engaged Local Stop. Process ceased.`,
            `[${new Date().toLocaleTimeString()}] [OVERRIDE] Remote RESUME commands strictly locked out.`,
            ...prev.slice(0, 8)
          ]);
        } else if (spike) {
          setSimConsoleLogs(prev => [
            `[${new Date().toLocaleTimeString()}] [ADAPTIVE] Host CPU utilization reached 92%!`,
            `[${new Date().toLocaleTimeString()}] [THROTTLE] Scaled threads down to ${updated.metrics.threadsAllocated} to save host responsiveness.`,
            ...prev.slice(0, 8)
          ]);
        } else {
          setSimConsoleLogs(prev => [
            `[${new Date().toLocaleTimeString()}] [COMPLETED] Finished analysis depth 26. Uploaded position score to Belzedar server.`,
            `[${new Date().toLocaleTimeString()}] [SPEED] Effective speed: ${(updated.metrics.taskSpeedNps / 1000000).toFixed(1)} MNPS (Total Tasks: ${data.totalTasks})`,
            ...prev.slice(0, 8)
          ]);
        }
        fetchFleetData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const filteredNodes = useMemo(() => {
    return nodes.filter(n => {
      const matchesSearch = n.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        n.hardware.cpuModel.toLowerCase().includes(searchQuery.toLowerCase()) ||
        n.id.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesStatus = statusFilter === 'ALL' || n.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [nodes, searchQuery, statusFilter]);

  const filteredTasks = useMemo(() => {
    return tasks.filter(t => {
      const matchesDevice = taskDeviceFilter === 'ALL' || t.deviceId === taskDeviceFilter;
      const matchesSearch = !taskSearchQuery ||
        t.taskName.toLowerCase().includes(taskSearchQuery.toLowerCase()) ||
        t.fenSnippet.toLowerCase().includes(taskSearchQuery.toLowerCase()) ||
        t.deviceName.toLowerCase().includes(taskSearchQuery.toLowerCase());
      return matchesDevice && matchesSearch;
    });
  }, [tasks, taskDeviceFilter, taskSearchQuery]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500/30 selection:text-cyan-200">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-slate-900 border border-cyan-500/50 text-cyan-200 px-4 py-3 rounded-lg shadow-xl text-sm font-medium flex items-center gap-2 animate-bounce">
          <CheckCircle2 className="w-4 h-4 text-cyan-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Bar Contract (Brand Title — Nav Links — Primary Action) */}
      <header className="flex items-center justify-between gap-8 px-6 py-4 border-b border-slate-800 bg-slate-900/90 backdrop-blur shrink-0">
        <div className="flex items-center gap-3 whitespace-nowrap shrink-0">
          <div className="w-8 h-8 rounded bg-gradient-to-tr from-cyan-600 to-blue-500 flex items-center justify-center font-bold text-white shadow-md">
            <Cpu className="w-5 h-5 text-white" />
          </div>
          <span className="text-lg font-bold tracking-tight text-white whitespace-nowrap">
            AtomicDB Fleet Console
          </span>
          {isMasterAuthenticated && (
            <span className="text-xs text-amber-400 font-mono flex items-center gap-1 bg-amber-950/60 border border-amber-500/40 px-2 py-0.5 rounded">
              <Shield className="w-3 h-3 text-amber-400" />
              <span>MASTER CONTROL</span>
            </span>
          )}
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-slate-400">
          <button
            onClick={() => setActiveTab('fleet')}
            className={`transition-colors whitespace-nowrap shrink-0 pb-0.5 ${
              activeTab === 'fleet' ? 'text-cyan-400 border-b-2 border-cyan-400' : 'hover:text-slate-200'
            }`}
          >
            Compute Fleet
          </button>
          <button
            onClick={() => setActiveTab('master')}
            className={`transition-colors whitespace-nowrap shrink-0 pb-0.5 flex items-center gap-1.5 ${
              activeTab === 'master' ? 'text-amber-400 border-b-2 border-amber-400' : 'hover:text-slate-200'
            }`}
          >
            {isMasterAuthenticated ? <Unlock className="w-3.5 h-3.5 text-amber-400" /> : <Lock className="w-3.5 h-3.5" />}
            <span>Master Control</span>
          </button>
          <button
            onClick={() => setActiveTab('tasks')}
            className={`transition-colors whitespace-nowrap shrink-0 pb-0.5 ${
              activeTab === 'tasks' ? 'text-cyan-400 border-b-2 border-cyan-400' : 'hover:text-slate-200'
            }`}
          >
            Task Ledger ({tasks.length})
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`transition-colors whitespace-nowrap shrink-0 pb-0.5 ${
              activeTab === 'analytics' ? 'text-cyan-400 border-b-2 border-cyan-400' : 'hover:text-slate-200'
            }`}
          >
            Analytics &amp; Intelligence
          </button>
          <button
            onClick={() => setActiveTab('simulator')}
            className={`transition-colors whitespace-nowrap shrink-0 pb-0.5 ${
              activeTab === 'simulator' ? 'text-cyan-400 border-b-2 border-cyan-400' : 'hover:text-slate-200'
            }`}
          >
            Client Simulator
          </button>
          <button
            onClick={() => setActiveTab('usb')}
            className={`transition-colors whitespace-nowrap shrink-0 pb-0.5 ${
              activeTab === 'usb' ? 'text-cyan-400 border-b-2 border-cyan-400' : 'hover:text-slate-200'
            }`}
          >
            --onefile .EXE &amp; USB
          </button>
          <button
            onClick={() => setActiveTab('audit')}
            className={`transition-colors whitespace-nowrap shrink-0 pb-0.5 ${
              activeTab === 'audit' ? 'text-cyan-400 border-b-2 border-cyan-400' : 'hover:text-slate-200'
            }`}
          >
            Audit Log
          </button>
        </nav>

        {/* Primary Action Zone */}
        <div className="flex items-center gap-3 shrink-0">
          {isMasterAuthenticated ? (
            <button
              onClick={handleMasterLogout}
              className="px-3.5 py-1.5 text-xs font-semibold text-slate-300 bg-slate-800 rounded-lg hover:bg-slate-700 transition-colors whitespace-nowrap shrink-0 flex items-center gap-1.5"
            >
              <Lock className="w-3 h-3 text-slate-400" />
              <span>Lock Master</span>
            </button>
          ) : (
            <button
              onClick={() => setActiveTab('master')}
              className="px-3.5 py-1.5 text-xs font-semibold text-amber-300 bg-amber-950/70 border border-amber-500/40 rounded-lg hover:bg-amber-900/50 transition-colors whitespace-nowrap shrink-0 flex items-center gap-1.5"
            >
              <Key className="w-3 h-3" />
              <span>Unlock Master</span>
            </button>
          )}

          <button
            onClick={() => {
              setGeneratedToken(null);
              setIsTokenModalOpen(true);
            }}
            className="px-4 py-2 text-xs font-semibold text-white bg-cyan-600 rounded-lg hover:bg-cyan-500 transition-colors whitespace-nowrap shrink-0 flex items-center gap-2 shadow-sm"
          >
            <Key className="w-3.5 h-3.5" />
            <span>Generate Token</span>
          </button>
        </div>
      </header>

      {/* Main Workspace Body */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        {/* KPI Strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
            <div className="text-xs font-medium text-slate-400">Total Enrolled Nodes</div>
            <div className="text-2xl font-bold text-white mt-1 font-mono tabular-nums">
              {stats?.totalDevices ?? nodes.length}
            </div>
            <div className="text-xs text-slate-500 mt-1">
              <span>{stats?.activeNodes ?? 0} active</span>
              <span aria-hidden="true" className="mx-1">·</span>
              <span>{stats?.terminatedNodes ?? 0} terminated</span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
            <div className="text-xs font-medium text-slate-400">Aggregate Fleet Speed</div>
            <div className="text-2xl font-bold text-cyan-400 mt-1 font-mono tabular-nums">
              {((stats?.aggregateNps ?? 0) / 1000000).toFixed(1)} <span className="text-sm font-normal text-slate-400">MNPS</span>
            </div>
            <div className="text-xs text-slate-500 mt-1">
              <span>{stats?.activeThreads ?? 0} total active threads</span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
            <div className="text-xs font-medium text-slate-400">Cumulative Completed Tasks</div>
            <div className="text-2xl font-bold text-emerald-400 mt-1 font-mono tabular-nums">
              {stats?.totalTasksCompleted ?? tasks.length} <span className="text-sm font-normal text-slate-400">tasks</span>
            </div>
            <div className="text-xs text-slate-500 mt-1">
              <span>Categorised across all devices</span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
            <div className="text-xs font-medium text-slate-400">Total Network Uptime</div>
            <div className="text-2xl font-bold text-blue-400 mt-1 font-mono tabular-nums">
              {analytics?.totalFleetUptimeDays ?? 12.4} <span className="text-sm font-normal text-slate-400">days</span>
            </div>
            <div className="text-xs text-slate-500 mt-1">
              <span>{analytics?.totalFleetUptimeHours ?? 298} cumulative compute hours</span>
            </div>
          </div>
        </div>

        {/* TAB 1: FLEET MANAGEMENT VIEW */}
        {activeTab === 'fleet' && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-900 p-3 rounded-xl border border-slate-800">
              <div className="relative w-full sm:w-80">
                <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Filter by node name or CPU..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="flex items-center gap-1 p-1 bg-slate-950 rounded-lg border border-slate-800 overflow-x-auto w-full sm:w-auto">
                {['ALL', 'ACTIVE', 'THROTTLED', 'PAUSED', 'LOCAL_STOP', 'TERMINATED', 'OFFLINE'].map((status) => (
                  <button
                    key={status}
                    onClick={() => setStatusFilter(status)}
                    className={`px-3 py-1 text-xs font-medium rounded transition-colors whitespace-nowrap ${
                      statusFilter === status
                        ? 'bg-slate-800 text-cyan-300 shadow-sm'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {status === 'ALL' ? 'All Nodes' : status}
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950/70 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4">Device / IP Address</th>
                      <th className="py-3 px-4">Status &amp; Architecture</th>
                      <th className="py-3 px-4 text-right">Host CPU / Worker</th>
                      <th className="py-3 px-4 text-right">Threads / Hash</th>
                      <th className="py-3 px-4">Active Position</th>
                      <th className="py-3 px-4 text-right">Uptime / Tasks</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono tabular-nums">
                    {filteredNodes.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="text-center py-8 text-slate-500 font-sans">
                          No matching distributed computing nodes found.
                        </td>
                      </tr>
                    ) : (
                      filteredNodes.map((node) => (
                        <tr key={node.id} className="hover:bg-slate-800/40 transition-colors">
                          <td className="py-3 px-4">
                            <div className="font-semibold text-slate-200 font-sans flex items-center gap-1.5">
                              <span>{node.name}</span>
                              {node.ipAddress && (
                                <span className="text-[10px] text-slate-500 font-mono">({node.ipAddress})</span>
                              )}
                            </div>
                            <div className="text-[11px] text-slate-500 truncate max-w-xs font-sans">
                              {node.hardware.cpuModel}
                            </div>
                          </td>

                          <td className="py-3 px-4 font-sans text-xs">
                            <div className="flex items-center gap-1.5">
                              {node.status === 'ACTIVE' && <span className="text-emerald-400 font-semibold">Active Compute</span>}
                              {node.status === 'THROTTLED' && <span className="text-amber-400 font-semibold">Adaptive Throttle</span>}
                              {node.status === 'PAUSED' && <span className="text-slate-400">Admin Paused</span>}
                              {node.status === 'LOCAL_STOP' && <span className="text-rose-400 font-bold">Local Stop Override</span>}
                              {node.status === 'TERMINATED' && <span className="text-red-500 font-bold">Terminated by Master</span>}
                              {node.status === 'OFFLINE' && <span className="text-slate-500">Offline</span>}
                            </div>
                            <div className="text-[11px] text-slate-500">
                              <span>Mode: {node.cpuMode}</span>
                              <span aria-hidden="true"> · </span>
                              <span>{node.hardware.instructions.join(', ')}</span>
                            </div>
                          </td>

                          <td className="py-3 px-4 text-right">
                            <div className="text-slate-200">{node.metrics.systemCpuPct}% sys</div>
                            <div className="text-[11px] text-cyan-400">{node.metrics.workerCpuPct}% worker</div>
                          </td>

                          <td className="py-3 px-4 text-right">
                            <div className="text-slate-200">{node.metrics.threadsAllocated} threads</div>
                            <div className="text-[11px] text-slate-400">{node.metrics.hashAllocatedMb} MB hash</div>
                          </td>

                          <td className="py-3 px-4 font-sans text-xs max-w-xs">
                            {node.currentTask ? (
                              <div>
                                <div className="text-slate-300 font-medium truncate">{node.currentTask.taskName}</div>
                                <div className="text-[11px] text-slate-500 font-mono truncate">
                                  D{node.currentTask.depth} · {(node.metrics.taskSpeedNps / 1000000).toFixed(1)} MNPS
                                </div>
                              </div>
                            ) : (
                              <span className="text-slate-500 italic">Queue idle</span>
                            )}
                          </td>

                          <td className="py-3 px-4 text-right font-mono text-xs">
                            <div className="text-slate-300">{(node.uptimeSeconds / 3600).toFixed(1)}h</div>
                            <div className="text-[11px] text-emerald-400">{node.totalTasksCompleted} completed</div>
                          </td>

                          <td className="py-3 px-4 text-right font-sans">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => {
                                  setCommandTarget(node);
                                  setCommandType('UPDATE_CONFIG');
                                  setConfigThreads(node.metrics.threadsAllocated);
                                  setConfigHash(node.metrics.hashAllocatedMb);
                                  setConfigCpuMode(node.cpuMode);
                                  setIsCommandModalOpen(true);
                                }}
                                className="p-1.5 text-slate-400 hover:text-cyan-300 rounded hover:bg-slate-800 transition-colors"
                                title="Configure Limits"
                              >
                                <Sliders className="w-4 h-4" />
                              </button>

                              {node.status === 'ACTIVE' || node.status === 'THROTTLED' ? (
                                <button
                                  onClick={async () => {
                                    await fetch('/api/admin/command', {
                                      method: 'POST',
                                      headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({ deviceId: node.id, commandType: 'PAUSE' })
                                    });
                                    showToast(`Dispatched PAUSE to ${node.name}`);
                                    fetchFleetData();
                                  }}
                                  className="p-1.5 text-amber-400 hover:text-amber-300 rounded hover:bg-slate-800 transition-colors"
                                  title="Remote Pause"
                                >
                                  <Pause className="w-4 h-4" />
                                </button>
                              ) : (
                                <button
                                  onClick={async () => {
                                    await fetch('/api/admin/command', {
                                      method: 'POST',
                                      headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({ deviceId: node.id, commandType: 'RESUME' })
                                    });
                                    showToast(`Dispatched RESUME to ${node.name}`);
                                    fetchFleetData();
                                  }}
                                  className="p-1.5 text-emerald-400 hover:text-emerald-300 rounded hover:bg-slate-800 transition-colors"
                                  title="Remote Resume"
                                >
                                  <Play className="w-4 h-4" />
                                </button>
                              )}

                              {/* Master Remote Terminate Kill Action */}
                              <button
                                onClick={() => handleTerminateNode(node.id, node.name)}
                                className="p-1.5 text-red-400 hover:text-red-300 rounded hover:bg-red-950/50 transition-colors"
                                title="Terminate Exe from Server"
                              >
                                <XCircle className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: MASTER CONTROL PORTAL (PASSWORD PROTECTED) */}
        {activeTab === 'master' && (
          <div className="space-y-6 max-w-5xl">
            {!isMasterAuthenticated ? (
              <div className="p-8 rounded-xl bg-slate-900 border border-amber-500/30 max-w-md mx-auto space-y-4 shadow-xl">
                <div className="w-10 h-10 rounded-lg bg-amber-950/60 border border-amber-500/40 flex items-center justify-center text-amber-400 mx-auto">
                  <Lock className="w-5 h-5" />
                </div>
                <div className="text-center">
                  <h3 className="text-base font-bold text-white">Master Control Access</h3>
                  <p className="text-xs text-slate-400 mt-1">
                    Enter the Master Administrator Password to access global fleet commands and remote termination capabilities.
                  </p>
                </div>

                <form onSubmit={handleMasterLogin} className="space-y-4 pt-2">
                  <div>
                    <input
                      type="password"
                      placeholder="Master Password..."
                      value={masterPasswordInput}
                      onChange={(e) => setMasterPasswordInput(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-500"
                    />
                    {masterAuthError && (
                      <div className="text-xs text-rose-400 mt-1.5">{masterAuthError}</div>
                    )}
                  </div>

                  <button
                    type="submit"
                    className="w-full py-2 bg-amber-600 hover:bg-amber-500 text-slate-950 font-bold rounded-lg text-xs transition-colors flex items-center justify-center gap-2"
                  >
                    <Unlock className="w-3.5 h-3.5" />
                    <span>Unlock Master Control</span>
                  </button>
                </form>

                <div className="text-[11px] text-slate-500 text-center font-mono">
                  Default Master Password: <span className="text-amber-400 font-bold">Pineapple2357</span> (Caesar Obfuscated: <code className="text-slate-400">Wpulhwwsl9:&lt;&gt;</code>)
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="p-6 rounded-xl bg-slate-900 border border-amber-500/40 space-y-4 shadow-lg">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-amber-950/80 border border-amber-500/60 flex items-center justify-center text-amber-400">
                        <Shield className="w-6 h-6" />
                      </div>
                      <div>
                        <h3 className="text-base font-bold text-white">Master Remote Control Active</h3>
                        <p className="text-xs text-slate-400">
                          Direct control over every device connected to the internet running this .exe file.
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <button
                        onClick={handleEmergencyFleetHalt}
                        className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-bold transition-colors flex items-center gap-2 shadow-md"
                      >
                        <XCircle className="w-4 h-4" />
                        <span>Emergency Fleet Kill Switch</span>
                      </button>
                      <button
                        onClick={handleMasterLogout}
                        className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold"
                      >
                        Lock Portal
                      </button>
                    </div>
                  </div>
                </div>

                {/* Connected Devices Grid with Instant Kill Options */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-white">Connected Devices Under Master Control</h4>
                    <span className="text-xs text-slate-400 font-mono">{nodes.length} online devices</span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {nodes.map(node => (
                      <div key={node.id} className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="font-bold text-sm text-white truncate">{node.name}</div>
                          <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                            node.status === 'ACTIVE' ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/30' :
                            node.status === 'TERMINATED' ? 'bg-red-950 text-red-400 border border-red-500/30' :
                            'bg-slate-800 text-slate-300'
                          }`}>
                            {node.status}
                          </span>
                        </div>

                        <div className="text-xs text-slate-400 space-y-1 font-mono">
                          <div className="flex justify-between">
                            <span>IP Address:</span>
                            <span className="text-slate-200">{node.ipAddress || '127.0.0.1'}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Speed (NPS):</span>
                            <span className="text-cyan-400">{(node.metrics.taskSpeedNps / 1000000).toFixed(1)}M</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Uptime:</span>
                            <span className="text-slate-200">{(node.uptimeSeconds / 3600).toFixed(1)} hrs</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Tasks Completed:</span>
                            <span className="text-emerald-400">{node.totalTasksCompleted}</span>
                          </div>
                        </div>

                        <div className="border-t border-slate-800 pt-2 flex items-center justify-between">
                          <button
                            onClick={() => {
                              setCommandTarget(node);
                              setCommandType('UPDATE_CONFIG');
                              setConfigThreads(node.metrics.threadsAllocated);
                              setConfigHash(node.metrics.hashAllocatedMb);
                              setConfigCpuMode(node.cpuMode);
                              setIsCommandModalOpen(true);
                            }}
                            className="px-2.5 py-1 text-xs text-slate-300 bg-slate-800 hover:bg-slate-700 rounded transition-colors"
                          >
                            Configure
                          </button>

                          <button
                            onClick={() => handleTerminateNode(node.id, node.name)}
                            className="px-3 py-1 text-xs font-bold text-white bg-red-600 hover:bg-red-500 rounded transition-colors flex items-center gap-1.5 shadow-sm"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                            <span>Terminate Exe</span>
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: HISTORICAL TASK LEDGER (CATEGORISED BY DEVICE) */}
        {activeTab === 'tasks' && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-900 p-4 rounded-xl border border-slate-800">
              <div className="flex items-center gap-3 w-full sm:w-auto">
                <div className="text-xs font-semibold text-slate-400">Device Category:</div>
                <select
                  value={taskDeviceFilter}
                  onChange={(e) => setTaskDeviceFilter(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200"
                >
                  <option value="ALL">All Enrolled Devices ({tasks.length} tasks)</option>
                  {nodes.map(n => (
                    <option key={n.id} value={n.id}>{n.name}</option>
                  ))}
                </select>
              </div>

              <div className="relative w-full sm:w-80">
                <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Search opening, FEN, or task ID..."
                  value={taskSearchQuery}
                  onChange={(e) => setTaskSearchQuery(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono tabular-nums">
                  <thead className="bg-slate-950/70 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider font-sans">
                    <tr>
                      <th className="py-3 px-4">Task ID</th>
                      <th className="py-3 px-4">Device (Origin)</th>
                      <th className="py-3 px-4">Opening &amp; Position (FEN)</th>
                      <th className="py-3 px-4 text-right">Depth</th>
                      <th className="py-3 px-4 text-right">Score</th>
                      <th className="py-3 px-4 text-right">Nodes Evaluated</th>
                      <th className="py-3 px-4 text-right">Effective NPS</th>
                      <th className="py-3 px-4 text-right">Completed</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {filteredTasks.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="text-center py-8 text-slate-500 font-sans">
                          No completed analysis tasks found for the selected filter.
                        </td>
                      </tr>
                    ) : (
                      filteredTasks.map(t => (
                        <tr key={t.id} className="hover:bg-slate-800/40 transition-colors">
                          <td className="py-3 px-4 text-slate-400">{t.id}</td>
                          <td className="py-3 px-4 font-sans font-semibold text-slate-200">{t.deviceName}</td>
                          <td className="py-3 px-4 max-w-sm font-sans">
                            <div className="text-slate-200 font-medium truncate">{t.taskName}</div>
                            <div className="text-[11px] text-slate-500 font-mono truncate">{t.fenSnippet}</div>
                          </td>
                          <td className="py-3 px-4 text-right text-cyan-400">D{t.depth}</td>
                          <td className="py-3 px-4 text-right text-slate-200">{t.scoreCp > 0 ? `+${t.scoreCp}` : t.scoreCp} cp</td>
                          <td className="py-3 px-4 text-right text-slate-300">{(t.nodesAnalyzed / 1000000).toFixed(1)}M</td>
                          <td className="py-3 px-4 text-right text-emerald-400">{(t.nps / 1000000).toFixed(1)} MNPS</td>
                          <td className="py-3 px-4 text-right text-slate-400 text-xs">
                            {new Date(t.completedAt).toLocaleTimeString()}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: COMPILED ANALYTICS & INTELLIGENCE */}
        {activeTab === 'analytics' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                  <Zap className="w-4 h-4 text-cyan-400" />
                  <span>Network Chess Speed (Nodes / Sec)</span>
                </div>
                <div className="text-3xl font-bold text-white font-mono">
                  {((stats?.aggregateNps ?? 0) / 1000000).toFixed(1)} <span className="text-base font-normal text-slate-400">MNPS</span>
                </div>
                <p className="text-xs text-slate-500">
                  Peak Fleet Speed Recorded: {((analytics?.peakFleetNps ?? 28520000) / 1000000).toFixed(1)} MNPS
                </p>
              </div>

              <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                  <ListOrdered className="w-4 h-4 text-emerald-400" />
                  <span>Total Tasks Completed</span>
                </div>
                <div className="text-3xl font-bold text-emerald-400 font-mono">
                  {analytics?.totalCompletedTasks ?? tasks.length}
                </div>
                <p className="text-xs text-slate-500">
                  Total Evaluated Positions: {((analytics?.totalFleetNodesEvaluated ?? 30990000000) / 1000000000).toFixed(2)} Billion nodes
                </p>
              </div>

              <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                  <Clock className="w-4 h-4 text-blue-400" />
                  <span>Total Compute Uptime</span>
                </div>
                <div className="text-3xl font-bold text-blue-400 font-mono">
                  {analytics?.totalFleetUptimeHours ?? 298.5} <span className="text-base font-normal text-slate-400">hours</span>
                </div>
                <p className="text-xs text-slate-500">
                  Equivalent to {analytics?.totalFleetUptimeDays ?? 12.4} days of continuous Stockfish analysis
                </p>
              </div>
            </div>

            {/* Hardware Contribution Leaderboard */}
            <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-bold text-white">Device Contribution Breakdown &amp; Performance</h4>
                  <p className="text-xs text-slate-400">Analysis output categorized by physical host hardware</p>
                </div>
                <span className="text-xs text-cyan-400 font-mono">Live Sync</span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono tabular-nums">
                  <thead className="border-b border-slate-800 text-slate-400 font-sans font-semibold">
                    <tr>
                      <th className="py-2.5 px-3">Device Name</th>
                      <th className="py-2.5 px-3">Hardware Specs</th>
                      <th className="py-2.5 px-3 text-right">Uptime</th>
                      <th className="py-2.5 px-3 text-right">Tasks Done</th>
                      <th className="py-2.5 px-3 text-right">Total Nodes</th>
                      <th className="py-2.5 px-3 text-right">Current NPS</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {(analytics?.deviceBreakdowns ?? []).map(d => (
                      <tr key={d.deviceId} className="hover:bg-slate-800/40">
                        <td className="py-3 px-3 font-sans font-bold text-slate-200">{d.deviceName}</td>
                        <td className="py-3 px-3 font-sans text-slate-400 truncate max-w-xs">{d.hardware}</td>
                        <td className="py-3 px-3 text-right text-slate-300">{d.uptimeHours} hrs</td>
                        <td className="py-3 px-3 text-right text-emerald-400 font-bold">{d.tasksCount}</td>
                        <td className="py-3 px-3 text-right text-slate-300">{(d.nodesEvaluated / 1000000000).toFixed(2)}B</td>
                        <td className="py-3 px-3 text-right text-cyan-400">{(d.currentNps / 1000000).toFixed(1)} MNPS</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: CLIENT SIMULATOR */}
        {activeTab === 'simulator' && (
          <div className="space-y-6">
            {/* Top Config Card with All 14 OpenBench Contributor Variables */}
            <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-5 shadow-lg">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-cyan-950/70 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
                    <Usb className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <span>OpenBench Contributor API Configuration &amp; Simulator</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-500/30">
                        Zero C: Trace Protected
                      </span>
                    </h3>
                    <p className="text-xs text-slate-400">
                      Input boxes, numeric spinners, and checkboxes for all 14 official upstream variables. All operations run USB-isolated.
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => {
                    setSimConsoleLogs(prev => [
                      `[${new Date().toLocaleTimeString()}] [SUPERVISOR] Starting official worker: python atomicdb_worker.py -U ${simUser} -P ******** -S ${simServer} -T ${simThreads} --hash ${simHash}${simJobs > 1 ? ` --jobs ${simJobs}` : ''}${simEngine ? ` --engine "${simEngine}"` : ''}${simSyzygy ? ` --syzygy "${simSyzygy}"` : ''}${simNoFetchSyzygy ? ' --no-fetch-syzygy' : ''}${simSolve ? ' --solve' : ''}${simNoAutoUpdate ? ' --no-auto-update' : ''}${simNoEngineUpdate ? ' --no-engine-update' : ''}${simEngineUpdateMin !== 15 ? ` --engine-update-minutes ${simEngineUpdateMin}` : ''}${simOnce ? ' --once' : ''}`,
                      `[${new Date().toLocaleTimeString()}] [SUPERVISOR] Worker process spawned with PID ${Math.floor(Math.random() * 20000 + 10000)}`,
                      simNoFetchSyzygy
                        ? `[${new Date().toLocaleTimeString()}] syzygy: download disabled (--no-fetch-syzygy); zero trace on C: drive.`
                        : `[${new Date().toLocaleTimeString()}] syzygy: verified in USB storage root E:\\AtomicDB_USB\\syzygy-345.`,
                      `[${new Date().toLocaleTimeString()}] [CONNECT] Authenticating user "${simUser}" with OpenBench server ${simServer}...`,
                      `[${new Date().toLocaleTimeString()}] [CAPACITY] Allocated ${simThreads} threads (${simJobs} job slots), ${simHash} MB hash memory.`,
                      ...prev.slice(0, 10)
                    ]);
                    showToast('Applied configuration to virtual worker');
                  }}
                  className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow transition-colors shrink-0"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Apply Variables &amp; Respawn Worker</span>
                </button>
              </div>

              {/* Grid 1: Text Inputs (Credentials, Server, Engine, Syzygy) */}
              <div className="space-y-2">
                <div className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  1. Connection &amp; Path Inputs (Text Strings)
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Server URL (-S / --server)
                    </label>
                    <input
                      type="text"
                      value={simServer}
                      onChange={(e) => setSimServer(e.target.value)}
                      placeholder="https://belzedar.duckdns.org"
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-white font-mono focus:border-cyan-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Username (-U / --user)
                    </label>
                    <input
                      type="text"
                      value={simUser}
                      onChange={(e) => setSimUser(e.target.value)}
                      placeholder="OpenBench account username"
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-white font-mono focus:border-cyan-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-[11px] font-medium text-slate-400">
                        Password (-P / --password)
                      </label>
                      <button
                        type="button"
                        onClick={() => setSimShowPass(!simShowPass)}
                        className="text-[10px] text-cyan-400 hover:underline"
                      >
                        {simShowPass ? 'Mask' : 'Show'}
                      </button>
                    </div>
                    <input
                      type={simShowPass ? 'text' : 'password'}
                      value={simPass}
                      onChange={(e) => setSimPass(e.target.value)}
                      placeholder="OpenBench password"
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-white font-mono focus:border-cyan-500 focus:outline-none"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Custom Engine Path (--engine)
                    </label>
                    <input
                      type="text"
                      value={simEngine}
                      onChange={(e) => setSimEngine(e.target.value)}
                      placeholder="e.g. E:\AtomicDB_USB\Engines\stockfish.exe (blank uses default)"
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-white font-mono focus:border-cyan-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Syzygy Tablebase Directories (--syzygy)
                    </label>
                    <input
                      type="text"
                      value={simSyzygy}
                      onChange={(e) => setSimSyzygy(e.target.value)}
                      placeholder="Paths separated by ; (e.g. E:\AtomicDB_USB\syzygy-345)"
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-white font-mono focus:border-cyan-500 focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              {/* Grid 2: Numeric Controls (Threads, Jobs, Hash, Update Interval) */}
              <div className="space-y-2 pt-1 border-t border-slate-800/80">
                <div className="text-xs font-bold text-slate-300 uppercase tracking-wider pt-2">
                  2. Resource Allocation Spinners &amp; Intervals (Numbers)
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      CPU Mode
                    </label>
                    <select
                      value={simCpuMode}
                      onChange={(e) => setSimCpuMode(e.target.value as any)}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                    >
                      <option value="Adaptive">Adaptive (Default)</option>
                      <option value="Balanced">Balanced</option>
                      <option value="Maximum">Maximum</option>
                      <option value="Custom">Custom</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Threads (-T)
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="64"
                      value={simThreads}
                      onChange={(e) => setSimThreads(Math.max(1, Number(e.target.value)))}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Jobs (--jobs)
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="32"
                      value={simJobs}
                      onChange={(e) => setSimJobs(Math.max(1, Number(e.target.value)))}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Hash (--hash MB)
                    </label>
                    <input
                      type="number"
                      min="64"
                      max="65536"
                      step="128"
                      value={simHash}
                      onChange={(e) => setSimHash(Math.max(64, Number(e.target.value)))}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Engine Check Min
                    </label>
                    <input
                      type="number"
                      min="0.5"
                      max="1440"
                      step="1"
                      value={simEngineUpdateMin}
                      onChange={(e) => setSimEngineUpdateMin(Math.max(0.5, Number(e.target.value)))}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-white font-mono"
                    />
                  </div>
                </div>
              </div>

              {/* Grid 3: Checkboxes (All Boolean API Flags) */}
              <div className="space-y-2 pt-1 border-t border-slate-800/80">
                <div className="text-xs font-bold text-slate-300 uppercase tracking-wider pt-2">
                  3. OpenBench Feature Flags &amp; Toggles (Checkboxes)
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  <label className="flex items-start gap-2 p-2.5 rounded-lg bg-slate-950/80 border border-emerald-500/40 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={simNoFetchSyzygy}
                      onChange={(e) => setSimNoFetchSyzygy(e.target.checked)}
                      className="mt-0.5 rounded border-slate-700 text-cyan-500 focus:ring-0"
                    />
                    <div>
                      <div className="text-xs font-semibold text-emerald-300">
                        No Tablebase (--no-fetch-syzygy)
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Always enabled by default. Prevents downloading 1.3 GB tablebases to host C: drive.
                      </div>
                    </div>
                  </label>

                  <label className="flex items-start gap-2 p-2.5 rounded-lg bg-slate-950 border border-slate-800 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={simSolve}
                      onChange={(e) => setSimSolve(e.target.checked)}
                      className="mt-0.5 rounded border-slate-700 text-cyan-500 focus:ring-0"
                    />
                    <div>
                      <div className="text-xs font-semibold text-slate-200">
                        Solve Tasks (--solve)
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Also serve exhaustive proof solve tasks besides position analysis.
                      </div>
                    </div>
                  </label>

                  <label className="flex items-start gap-2 p-2.5 rounded-lg bg-slate-950 border border-slate-800 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={simNoAutoUpdate}
                      onChange={(e) => setSimNoAutoUpdate(e.target.checked)}
                      className="mt-0.5 rounded border-slate-700 text-cyan-500 focus:ring-0"
                    />
                    <div>
                      <div className="text-xs font-semibold text-slate-200">
                        No Auto-Update Worker (--no-auto-update)
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Do not auto-update worker script from official server.
                      </div>
                    </div>
                  </label>

                  <label className="flex items-start gap-2 p-2.5 rounded-lg bg-slate-950 border border-slate-800 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={simNoEngineUpdate}
                      onChange={(e) => setSimNoEngineUpdate(e.target.checked)}
                      className="mt-0.5 rounded border-slate-700 text-cyan-500 focus:ring-0"
                    />
                    <div>
                      <div className="text-xs font-semibold text-slate-200">
                        No Engine Update (--no-engine-update)
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Do not switch engine binary while analysis is currently active.
                      </div>
                    </div>
                  </label>

                  <label className="flex items-start gap-2 p-2.5 rounded-lg bg-slate-950 border border-slate-800 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={simOnce}
                      onChange={(e) => setSimOnce(e.target.checked)}
                      className="mt-0.5 rounded border-slate-700 text-cyan-500 focus:ring-0"
                    />
                    <div>
                      <div className="text-xs font-semibold text-slate-200">
                        Run Once (--once)
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Execute a single smoke analysis task and exit cleanly.
                      </div>
                    </div>
                  </label>
                </div>
              </div>

              {/* Live Generated Command Display */}
              <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 space-y-1">
                <div className="text-[11px] font-semibold text-slate-400">
                  Exact Upstream Invocation Command Line:
                </div>
                <div className="font-mono text-xs text-cyan-300 break-all select-all">
                  python atomicdb_worker.py -U {simUser || 'USER'} -P ******** -S {simServer} -T {simThreads} --hash {simHash}
                  {simJobs > 1 ? ` --jobs ${simJobs}` : ''}
                  {simEngine ? ` --engine "${simEngine}"` : ''}
                  {simSyzygy ? ` --syzygy "${simSyzygy}"` : ''}
                  {simNoFetchSyzygy ? ' --no-fetch-syzygy' : ''}
                  {simSolve ? ' --solve' : ''}
                  {simNoAutoUpdate ? ' --no-auto-update' : ''}
                  {simNoEngineUpdate ? ' --no-engine-update' : ''}
                  {simEngineUpdateMin !== 15 ? ` --engine-update-minutes ${simEngineUpdateMin}` : ''}
                  {simOnce ? ' --once' : ''}
                </div>
              </div>
            </div>

            {/* Bottom Row: Runtime Controls & STDOUT Stream */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-1 space-y-4">
                <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4 shadow-sm">
                  <div className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                    Runtime Simulation Controls
                  </div>

                  <div className="space-y-3">
                    <button
                      onClick={() => handleSimulatorStep(false, false)}
                      className="w-full px-3 py-2.5 text-xs font-semibold rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white transition-colors flex items-center justify-center gap-2 shadow"
                    >
                      <Play className="w-3.5 h-3.5" />
                      <span>Complete Analysis Task &amp; Submit Score</span>
                    </button>

                    <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950 border border-slate-800">
                      <div>
                        <div className="text-xs font-semibold text-slate-200">Host CPU Load Spike</div>
                        <div className="text-[11px] text-slate-500">Triggers adaptive throttle hysteresis</div>
                      </div>
                      <button
                        onClick={() => {
                          const next = !simCpuSpike;
                          setSimCpuSpike(next);
                          handleSimulatorStep(next, simLocalStop);
                        }}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                          simCpuSpike ? 'bg-amber-500 text-slate-950 font-bold' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                        }`}
                      >
                        {simCpuSpike ? 'Spike Active' : 'Trigger Spike'}
                      </button>
                    </div>

                    <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950 border border-slate-800">
                      <div>
                        <div className="text-xs font-semibold text-rose-400">Emergency Local Stop</div>
                        <div className="text-[11px] text-slate-500">Overrides remote administrator commands</div>
                      </div>
                      <button
                        onClick={() => {
                          const next = !simLocalStop;
                          setSimLocalStop(next);
                          handleSimulatorStep(simCpuSpike, next);
                        }}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                          simLocalStop ? 'bg-rose-600 text-white font-bold' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                        }`}
                      >
                        {simLocalStop ? 'Local Stop Engaged' : 'Trigger Stop'}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div className="lg:col-span-2 space-y-4">
                <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-300">
                      <Terminal className="w-4 h-4 text-cyan-400" />
                      <span>Worker Subprocess STDOUT Stream (Live Console)</span>
                    </div>
                    <span className="text-[11px] text-emerald-400 font-mono">Running (PID: 28564)</span>
                  </div>

                  <div className="bg-slate-950 rounded-lg p-4 font-mono text-xs text-cyan-300 space-y-1.5 h-80 overflow-y-auto border border-slate-800/80">
                    {simConsoleLogs.map((log, idx) => (
                      <div key={idx} className="leading-relaxed">
                        {log}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 6: ONEFILE .EXE & USB INSTRUCTIONS */}
        {activeTab === 'usb' && (
          <div className="space-y-6 max-w-4xl">
            <div className="p-6 rounded-xl bg-slate-900 border border-slate-800 space-y-5">
              <div className="flex items-center gap-2 text-base font-bold text-white">
                <Usb className="w-5 h-5 text-cyan-400" />
                <span>Single Standalone Windows x64 .EXE (--onefile)</span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                The PyInstaller build configuration has been compiled into <strong className="text-white">--onefile</strong> mode.
                This packages the entire Python runtime, PySide6 GUI, official AtomicDB worker script, and cryptographic modules into a single <code className="text-cyan-300 font-mono">AtomicDBPortable.exe</code>.
              </p>

              <div className="bg-slate-950 p-4 rounded-lg font-mono text-xs text-slate-300 border border-slate-800 space-y-1">
                <div className="text-cyan-400 font-bold mb-2">Standalone Output Location:</div>
                <div>dist\AtomicDBPortable.exe  [Single Standalone .EXE, ~55MB, Zero Admin, Zero Python Required]</div>
                <div>dist\AtomicDB_USB\         [USB deployment folder with engine\ and logs\ helper directories]</div>
              </div>

              <div className="space-y-3 pt-2">
                <div className="text-xs font-semibold text-slate-200">1-Click Windows Build (Batch):</div>
                <div className="bg-slate-950 p-3 rounded font-mono text-xs text-cyan-300 border border-slate-800 flex items-center justify-between">
                  <span>cd AtomicDBPortable &amp;&amp; build.bat</span>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText('cd AtomicDBPortable && build.bat');
                      showToast('Copied build command to clipboard');
                    }}
                    className="p-1 hover:text-white"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="text-xs font-semibold text-slate-200">Python Build Runner:</div>
                <div className="bg-slate-950 p-3 rounded font-mono text-xs text-cyan-300 border border-slate-800 flex items-center justify-between">
                  <span>python build_exe.py</span>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText('python build_exe.py');
                      showToast('Copied build command to clipboard');
                    }}
                    className="p-1 hover:text-white"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 7: AUDIT LOG */}
        {activeTab === 'audit' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white">Immutable Security &amp; Administrative Audit Log</h3>
                <p className="text-xs text-slate-400">All Master Control interventions, kill switch executions, and device task submissions.</p>
              </div>
              <button
                onClick={fetchFleetData}
                className="px-3 py-1.5 text-xs text-slate-300 bg-slate-900 border border-slate-800 hover:bg-slate-800 rounded-lg flex items-center gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Refresh Log</span>
              </button>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/70 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4">Timestamp</th>
                    <th className="py-3 px-4">Actor</th>
                    <th className="py-3 px-4">Action</th>
                    <th className="py-3 px-4">Target Device</th>
                    <th className="py-3 px-4">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                  {auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-800/30">
                      <td className="py-2.5 px-4 text-slate-500 tabular-nums">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </td>
                      <td className="py-2.5 px-4 font-sans font-medium text-slate-300">
                        {log.actor}
                      </td>
                      <td className="py-2.5 px-4">
                        <span className={`font-semibold ${
                          log.status === 'ERROR' ? 'text-rose-400' :
                          log.status === 'WARNING' ? 'text-amber-400' : 'text-cyan-400'
                        }`}>
                          {log.action}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-slate-400">
                        {log.target || '—'}
                      </td>
                      <td className="py-2.5 px-4 font-sans text-slate-300 max-w-md truncate">
                        {log.details}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* Remote Command Modal */}
      {isCommandModalOpen && commandTarget && (
        <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-md w-full space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-bold text-white">
                Dispatch Command: {commandTarget.name}
              </h4>
              <button
                onClick={() => setIsCommandModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSendCommand} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Command Action</label>
                <select
                  value={commandType}
                  onChange={(e) => setCommandType(e.target.value as any)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 font-sans"
                >
                  <option value="UPDATE_CONFIG">UPDATE_CONFIG (Adjust Resource Limits)</option>
                  <option value="PAUSE">PAUSE (Release Compute &amp; Sleep)</option>
                  <option value="RESUME">RESUME (Resume Analysis)</option>
                  <option value="TERMINATE">TERMINATE (Immediate Remote Kill)</option>
                  <option value="REVOKE">REVOKE (Invalidate Device Credentials)</option>
                </select>
              </div>

              {commandType === 'UPDATE_CONFIG' && (
                <div className="space-y-3 p-3.5 rounded-lg bg-slate-950 border border-slate-800 max-h-96 overflow-y-auto">
                  <div className="text-[11px] font-bold text-slate-300 uppercase tracking-wider">
                    Compute &amp; Memory Limits (Numbers)
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[11px] font-medium text-slate-400 mb-1">CPU Allocation Mode</label>
                      <select
                        value={configCpuMode}
                        onChange={(e) => setConfigCpuMode(e.target.value as any)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                      >
                        <option value="Adaptive">Adaptive (Default)</option>
                        <option value="Balanced">Balanced (50% Cores)</option>
                        <option value="Maximum">Maximum (Cores - 1)</option>
                        <option value="Custom">Custom Manual</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-slate-400 mb-1">Threads (-T)</label>
                      <input
                        type="number"
                        min="1"
                        max={commandTarget.hardware.logicalCores}
                        value={configThreads}
                        onChange={(e) => setConfigThreads(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <label className="block text-[11px] font-medium text-slate-400 mb-1">Jobs (--jobs)</label>
                      <input
                        type="number"
                        min="1"
                        max="32"
                        value={configJobs}
                        onChange={(e) => setConfigJobs(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-slate-400 mb-1">Hash MB (--hash)</label>
                      <input
                        type="number"
                        min="64"
                        max="65536"
                        step="128"
                        value={configHash}
                        onChange={(e) => setConfigHash(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-slate-400 mb-1">Engine Check Min</label>
                      <input
                        type="number"
                        min="0.5"
                        max="1440"
                        step="1"
                        value={configEngineUpdateMin}
                        onChange={(e) => setConfigEngineUpdateMin(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                      />
                    </div>
                  </div>

                  <div className="text-[11px] font-bold text-slate-300 uppercase tracking-wider pt-2 border-t border-slate-800">
                    Engine &amp; Path Settings (Inputs)
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">Custom Engine Path (--engine)</label>
                    <input
                      type="text"
                      placeholder="Optional binary path (blank = default)"
                      value={configEngine}
                      onChange={(e) => setConfigEngine(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">Syzygy Paths (--syzygy)</label>
                    <input
                      type="text"
                      placeholder="Paths separated by ;"
                      value={configSyzygy}
                      onChange={(e) => setConfigSyzygy(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                    />
                  </div>

                  <div className="text-[11px] font-bold text-slate-300 uppercase tracking-wider pt-2 border-t border-slate-800">
                    OpenBench Toggles &amp; Flags (Checkboxes)
                  </div>
                  <div className="space-y-1.5 text-xs">
                    <label className="flex items-center gap-2 p-1.5 rounded bg-slate-900/60 border border-emerald-500/30 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={configNoFetchSyzygy}
                        onChange={(e) => setConfigNoFetchSyzygy(e.target.checked)}
                        className="rounded border-slate-700 text-cyan-500"
                      />
                      <span className="text-emerald-300 font-semibold text-[11px]">
                        No Tablebase (--no-fetch-syzygy, Zero C: Trace, Always Enabled)
                      </span>
                    </label>

                    <label className="flex items-center gap-2 p-1.5 rounded bg-slate-900/60 border border-slate-800 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={configSolve}
                        onChange={(e) => setConfigSolve(e.target.checked)}
                        className="rounded border-slate-700 text-cyan-500"
                      />
                      <span className="text-slate-300 text-[11px]">
                        Solve Tasks (--solve, exhaustive proofs)
                      </span>
                    </label>

                    <label className="flex items-center gap-2 p-1.5 rounded bg-slate-900/60 border border-slate-800 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={configNoAutoUpdate}
                        onChange={(e) => setConfigNoAutoUpdate(e.target.checked)}
                        className="rounded border-slate-700 text-cyan-500"
                      />
                      <span className="text-slate-300 text-[11px]">
                        No Worker Auto-Update (--no-auto-update)
                      </span>
                    </label>

                    <label className="flex items-center gap-2 p-1.5 rounded bg-slate-900/60 border border-slate-800 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={configNoEngineUpdate}
                        onChange={(e) => setConfigNoEngineUpdate(e.target.checked)}
                        className="rounded border-slate-700 text-cyan-500"
                      />
                      <span className="text-slate-300 text-[11px]">
                        No Engine Auto-Update (--no-engine-update)
                      </span>
                    </label>

                    <label className="flex items-center gap-2 p-1.5 rounded bg-slate-900/60 border border-slate-800 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={configOnce}
                        onChange={(e) => setConfigOnce(e.target.checked)}
                        className="rounded border-slate-700 text-cyan-500"
                      />
                      <span className="text-slate-300 text-[11px]">
                        Run Once Smoke Test (--once)
                      </span>
                    </label>
                  </div>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCommandModalOpen(false)}
                  className="px-3 py-1.5 text-xs text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-semibold transition-colors"
                >
                  {isLoading ? 'Dispatching...' : 'Sign &amp; Dispatch Command'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Enrollment Token Modal */}
      {isTokenModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-md w-full space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-bold text-white">Generate Enrollment Token</h4>
              <button
                onClick={() => setIsTokenModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleGenerateToken} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Max Threads</label>
                <input
                  type="number"
                  value={tokenMaxThreads}
                  onChange={(e) => setTokenMaxThreads(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-white"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Max Hash (MB)</label>
                <input
                  type="number"
                  value={tokenMaxHash}
                  onChange={(e) => setTokenMaxHash(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-white"
                />
              </div>

              {generatedToken ? (
                <div className="p-3 bg-slate-950 border border-cyan-500/40 rounded space-y-2">
                  <div className="text-xs text-cyan-300 font-mono break-all">{generatedToken}</div>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(generatedToken);
                      showToast('Copied token to clipboard');
                    }}
                    className="w-full py-1 bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 rounded"
                  >
                    Copy Token
                  </button>
                </div>
              ) : (
                <button
                  type="submit"
                  className="w-full py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-semibold"
                >
                  Generate Token
                </button>
              )}
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

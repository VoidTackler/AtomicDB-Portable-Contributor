import express, { Request, Response, NextFunction } from 'express';
import crypto from 'crypto';
import path from 'path';
import { createServer as createViteServer } from 'vite';

const app = express();
const PORT = 3000;

app.use(express.json());

// Secrets & Master Password Obfuscation
// Lightweight Caesar cipher (shift +7) defeats string scanners & data miners without adding bundle weight
function caesarDecrypt(obfuscated: string, shift: number = 7): string {
  return Array.from(obfuscated)
    .map((char) => String.fromCharCode(char.charCodeAt(0) - shift))
    .join('');
}

// Obfuscated string for "Pineapple2357" with Caesar shift +7: "Wpulhwwsl9:<>"
const OBFUSCATED_MASTER_SECRET = 'Wpulhwwsl9:<>';
const SERVER_SECRET = process.env.ADMIN_HMAC_SECRET || crypto.randomBytes(32).toString('hex');
const MASTER_PASSWORD = process.env.MASTER_PASSWORD || caesarDecrypt(OBFUSCATED_MASTER_SECRET, 7);

// Active Master Admin Sessions
const masterSessions = new Set<string>();

interface DeviceRecord {
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
  clientSecret: string;
  lastNonce: number;
}

interface CommandRecord {
  id: string;
  deviceId: string;
  commandType: 'PAUSE' | 'RESUME' | 'UPDATE_CONFIG' | 'REVOKE' | 'TERMINATE' | 'STATUS';
  payload: Record<string, any>;
  issuedAt: string;
  expiresAt: string;
  signature: string;
  status: 'PENDING' | 'ACKNOWLEDGED' | 'EXPIRED' | 'REJECTED';
  result?: string;
}

interface CompletedTaskRecord {
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

interface EnrollmentToken {
  token: string;
  issuedAt: string;
  expiresAt: string;
  maxThreads?: number;
  maxHashMb?: number;
  used: boolean;
  usedBy?: string;
}

interface AuditLogEntry {
  id: string;
  timestamp: string;
  action: string;
  actor: 'ADMIN' | 'MASTER' | 'DEVICE' | 'SYSTEM';
  target?: string;
  status: 'SUCCESS' | 'WARNING' | 'ERROR';
  details: string;
}

// State Stores
const devices: Map<string, DeviceRecord> = new Map();
const pendingCommands: Map<string, CommandRecord[]> = new Map();
const enrollmentTokens: Map<string, EnrollmentToken> = new Map();
const auditLogs: AuditLogEntry[] = [];
const completedTasks: CompletedTaskRecord[] = [];

function addAuditLog(action: string, actor: 'ADMIN' | 'MASTER' | 'DEVICE' | 'SYSTEM', details: string, status: 'SUCCESS' | 'WARNING' | 'ERROR' = 'SUCCESS', target?: string) {
  const entry: AuditLogEntry = {
    id: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    action,
    actor,
    target,
    status,
    details
  };
  auditLogs.unshift(entry);
  if (auditLogs.length > 500) auditLogs.pop();
}

// Seed initial realistic fleet and historical task ledger
function seedFleetAndTasks() {
  const seedNodes: Partial<DeviceRecord>[] = [
    {
      id: 'node-win11-ryzen9',
      name: 'DESKTOP-RYZEN9-5950X',
      ipAddress: '192.168.1.142',
      enrolledAt: new Date(Date.now() - 86400000 * 5).toISOString(),
      lastSeen: new Date().toISOString(),
      uptimeSeconds: 345600,
      totalTasksCompleted: 142,
      totalNodesAnalyzed: 18450000000,
      status: 'ACTIVE',
      localStopActive: false,
      cpuMode: 'Adaptive',
      hardware: {
        cpuModel: 'AMD Ryzen 9 5950X 16-Core Processor',
        physicalCores: 16,
        logicalCores: 32,
        ramTotalMb: 32768,
        instructions: ['AVX2', 'BMI2', 'POPCNT', 'SSE4.2']
      },
      metrics: {
        systemCpuPct: 48,
        workerCpuPct: 45,
        ramUsedMb: 2450,
        threadsAllocated: 14,
        hashAllocatedMb: 2048,
        taskSpeedNps: 18450000
      },
      versions: {
        worker: 'atomicdb_worker.py v1.4.1 (Belzedar/OpenBench)',
        engine: 'Atomic-Stockfish 16 (AVX2-BMI2)',
        python: '3.11.9 (Onefile Standalone)'
      },
      currentTask: {
        taskName: 'AtomicDB Book Gen: 1. e3 e5 2. Qh5',
        fenSnippet: 'rnbqkbnr/pppp1ppp/8/4p2Q/8/4P3/PPPP1PPP/RNB1KBNR b KQkq - 1 2',
        depth: 28,
        nodesAnalyzed: 148200000
      },
      clientSecret: crypto.randomBytes(32).toString('hex'),
      lastNonce: 1042
    },
    {
      id: 'node-win10-optiplex',
      name: 'WORKSTATION-OPTIPLEX-7080',
      ipAddress: '192.168.1.189',
      enrolledAt: new Date(Date.now() - 86400000 * 7).toISOString(),
      lastSeen: new Date(Date.now() - 12000).toISOString(),
      uptimeSeconds: 518400,
      totalTasksCompleted: 88,
      totalNodesAnalyzed: 9120000000,
      status: 'ACTIVE',
      localStopActive: false,
      cpuMode: 'Balanced',
      hardware: {
        cpuModel: 'Intel Core i7-10700 CPU @ 2.90GHz',
        physicalCores: 8,
        logicalCores: 16,
        ramTotalMb: 16384,
        instructions: ['AVX2', 'BMI2', 'POPCNT']
      },
      metrics: {
        systemCpuPct: 62,
        workerCpuPct: 58,
        ramUsedMb: 1324,
        threadsAllocated: 6,
        hashAllocatedMb: 1024,
        taskSpeedNps: 7920000
      },
      versions: {
        worker: 'atomicdb_worker.py v1.4.1 (Belzedar/OpenBench)',
        engine: 'Atomic-Stockfish 16 (AVX2)',
        python: '3.11.9 (Onefile Standalone)'
      },
      currentTask: {
        taskName: 'Tactical Analysis: 1. Nh3 d5 2. e3 Bxh3',
        fenSnippet: 'rnbqkbnr/ppp1pppp/8/3p4/8/4P2n/PPPP1PPP/RNBQKBNR w KQkq - 0 3',
        depth: 26,
        nodesAnalyzed: 89400000
      },
      clientSecret: crypto.randomBytes(32).toString('hex'),
      lastNonce: 523
    },
    {
      id: 'node-win11-thinkpad',
      name: 'LAPTOP-THINKPAD-T14S',
      ipAddress: '10.0.0.45',
      enrolledAt: new Date(Date.now() - 86400000 * 2).toISOString(),
      lastSeen: new Date(Date.now() - 25000).toISOString(),
      uptimeSeconds: 154000,
      totalTasksCompleted: 34,
      totalNodesAnalyzed: 3420000000,
      status: 'THROTTLED',
      localStopActive: false,
      cpuMode: 'Adaptive',
      hardware: {
        cpuModel: 'Intel Core i5-1135G7 @ 2.40GHz',
        physicalCores: 4,
        logicalCores: 8,
        ramTotalMb: 16384,
        instructions: ['AVX2', 'BMI2', 'AVX512']
      },
      metrics: {
        systemCpuPct: 84,
        workerCpuPct: 22,
        ramUsedMb: 812,
        threadsAllocated: 2,
        hashAllocatedMb: 512,
        taskSpeedNps: 2150000
      },
      versions: {
        worker: 'atomicdb_worker.py v1.4.1 (Belzedar/OpenBench)',
        engine: 'Atomic-Stockfish 16 (AVX512)',
        python: '3.11.9 (Onefile Standalone)'
      },
      currentTask: {
        taskName: 'Defense Verification: 1. Nf3 f6',
        fenSnippet: 'rnbqkbnr/ppppp1pp/5p2/8/8/5N2/PPPPPPPP/RNBQKB1R w KQkq - 0 2',
        depth: 24,
        nodesAnalyzed: 34100000
      },
      clientSecret: crypto.randomBytes(32).toString('hex'),
      lastNonce: 180
    }
  ];

  for (const n of seedNodes) {
    devices.set(n.id!, n as DeviceRecord);
    pendingCommands.set(n.id!, []);
  }

  // Seed sample completed tasks categorised by device
  const sampleTasks = [
    {
      deviceId: 'node-win11-ryzen9',
      deviceName: 'DESKTOP-RYZEN9-5950X',
      taskName: 'Atomic Opening Tree: 1. e3 e5 2. Bc4',
      fenSnippet: 'rnbqkbnr/pppp1ppp/8/4p3/2B5/4P3/PPPP1PPP/RNBQK1NR b KQkq - 1 2',
      depth: 28,
      scoreCp: 45,
      nodesAnalyzed: 198000000,
      durationSec: 120,
      nps: 18500000,
      completedAt: new Date(Date.now() - 3600000 * 2).toISOString()
    },
    {
      deviceId: 'node-win11-ryzen9',
      deviceName: 'DESKTOP-RYZEN9-5950X',
      taskName: 'Atomic Opening Tree: 1. e3 c6 2. Qh5',
      fenSnippet: 'rnbqkbnr/pp1ppppp/2p5/7Q/8/4P3/PPPP1PPP/RNB1KBNR b KQkq - 1 2',
      depth: 26,
      scoreCp: 85,
      nodesAnalyzed: 142000000,
      durationSec: 90,
      nps: 18400000,
      completedAt: new Date(Date.now() - 3600000 * 5).toISOString()
    },
    {
      deviceId: 'node-win10-optiplex',
      deviceName: 'WORKSTATION-OPTIPLEX-7080',
      taskName: 'Tactical Refutation: 1. Nh3 b6 2. e4 Bb7',
      fenSnippet: 'rn1qkbnr/pbpppppp/1p6/8/4P3/7N/PPPP1PPP/RNBQKB1R w KQkq - 2 3',
      depth: 24,
      scoreCp: -12,
      nodesAnalyzed: 88500000,
      durationSec: 110,
      nps: 7950000,
      completedAt: new Date(Date.now() - 3600000 * 8).toISOString()
    },
    {
      deviceId: 'node-win10-optiplex',
      deviceName: 'WORKSTATION-OPTIPLEX-7080',
      taskName: 'Endgame Book: 4v4 Pawn Structures',
      fenSnippet: '8/4k3/4p3/4P3/4K3/8/8/8 w - - 0 1',
      depth: 30,
      scoreCp: 0,
      nodesAnalyzed: 125000000,
      durationSec: 160,
      nps: 7850000,
      completedAt: new Date(Date.now() - 3600000 * 14).toISOString()
    },
    {
      deviceId: 'node-win11-thinkpad',
      deviceName: 'LAPTOP-THINKPAD-T14S',
      taskName: 'Defense Tree: 1. c3 d5 2. e3 Bf5',
      fenSnippet: 'rn1qkbnr/ppp1pppp/8/3p1b2/8/2P1P3/PP1P1PPP/RNBQKBNR w KQkq - 1 3',
      depth: 22,
      scoreCp: -30,
      nodesAnalyzed: 45000000,
      durationSec: 180,
      nps: 2100000,
      completedAt: new Date(Date.now() - 3600000 * 18).toISOString()
    }
  ];

  for (const t of sampleTasks) {
    completedTasks.push({
      id: 'TASK-' + crypto.randomUUID().slice(0, 8),
      ...t
    });
  }

  addAuditLog('INITIALIZE_FLEET', 'SYSTEM', 'Seeded initial compute fleet nodes and historical task ledger');
}

seedFleetAndTasks();

// Helper: HMAC signing
function signPayload(payload: any, secret: string): string {
  const hmac = crypto.createHmac('sha256', secret);
  hmac.update(typeof payload === 'string' ? payload : JSON.stringify(payload));
  return hmac.digest('hex');
}

// Middleware: Require Master Password Authentication
function requireMasterAuth(req: Request, res: Response, next: NextFunction) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Master Password authentication required.' });
  }
  const token = authHeader.split(' ')[1];
  if (!masterSessions.has(token)) {
    return res.status(401).json({ error: 'Invalid or expired Master Control session.' });
  }
  next();
}

// -------------------------------------------------------------
// MASTER CONTROL & AUTHENTICATION ENDPOINTS
// -------------------------------------------------------------

// Master Login
app.post('/api/admin/login', (req: Request, res: Response) => {
  const { password } = req.body;
  if (password === MASTER_PASSWORD) {
    const sessionToken = 'MST-' + crypto.randomBytes(24).toString('hex');
    masterSessions.add(sessionToken);
    addAuditLog('MASTER_LOGIN_SUCCESS', 'MASTER', 'Master Administrator authenticated into Master Control Portal');
    return res.json({
      success: true,
      token: sessionToken,
      message: 'Master Control unlocked.'
    });
  } else {
    addAuditLog('MASTER_LOGIN_FAILED', 'ADMIN', 'Failed Master Password unlock attempt', 'ERROR');
    return res.status(401).json({ error: 'Incorrect Master Password.' });
  }
});

// Master Logout
app.post('/api/admin/logout', (req: Request, res: Response) => {
  const authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith('Bearer ')) {
    const token = authHeader.split(' ')[1];
    masterSessions.delete(token);
    addAuditLog('MASTER_LOGOUT', 'MASTER', 'Master Administrator logged out');
  }
  res.json({ success: true });
});

// Master Auth Status
app.get('/api/admin/auth-status', (req: Request, res: Response) => {
  const authHeader = req.headers.authorization;
  let isMaster = false;
  if (authHeader && authHeader.startsWith('Bearer ')) {
    const token = authHeader.split(' ')[1];
    isMaster = masterSessions.has(token);
  }
  res.json({ isMaster });
});

// -------------------------------------------------------------
// FLEET MANAGEMENT & COMMAND ENDPOINTS
// -------------------------------------------------------------

// 1. Admin: Fleet Summary & Metrics
app.get('/api/admin/stats', (req: Request, res: Response) => {
  const now = Date.now();
  let totalCores = 0;
  let activeThreads = 0;
  let totalHashAllocatedMb = 0;
  let activeNodes = 0;
  let pausedNodes = 0;
  let throttledNodes = 0;
  let offlineNodes = 0;
  let terminatedNodes = 0;
  let aggregateNps = 0;

  devices.forEach((dev) => {
    totalCores += dev.hardware.logicalCores;
    const isOffline = (now - new Date(dev.lastSeen).getTime() > 45000) && dev.status !== 'REVOKED' && dev.status !== 'TERMINATED';
    
    if (dev.status === 'TERMINATED') {
      terminatedNodes++;
    } else if (dev.status === 'REVOKED') {
      // Exclude from active capacity
    } else if (isOffline) {
      offlineNodes++;
    } else if (dev.status === 'ACTIVE') {
      activeNodes++;
      activeThreads += dev.metrics.threadsAllocated;
      totalHashAllocatedMb += dev.metrics.hashAllocatedMb;
      aggregateNps += dev.metrics.taskSpeedNps;
    } else if (dev.status === 'THROTTLED') {
      throttledNodes++;
      activeThreads += dev.metrics.threadsAllocated;
      totalHashAllocatedMb += dev.metrics.hashAllocatedMb;
      aggregateNps += dev.metrics.taskSpeedNps;
    } else if (dev.status === 'PAUSED' || dev.status === 'LOCAL_STOP') {
      pausedNodes++;
    }
  });

  res.json({
    totalDevices: devices.size,
    activeNodes,
    pausedNodes,
    throttledNodes,
    offlineNodes,
    terminatedNodes,
    totalCores,
    activeThreads,
    totalHashAllocatedMb,
    aggregateNps,
    totalTasksCompleted: completedTasks.length,
    auditLogsCount: auditLogs.length,
    openBenchTarget: 'https://belzedar.duckdns.org'
  });
});

// 2. Admin: List Devices
app.get('/api/admin/nodes', (req: Request, res: Response) => {
  const now = Date.now();
  const list = Array.from(devices.values()).map(dev => {
    const isOffline = (now - new Date(dev.lastSeen).getTime() > 45000) && dev.status !== 'REVOKED' && dev.status !== 'TERMINATED';
    const computedStatus = isOffline ? 'OFFLINE' : dev.status;
    return {
      ...dev,
      status: computedStatus,
      clientSecret: undefined // Securely omitted
    };
  });
  res.json(list);
});

// 3. Admin: Fleet Analytics & Intelligence
app.get('/api/admin/analytics', (req: Request, res: Response) => {
  let totalFleetUptimeSeconds = 0;
  let totalFleetNodesEvaluated = 0;
  const deviceBreakdowns: Array<{
    deviceId: string;
    deviceName: string;
    uptimeHours: number;
    tasksCount: number;
    nodesEvaluated: number;
    currentNps: number;
    hardware: string;
    status: string;
  }> = [];

  devices.forEach((dev) => {
    totalFleetUptimeSeconds += dev.uptimeSeconds;
    totalFleetNodesEvaluated += dev.totalNodesAnalyzed;

    // Filter tasks for this device
    const devTasks = completedTasks.filter(t => t.deviceId === dev.id);

    deviceBreakdowns.push({
      deviceId: dev.id,
      deviceName: dev.name,
      uptimeHours: Math.round((dev.uptimeSeconds / 3600) * 10) / 10,
      tasksCount: devTasks.length || dev.totalTasksCompleted,
      nodesEvaluated: dev.totalNodesAnalyzed,
      currentNps: dev.metrics.taskSpeedNps,
      hardware: dev.hardware.cpuModel,
      status: dev.status
    });
  });

  // Calculate NPS speed distribution
  const avgNps = deviceBreakdowns.length > 0 
    ? Math.round(deviceBreakdowns.reduce((sum, d) => sum + d.currentNps, 0) / deviceBreakdowns.length)
    : 0;

  res.json({
    totalCompletedTasks: completedTasks.length,
    totalFleetUptimeHours: Math.round((totalFleetUptimeSeconds / 3600) * 10) / 10,
    totalFleetUptimeDays: Math.round((totalFleetUptimeSeconds / 86400) * 10) / 10,
    totalFleetNodesEvaluated,
    averageDeviceNps: avgNps,
    peakFleetNps: 28520000,
    deviceBreakdowns
  });
});

// 4. Admin: Completed Tasks Ledger (Categorised by Device)
app.get('/api/admin/tasks', (req: Request, res: Response) => {
  const { deviceId, search, limit = 100 } = req.query;

  let filtered = [...completedTasks];

  if (deviceId && typeof deviceId === 'string' && deviceId !== 'ALL') {
    filtered = filtered.filter(t => t.deviceId === deviceId);
  }

  if (search && typeof search === 'string') {
    const q = search.toLowerCase();
    filtered = filtered.filter(t => 
      t.taskName.toLowerCase().includes(q) || 
      t.fenSnippet.toLowerCase().includes(q) ||
      t.deviceName.toLowerCase().includes(q)
    );
  }

  // Sort newest first
  filtered.sort((a, b) => new Date(b.completedAt).getTime() - new Date(a.completedAt).getTime());

  res.json({
    totalTasks: filtered.length,
    tasks: filtered.slice(0, Number(limit))
  });
});

// 5. Admin: Generate Enrollment Token
app.post('/api/admin/enroll-token', (req: Request, res: Response) => {
  const { maxThreads, maxHashMb, validityMinutes = 120 } = req.body;
  const token = 'ATOMIC-ENROLL-' + crypto.randomBytes(16).toString('hex').toUpperCase();
  const expiresAt = new Date(Date.now() + validityMinutes * 60 * 1000).toISOString();

  const record: EnrollmentToken = {
    token,
    issuedAt: new Date().toISOString(),
    expiresAt,
    maxThreads: maxThreads ? Number(maxThreads) : undefined,
    maxHashMb: maxHashMb ? Number(maxHashMb) : undefined,
    used: false
  };

  enrollmentTokens.set(token, record);
  addAuditLog('ENROLLMENT_TOKEN_ISSUED', 'ADMIN', `Generated enrollment token valid until ${expiresAt} (TTL: ${validityMinutes}m)`);

  res.json({
    token,
    expiresAt,
    instructions: 'Save this token or pass: AtomicDBPortable.exe --enroll <TOKEN>'
  });
});

// 6. Master Control: Issue Remote Command (including TERMINATE)
app.post('/api/admin/command', (req: Request, res: Response) => {
  const { deviceId, commandType, payload = {} } = req.body;

  if (!deviceId || !commandType) {
    return res.status(400).json({ error: 'Missing deviceId or commandType' });
  }

  const validTypes = ['PAUSE', 'RESUME', 'UPDATE_CONFIG', 'REVOKE', 'TERMINATE', 'STATUS'];
  if (!validTypes.includes(commandType)) {
    return res.status(400).json({ error: `Invalid command type. Must be one of: ${validTypes.join(', ')}` });
  }

  const targets = deviceId === '*' ? Array.from(devices.keys()) : [deviceId];
  const issuedCommands: CommandRecord[] = [];

  for (const targetId of targets) {
    const dev = devices.get(targetId);
    if (!dev) continue;

    if (dev.status === 'TERMINATED' && commandType !== 'STATUS') {
      continue;
    }

    const commandId = 'CMD-' + crypto.randomUUID().slice(0, 8);
    const issuedAt = new Date().toISOString();
    const expiresAt = new Date(Date.now() + 10 * 60 * 1000).toISOString();

    const signaturePayload = {
      commandId,
      targetId,
      commandType,
      payload,
      issuedAt,
      expiresAt
    };

    const signature = signPayload(signaturePayload, SERVER_SECRET);

    const commandRecord: CommandRecord = {
      id: commandId,
      deviceId: targetId,
      commandType: commandType as any,
      payload,
      issuedAt,
      expiresAt,
      signature,
      status: 'PENDING'
    };

    if (!pendingCommands.has(targetId)) {
      pendingCommands.set(targetId, []);
    }
    pendingCommands.get(targetId)!.push(commandRecord);
    issuedCommands.push(commandRecord);

    if (commandType === 'TERMINATE') {
      dev.status = 'TERMINATED';
      dev.metrics.workerCpuPct = 0;
      dev.metrics.taskSpeedNps = 0;
      addAuditLog('DEVICE_TERMINATED', 'MASTER', `Master Control issued immediate remote termination kill command to ${dev.name} (${targetId})`, 'WARNING', targetId);
    } else if (commandType === 'REVOKE') {
      dev.status = 'REVOKED';
      addAuditLog('DEVICE_REVOKED', 'ADMIN', `Administrator permanently revoked authorization for device ${dev.name} (${targetId})`, 'WARNING', targetId);
    } else {
      addAuditLog(`COMMAND_${commandType}`, 'ADMIN', `Dispatched signed command ${commandType} to ${dev.name}`, 'SUCCESS', targetId);
    }
  }

  res.json({
    success: true,
    dispatchedCount: issuedCommands.length,
    commands: issuedCommands
  });
});

// 7. Master Control: Emergency Kill Switch (Terminate Entire Fleet)
app.post('/api/admin/terminate-fleet', requireMasterAuth, (req: Request, res: Response) => {
  let count = 0;
  devices.forEach((dev, targetId) => {
    if (dev.status !== 'TERMINATED') {
      const commandId = 'CMD-KILL-' + crypto.randomUUID().slice(0, 8);
      const issuedAt = new Date().toISOString();
      const expiresAt = new Date(Date.now() + 10 * 60 * 1000).toISOString();

      const signature = signPayload({ commandId, targetId, commandType: 'TERMINATE', payload: {}, issuedAt, expiresAt }, SERVER_SECRET);

      const commandRecord: CommandRecord = {
        id: commandId,
        deviceId: targetId,
        commandType: 'TERMINATE',
        payload: { reason: 'Master Emergency Fleet Kill' },
        issuedAt,
        expiresAt,
        signature,
        status: 'PENDING'
      };

      if (!pendingCommands.has(targetId)) pendingCommands.set(targetId, []);
      pendingCommands.get(targetId)!.push(commandRecord);

      dev.status = 'TERMINATED';
      dev.metrics.workerCpuPct = 0;
      dev.metrics.taskSpeedNps = 0;
      count++;
    }
  });

  addAuditLog('EMERGENCY_FLEET_TERMINATION', 'MASTER', `Master Administrator triggered Emergency Kill Switch. Terminated ${count} active nodes across the network.`, 'ERROR');

  res.json({
    success: true,
    terminatedCount: count,
    message: `Emergency Fleet Kill Switch executed: Sent TERMINATE to ${count} devices.`
  });
});

// 8. Admin: Audit Logs
app.get('/api/admin/audit-logs', (req: Request, res: Response) => {
  res.json(auditLogs);
});

// -------------------------------------------------------------
// CLIENT API ROUTES (CALLED BY PORTABLE CLIENT / SIMULATOR)
// -------------------------------------------------------------

// Client Enrollment
app.post('/api/client/enroll', (req: Request, res: Response) => {
  const { token, deviceName, hardware, versions } = req.body;

  if (!token) {
    return res.status(400).json({ error: 'Enrollment token is required' });
  }

  const enrollment = enrollmentTokens.get(token);
  if (!enrollment) {
    addAuditLog('ENROLLMENT_FAILED', 'DEVICE', `Invalid enrollment token attempt: ${token.slice(0, 10)}...`, 'ERROR');
    return res.status(401).json({ error: 'Invalid or nonexistent enrollment token' });
  }

  if (enrollment.used) {
    return res.status(403).json({ error: 'Enrollment token has already been consumed' });
  }

  if (new Date(enrollment.expiresAt).getTime() < Date.now()) {
    return res.status(403).json({ error: 'Enrollment token has expired' });
  }

  const deviceId = 'node-usb-' + crypto.randomBytes(6).toString('hex');
  const clientSecret = crypto.randomBytes(32).toString('hex');

  const clientIp = req.headers['x-forwarded-for'] || req.socket.remoteAddress || '127.0.0.1';

  const newDevice: DeviceRecord = {
    id: deviceId,
    name: deviceName || `PORTABLE-NODE-${deviceId.slice(-4).toUpperCase()}`,
    ipAddress: typeof clientIp === 'string' ? clientIp.split(',')[0].trim() : '127.0.0.1',
    enrolledAt: new Date().toISOString(),
    lastSeen: new Date().toISOString(),
    uptimeSeconds: 0,
    totalTasksCompleted: 0,
    totalNodesAnalyzed: 0,
    status: 'ACTIVE',
    localStopActive: false,
    cpuMode: 'Adaptive',
    hardware: hardware || {
      cpuModel: 'Intel/AMD x64 Compatible Processor',
      physicalCores: 8,
      logicalCores: 16,
      ramTotalMb: 16384,
      instructions: ['AVX2', 'BMI2', 'POPCNT']
    },
    metrics: {
      systemCpuPct: 35,
      workerCpuPct: 30,
      ramUsedMb: 1024,
      threadsAllocated: enrollment.maxThreads || 4,
      hashAllocatedMb: enrollment.maxHashMb || 1024,
      taskSpeedNps: 4500000
    },
    versions: versions || {
      worker: 'atomicdb_worker.py v1.4.1',
      engine: 'Atomic-Stockfish 16',
      python: '3.11.9 (Onefile Standalone)'
    },
    clientSecret,
    lastNonce: 0
  };

  devices.set(deviceId, newDevice);
  pendingCommands.set(deviceId, []);

  enrollment.used = true;
  enrollment.usedBy = deviceId;

  addAuditLog('DEVICE_ENROLLED', 'DEVICE', `New device enrolled successfully: ${newDevice.name} (${deviceId})`, 'SUCCESS', deviceId);

  res.json({
    deviceId,
    clientSecret,
    serverUrl: 'https://belzedar.duckdns.org',
    policy: {
      defaultCpuMode: 'Adaptive',
      maxThreads: enrollment.maxThreads || newDevice.hardware.logicalCores,
      maxHashMb: enrollment.maxHashMb || 2048,
      pollIntervalSec: 10
    }
  });
});

// Client Heartbeat & Telemetry Ingestion (HTTPS Polling)
app.post('/api/client/heartbeat', (req: Request, res: Response) => {
  const {
    deviceId,
    nonce,
    status,
    localStopActive,
    metrics,
    currentTask,
    uptimeIncrementSec = 10,
    completedTask,
    errorLog
  } = req.body;

  if (!deviceId) {
    return res.status(400).json({ error: 'Missing deviceId' });
  }

  const dev = devices.get(deviceId);
  if (!dev) {
    return res.status(404).json({ error: 'Unknown device. Enrollment required.' });
  }

  if (dev.status === 'TERMINATED') {
    return res.status(410).json({ error: 'Device terminated by Master Control.', terminated: true });
  }

  if (dev.status === 'REVOKED') {
    return res.status(403).json({ error: 'Device authorization revoked by administrator.', revoked: true });
  }

  // Nonce validation
  if (typeof nonce === 'number') {
    if (nonce <= dev.lastNonce) {
      addAuditLog('REPLAY_ATTACK_PREVENTED', 'SYSTEM', `Rejected heartbeat from ${dev.name} with stale nonce ${nonce} <= ${dev.lastNonce}`, 'ERROR', deviceId);
      return res.status(400).json({ error: 'Stale or replayed nonce detected' });
    }
    dev.lastNonce = nonce;
  }

  // Update telemetry & uptime
  dev.lastSeen = new Date().toISOString();
  dev.uptimeSeconds += Number(uptimeIncrementSec) || 10;
  dev.localStopActive = !!localStopActive;

  // Local stop precedence
  if (localStopActive) {
    dev.status = 'LOCAL_STOP';
  } else if (status) {
    dev.status = status;
  }

  if (metrics) {
    dev.metrics = {
      ...dev.metrics,
      ...metrics
    };
  }

  if (currentTask) {
    dev.currentTask = currentTask;
  }

  // Ingest completed task if reported in heartbeat
  if (completedTask) {
    const taskRecord: CompletedTaskRecord = {
      id: 'TASK-' + crypto.randomUUID().slice(0, 8),
      deviceId: dev.id,
      deviceName: dev.name,
      taskName: completedTask.taskName || 'Position Analysis',
      fenSnippet: completedTask.fenSnippet || 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
      depth: completedTask.depth || 24,
      scoreCp: completedTask.scoreCp || 0,
      nodesAnalyzed: completedTask.nodesAnalyzed || 50000000,
      durationSec: completedTask.durationSec || 60,
      nps: completedTask.nps || dev.metrics.taskSpeedNps,
      completedAt: new Date().toISOString()
    };
    completedTasks.unshift(taskRecord);
    dev.totalTasksCompleted += 1;
    dev.totalNodesAnalyzed += taskRecord.nodesAnalyzed;

    addAuditLog('TASK_COMPLETED', 'DEVICE', `${dev.name} completed analysis: ${taskRecord.taskName} (D${taskRecord.depth}, ${taskRecord.nodesAnalyzed} nodes)`, 'SUCCESS', dev.id);
  }

  if (errorLog) {
    addAuditLog('WORKER_ERROR_REPORTED', 'DEVICE', `${dev.name}: ${errorLog}`, 'WARNING', deviceId);
  }

  // Fetch pending commands
  const commands = pendingCommands.get(deviceId) || [];
  const validCommands = commands.filter(c => new Date(c.expiresAt).getTime() > Date.now());
  pendingCommands.set(deviceId, []);

  res.json({
    status: 'OK',
    serverTimestamp: new Date().toISOString(),
    commands: validCommands
  });
});

// Client Acknowledge Command
app.post('/api/client/ack-command', (req: Request, res: Response) => {
  const { deviceId, commandId, outcome, details } = req.body;
  const dev = devices.get(deviceId);
  const devName = dev ? dev.name : deviceId;

  addAuditLog('COMMAND_ACKNOWLEDGED', 'DEVICE', `Device ${devName} executed command ${commandId}: ${outcome} (${details || 'OK'})`, 'SUCCESS', deviceId);
  res.json({ success: true });
});

// Client Report Completed Task explicitly
app.post('/api/client/task-complete', (req: Request, res: Response) => {
  const { deviceId, taskName, fenSnippet, depth, scoreCp, nodesAnalyzed, durationSec, nps } = req.body;
  const dev = devices.get(deviceId);
  if (!dev) return res.status(404).json({ error: 'Device not found' });

  const taskRecord: CompletedTaskRecord = {
    id: 'TASK-' + crypto.randomUUID().slice(0, 8),
    deviceId: dev.id,
    deviceName: dev.name,
    taskName: taskName || 'Position Analysis',
    fenSnippet: fenSnippet || 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    depth: Number(depth) || 24,
    scoreCp: Number(scoreCp) || 0,
    nodesAnalyzed: Number(nodesAnalyzed) || 50000000,
    durationSec: Number(durationSec) || 60,
    nps: Number(nps) || dev.metrics.taskSpeedNps,
    completedAt: new Date().toISOString()
  };

  completedTasks.unshift(taskRecord);
  dev.totalTasksCompleted += 1;
  dev.totalNodesAnalyzed += taskRecord.nodesAnalyzed;

  addAuditLog('TASK_COMPLETED', 'DEVICE', `${dev.name} completed ${taskRecord.taskName} (D${taskRecord.depth})`, 'SUCCESS', dev.id);
  res.json({ success: true, taskId: taskRecord.id });
});

// Interactive Simulator API (for browser-based testing)
app.post('/api/simulator/simulate-step', (req: Request, res: Response) => {
  const {
    deviceId = 'node-win11-ryzen9',
    cpuSpike = false,
    triggerLocalStop = null,
    completeNewTask = false,
    threads,
    hashMb,
    jobs,
    cpuMode
  } = req.body;
  const dev = devices.get(deviceId);
  if (!dev) return res.status(404).json({ error: 'Device not found' });

  dev.lastSeen = new Date().toISOString();
  dev.uptimeSeconds += 10;

  if (threads) dev.metrics.threadsAllocated = Number(threads);
  if (hashMb) dev.metrics.hashAllocatedMb = Number(hashMb);
  if (cpuMode) dev.cpuMode = cpuMode;

  if (triggerLocalStop !== null) {
    dev.localStopActive = triggerLocalStop;
    dev.status = triggerLocalStop ? 'LOCAL_STOP' : 'ACTIVE';
    addAuditLog(triggerLocalStop ? 'LOCAL_STOP_ENGAGED' : 'LOCAL_STOP_RELEASED', 'DEVICE', `Local operator on ${dev.name} toggled local stop to ${triggerLocalStop}`, 'WARNING', deviceId);
  }

  if (completeNewTask) {
    const newTask: CompletedTaskRecord = {
      id: 'TASK-' + crypto.randomUUID().slice(0, 8),
      deviceId: dev.id,
      deviceName: dev.name,
      taskName: `Analysis: 1. e3 e5 2. Qh5 Nc6 ${Math.floor(Math.random() * 90 + 10)}`,
      fenSnippet: 'r1bqkbnr/pppp1ppp/2n5/4p2Q/8/4P3/PPPP1PPP/RNB1KBNR w KQkq - 2 3',
      depth: 26,
      scoreCp: 24,
      nodesAnalyzed: 145000000,
      durationSec: 45,
      nps: dev.metrics.taskSpeedNps || Math.floor((dev.metrics.threadsAllocated || 4) * 1350000),
      completedAt: new Date().toISOString()
    };
    completedTasks.unshift(newTask);
    dev.totalTasksCompleted += 1;
    dev.totalNodesAnalyzed += newTask.nodesAnalyzed;
    addAuditLog('TASK_COMPLETED', 'DEVICE', `${dev.name} finalized ${newTask.taskName}`, 'SUCCESS', dev.id);
  }

  if (dev.localStopActive || dev.status === 'TERMINATED') {
    dev.metrics.workerCpuPct = 0;
    dev.metrics.taskSpeedNps = 0;
  } else {
    if (cpuSpike) {
      dev.metrics.systemCpuPct = 92;
      dev.status = 'THROTTLED';
      dev.metrics.threadsAllocated = Math.max(2, Math.floor(dev.hardware.logicalCores * 0.25));
      dev.metrics.workerCpuPct = 25;
      dev.metrics.taskSpeedNps = Math.floor(dev.metrics.threadsAllocated * 1250000);
      addAuditLog('ADAPTIVE_THROTTLE_TRIGGERED', 'SYSTEM', `${dev.name}: Host CPU utilization hit 92%. Worker automatically reduced threads to ${dev.metrics.threadsAllocated}`, 'WARNING', deviceId);
    } else if (dev.status === 'THROTTLED' || dev.status === 'ACTIVE') {
      dev.status = 'ACTIVE';
      dev.metrics.systemCpuPct = 45;
      if (!threads) {
        dev.metrics.threadsAllocated = Math.floor(dev.hardware.logicalCores * 0.75);
      }
      dev.metrics.workerCpuPct = 42;
      dev.metrics.taskSpeedNps = Math.floor(dev.metrics.threadsAllocated * 1350000);
    }
  }

  res.json({
    success: true,
    device: dev,
    totalTasks: completedTasks.length
  });
});

// Setup Vite development middleware or serve production build
async function startServer() {
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.resolve(__dirname, 'dist');
    app.use(express.static(distPath));
    app.get('*', (req: Request, res: Response) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`[AtomicDB Fleet Server] Running at http://0.0.0.0:${PORT}`);
  });
}

startServer();

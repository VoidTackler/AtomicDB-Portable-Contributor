import express, { Request, Response } from 'express';
import path from 'path';
import fs from 'fs';
import { execSync } from 'child_process';
import { createServer as createViteServer } from 'vite';

const app = express();
const PORT = 3000;

app.use(express.json());

// Fixed OpenBench credentials
const FIXED_CREDENTIALS = {
  username: 'PortableExe',
  passwordEncrypted: 'TH9sV2h6en52eWs=', // Caesar shifted "ExePassword"
  serverUrl: 'https://belzedar.duckdns.org',
  noFetchSyzygy: true
};

// Application status endpoint
app.get('/api/status', (_req: Request, res: Response) => {
  res.json({
    status: 'ONLINE',
    mode: 'STANDALONE_PORTABLE',
    fixedCredentials: {
      username: FIXED_CREDENTIALS.username,
      passwordEncrypted: FIXED_CREDENTIALS.passwordEncrypted,
      targetServer: FIXED_CREDENTIALS.serverUrl
    },
    folderLayout: {
      rootExe: 'AtomicDB.exe',
      launcher: 'RUN_ATOMICDB.bat',
      builder: 'build.bat',
      readyFolder: 'READY_TO_RUN_EXE/'
    }
  });
});

// Download complete USB package ZIP
app.get('/api/download-usb-package', (_req: Request, res: Response) => {
  try {
    const zipPath = path.resolve('/tmp', 'AtomicDB_Portable_USB.zip');
    const sourceDir = path.resolve(__dirname, 'AtomicDBPortable');

    // Generate zip using Python's standard zipfile library
    const script = `
import zipfile, os
src = "${sourceDir}"
dst = "${zipPath}"
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src):
        # Exclude pycache and build temporaries
        dirs[:] = [d for d in dirs if d not in ('__pycache__', 'build', '.git')]
        for f in files:
            if f.endswith('.pyc'):
                continue
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, src)
            zf.write(full_path, os.path.join('AtomicDBPortable', rel_path))
`;
    execSync(`python3 -c '${script}'`);

    if (fs.existsSync(zipPath)) {
      res.setHeader('Content-Type', 'application/zip');
      res.setHeader('Content-Disposition', 'attachment; filename="AtomicDB_Portable_USB.zip"');
      const fileStream = fs.createReadStream(zipPath);
      fileStream.pipe(res);
    } else {
      res.status(500).json({ error: 'Failed to generate package zip file' });
    }
  } catch (err: any) {
    console.error('Error creating zip package:', err);
    res.status(500).json({ error: String(err) });
  }
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
    app.get('*', (_req: Request, res: Response) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`[AtomicDB Portable Hub] Server listening at http://0.0.0.0:${PORT}`);
  });
}

startServer();

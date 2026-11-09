import express, { Request, Response } from 'express';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';
import { createServer as createViteServer } from 'vite';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3000;

app.use(express.json());

// Application status endpoint (credentials hidden from API responses)
app.get('/api/status', (_req: Request, res: Response) => {
  res.json({
    status: 'ONLINE',
    mode: 'STANDALONE_PORTABLE',
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

    // Generate zip using Python's shutil.make_archive
    execSync(`python3 -c "import shutil; shutil.make_archive('/tmp/AtomicDB_Portable_USB', 'zip', '${sourceDir}')"`);

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

// Guaranteed JSON handler for any other unhandled /api/* route (NEVER fallback to HTML)
app.all('/api/*', (req: Request, res: Response) => {
  res.status(404).json({
    error: 'API endpoint not found',
    path: req.path
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
    app.get('*', (_req: Request, res: Response) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`[AtomicDB Portable Hub] Server listening at http://0.0.0.0:${PORT}`);
  });
}

startServer();

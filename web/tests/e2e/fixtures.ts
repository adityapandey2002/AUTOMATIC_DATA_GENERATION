import { test as base, type Page } from '@playwright/test';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// fixtures.ts is at web/tests/e2e/fixtures.ts, so go up 3 levels to get AUTOMATIC_DATA_GENERATION
const PROJECT_ROOT = path.resolve(__dirname, '../../..');
const BACKEND_DIR = path.join(PROJECT_ROOT, 'backend');
const WEB_DIR = path.join(PROJECT_ROOT, 'web');

// Determine Python executable - prefer venv, fallback to system
const VENV_PYTHON = path.join(BACKEND_DIR, 'venv', 'Scripts', 'python.exe');
const SYSTEM_PYTHON = process.platform === 'win32' ? 'python.exe' : 'python3';
const PYTHON_EXE = existsSync(VENV_PYTHON) ? VENV_PYTHON : SYSTEM_PYTHON;

// For shell: true on Windows, quote paths with spaces
const PYTHON_CMD = process.platform === 'win32' && PYTHON_EXE.includes(' ') ? `"${PYTHON_EXE}"` : PYTHON_EXE;

// Determine npm executable - use npx which is always available
const NPM_EXE = 'npx';

console.log(`[FIXTURE] Python executable: ${PYTHON_EXE}`);
console.log(`[FIXTURE] Python command: ${PYTHON_CMD}`);
console.log(`[FIXTURE] Backend dir: ${BACKEND_DIR}`);
console.log(`[FIXTURE] Venv python exists: ${existsSync(VENV_PYTHON)}`);
console.log(`[FIXTURE] NPM executable: ${NPM_EXE}`);
console.log(`[FIXTURE] Web dir: ${WEB_DIR}`);

// Global process references (shared across tests in the same worker)
let globalBackendProcess: ChildProcess | null = null;
let globalFrontendProcess: ChildProcess | null = null;
let backendReady = false;
let frontendReady = false;

// Extend test with custom fixtures
type TestFixtures = {
  page: Page;
  backendUrl: string;
  frontendUrl: string;
};

export const test = base.extend<TestFixtures>({
  // Backend URL - starts backend once per worker
  backendUrl: [
    async ({}, use) => {
      if (!globalBackendProcess) {
        console.log('\n🚀 Starting backend server (once per worker)...');
        
        const env = {
          ...process.env,
          SCRIBE_TEST_PORT: '8766',
          DATABASE_URL: 'sqlite:///./test_scribe.db',
          GROQ_API_KEY: process.env.GROQ_API_KEY || '',
          GEMINI_API_KEY: process.env.GEMINI_API_KEY || '',
          SARVAM_API_KEY: '',
          BHASHINI_API_KEY: '',
          USE_LOCAL_FALLBACK: 'true',
          USE_INDIC_CONFORMER: 'false',
          LLM_FINAL_EXTRACT: 'false',
        };

        globalBackendProcess = spawn(PYTHON_CMD, ['-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8766'], {
          cwd: BACKEND_DIR,
          env,
          stdio: ['ignore', 'pipe', 'pipe'],
          shell: process.platform === 'win32', // Needed for .cmd files on Windows
        });

        globalBackendProcess.stdout?.on('data', (data) => {
          const msg = data.toString().trim();
          if (msg) console.log(`[BACKEND] ${msg}`);
        });
        globalBackendProcess.stderr?.on('data', (data) => {
          const msg = data.toString().trim();
          if (msg) console.error(`[BACKEND ERR] ${msg}`);
        });

        // Wait for backend to be ready
        await waitForHealth('http://localhost:8766/health', 30000);
        backendReady = true;
        console.log('✅ Backend ready at http://localhost:8766');
      } else {
        console.log('♻️  Reusing existing backend process');
      }

      await use('http://localhost:8766');

      // Note: We don't kill the backend here - it will be cleaned up in global teardown
    },
    { scope: 'worker', auto: true },
  ],

  // Frontend URL - starts frontend once per worker
  frontendUrl: [
    async ({ backendUrl }, use) => {
      if (!globalFrontendProcess) {
        console.log('\n🚀 Starting frontend dev server (once per worker)...');
        
        const env = {
          ...process.env,
          VITE_WS_URL: 'ws://localhost:8766/ws/dashboard',
          PORT: '3001',
        };

        globalFrontendProcess = spawn(NPM_EXE, ['vite', 'dev', '--port', '3001', '--host', '0.0.0.0'], {
          cwd: WEB_DIR,
          env,
          stdio: ['ignore', 'pipe', 'pipe'],
          shell: process.platform === 'win32',
        });

        globalFrontendProcess.stdout?.on('data', (data) => {
          const msg = data.toString().trim();
          if (msg) console.log(`[FRONTEND] ${msg}`);
        });
        globalFrontendProcess.stderr?.on('data', (data) => {
          const msg = data.toString().trim();
          if (msg) console.error(`[FRONTEND ERR] ${msg}`);
        });

        // Wait for Vite to be ready
        await waitForHealth('http://localhost:3001', 60000);
        frontendReady = true;
        console.log('✅ Frontend ready at http://localhost:3001');
      } else {
        console.log('♻️  Reusing existing frontend process');
      }

      await use('http://localhost:3001');
    },
    { scope: 'worker', auto: true },
  ],

  // Page fixture with baseURL set to frontend
  page: async ({ frontendUrl, browser }, use) => {
    const context = await browser.newContext({
      baseURL: frontendUrl,
      viewport: { width: 1440, height: 900 },
      permissions: ['microphone'],
    });
    const page = await context.newPage();
    
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        console.log(`[BROWSER CONSOLE ERROR] ${msg.text()}`);
      }
    });
    page.on('pageerror', (err) => {
      console.log(`[BROWSER PAGE ERROR] ${err.message}`);
    });

    await use(page);
    await context.close();
  },
});

// Helper to wait for a health endpoint
async function waitForHealth(url: string, timeoutMs: number): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Not ready yet
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`Timed out waiting for ${url} to become healthy after ${timeoutMs}ms`);
}

// Export cleanup function for global teardown
export async function cleanupProcesses() {
  console.log('\n🛑 Cleaning up processes...');
  
  if (globalFrontendProcess) {
    console.log('Stopping frontend...');
    globalFrontendProcess.kill('SIGTERM');
    await new Promise<void>((resolve) => {
      globalFrontendProcess!.on('exit', () => resolve());
      setTimeout(() => {
        globalFrontendProcess!.kill('SIGKILL');
        resolve();
      }, 5000);
    });
    globalFrontendProcess = null;
  }
  
  if (globalBackendProcess) {
    console.log('Stopping backend...');
    globalBackendProcess.kill('SIGTERM');
    await new Promise<void>((resolve) => {
      globalBackendProcess!.on('exit', () => resolve());
      setTimeout(() => {
        globalBackendProcess!.kill('SIGKILL');
        resolve();
      }, 5000);
    });
    globalBackendProcess = null;
  }
  
  backendReady = false;
  frontendReady = false;
}

export { expect } from '@playwright/test';
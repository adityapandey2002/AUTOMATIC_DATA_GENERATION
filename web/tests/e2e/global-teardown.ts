import { fileURLToPath } from 'url';
import path from 'path';
import { cleanupProcesses } from './fixtures';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default async function globalTeardown() {
  await cleanupProcesses();
}
// Đọc key theo thứ tự: biến môi trường -> .env trong thư mục đang chạy -> .env cạnh SKILL.md.
// Không bao giờ in giá trị key ra log.
import { readFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const SKILL_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const CANDIDATES = [resolve(process.cwd(), '.env'), resolve(SKILL_DIR, '.env')];

export function getEnv(name) {
  if (process.env[name]) return process.env[name];
  for (const p of CANDIDATES) {
    if (!existsSync(p)) continue;
    const m = readFileSync(p, 'utf8').match(new RegExp(`^${name}=(.*)$`, 'm'));
    if (m) return m[1].replace(/["\r]/g, '').trim();
  }
  return null;
}

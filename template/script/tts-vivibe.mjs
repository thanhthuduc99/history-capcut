#!/usr/bin/env node
// Vivibe (lucylab) TTS — json-rpc, 3 bước: ttsLongText -> poll getExportStatus -> tải wav -> ffmpeg sang mp3.
// Key/voice: VIVIBE_API_KEY + VIVIBE_VOICE trong .env (xem env.mjs).
// Usage: node tts-vivibe.mjs <text-file-or-"-"> <out.mp3>

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ENDPOINT = 'https://api.lucylab.io/json-rpc';
const __dirname = dirname(fileURLToPath(import.meta.url));

import { getEnv } from './env.mjs';
const findEnv = getEnv;

const KEY = findEnv('VIVIBE_API_KEY');
const VOICE_ID = findEnv('VIVIBE_VOICE') || findEnv('VOICE_ID');
if (!KEY || !VOICE_ID) { console.error('thiếu VIVIBE_API_KEY hoặc VIVIBE_VOICE trong .env'); process.exit(1); }

const [textArg, outArg] = process.argv.slice(2);
if (!textArg || !outArg) { console.error('Usage: node tts-vivibe.mjs <text-file|-> <out.mp3>'); process.exit(1); }
const text = (textArg === '-' ? readFileSync(0, 'utf8') : readFileSync(textArg, 'utf8')).trim();
if (!text) { console.error('text rỗng'); process.exit(1); }

async function rpc(method, input) {
  const res = await fetch(ENDPOINT, {
    method: 'POST',
    headers: { Authorization: `Bearer ${KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ method, input }),
  });
  const data = await res.json();
  if (data.error) throw new Error(`${method} lỗi: ${(data.error.message || '').slice(0, 200)}`);
  return data.result;
}

console.log(`vivibe TTS: ${text.length} ký tự, giọng ...${VOICE_ID.slice(-6)}`);
const { projectExportId, blockCount } = await rpc('ttsLongText', { text, userVoiceId: VOICE_ID, speed: 1 });
console.log(`đã gửi, ${blockCount || 0} block, chờ render...`);

let status = {};
for (let i = 0; i < 120; i++) {
  status = await rpc('getExportStatus', { projectExportId });
  if (status.state === 'completed') break;
  if (status.state === 'failed' || status.state === 'error') throw new Error(`job thất bại: ${JSON.stringify(status).slice(0, 200)}`);
  await new Promise((r) => setTimeout(r, 5000));
}
if (status.state !== 'completed') { console.error('chờ quá 10 phút vẫn chưa xong'); process.exit(1); }

const wavPath = outArg.replace(/\.mp3$/, '.wav');
const wavBuf = Buffer.from(await (await fetch(status.url)).arrayBuffer());
writeFileSync(wavPath, wavBuf);
if (status.srtUrl) {
  const srtBuf = Buffer.from(await (await fetch(status.srtUrl)).arrayBuffer());
  writeFileSync(outArg.replace(/\.mp3$/, '.srt'), srtBuf);
}

execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', wavPath, '-c:a', 'libmp3lame', '-b:a', '192k', outArg]);
console.log(`${outArg} ghi xong (wav ${wavBuf.length} byte)`);

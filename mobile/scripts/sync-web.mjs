#!/usr/bin/env node

/**
 * Sync web build to Capacitor www directory
 * Usage: node scripts/sync-web.mjs
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.join(__dirname, '..');
const srcDir = path.join(projectRoot, 'www');
const destDir = path.join(projectRoot, 'www');

function copyRecursive(src, dest) {
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true });
  }

  const files = fs.readdirSync(src);
  files.forEach(file => {
    const srcPath = path.join(src, file);
    const destPath = path.join(dest, file);
    const stat = fs.statSync(srcPath);

    if (stat.isDirectory()) {
      copyRecursive(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
      console.log(`✓ ${destPath}`);
    }
  });
}

console.log('Syncing web build to Capacitor...');
copyRecursive(srcDir, destDir);
console.log('\n✓ Web build synced to Capacitor');

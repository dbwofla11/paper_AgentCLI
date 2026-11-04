import { cpSync, createReadStream, existsSync, mkdirSync, readdirSync, statSync } from 'node:fs';
import { dirname, extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig, type Plugin } from 'vite';

// The WebUI server (`python3 .scripts/bin/research_webui.py serve`) owns every /api route.
const API_TARGET = 'http://127.0.0.1:8765';
const BASE = '/100-views/webui/';
const PDFJS_DIR = join(dirname(fileURLToPath(import.meta.url)), 'node_modules', 'pdfjs-dist');

/**
 * pdf.js assets fetched at runtime from `${BASE}pdfjs/` (src/reader/pdf.ts): CMaps, standard fonts,
 * and the no-WASM JPEG2000/JBIG2 decoders the worker imports when `useWasm` is false.
 * `*.wasm` and `iccs/` are not needed because WASM is off.
 */
function pdfjsAssetAllowed(path: string): boolean {
  const [top, ...rest] = path.split('/');
  if (rest.length === 0 || rest.some((part) => part === '' || part === '..')) return false;
  if (top === 'cmaps' || top === 'standard_fonts') return rest.length === 1;
  if (top !== 'wasm' || rest.length !== 1) return false;
  const [name] = rest;
  return name.endsWith('_nowasm_fallback.js') || name.startsWith('LICENSE_');
}

function pdfjsAssetFiles(): string[] {
  const files: string[] = [];
  for (const top of ['cmaps', 'standard_fonts', 'wasm']) {
    for (const name of readdirSync(join(PDFJS_DIR, top))) {
      const path = `${top}/${name}`;
      if (pdfjsAssetAllowed(path) && statSync(join(PDFJS_DIR, top, name)).isFile()) files.push(path);
    }
  }
  return files;
}

const ASSET_TYPES: Record<string, string> = {
  '.js': 'text/javascript; charset=utf-8',
  '.ttf': 'font/ttf',
};

function pdfjsAssets(): Plugin {
  return {
    name: 'pdfjs-assets',
    configureServer(server) {
      server.middlewares.use(`${BASE}pdfjs/`, (req, res, next) => {
        let path: string;
        try {
          path = decodeURIComponent((req.url ?? '').split('?')[0]).replace(/^\/+/, '');
        } catch {
          next();
          return;
        }
        // The allow-list admits only `<dir>/<name>` with no `..` segment, so the join stays inside pdfjs-dist.
        const file = join(PDFJS_DIR, path);
        if (!pdfjsAssetAllowed(path) || !existsSync(file)) {
          next();
          return;
        }
        res.setHeader('Content-Type', ASSET_TYPES[extname(file)] ?? 'application/octet-stream');
        createReadStream(file).pipe(res);
      });
    },
    writeBundle(options) {
      const outDir = options.dir;
      if (!outDir) return;
      for (const path of pdfjsAssetFiles()) {
        const target = join(outDir, 'pdfjs', path);
        mkdirSync(dirname(target), { recursive: true });
        cpSync(join(PDFJS_DIR, path), target);
      }
    },
  };
}

// Relative paths resolve against this directory (.scripts/webui), the Vite root.
export default defineConfig({
  base: BASE,
  plugins: [react(), pdfjsAssets()],
  build: {
    // Committed build output served by the WebUI server (decision D2).
    outDir: '../../100-views/webui',
    emptyOutDir: true,
    // Same as tsconfig; pdf.js 6 ships ES2022 syntax (class private fields and methods).
    target: 'es2022',
  },
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: API_TARGET,
        // The server accepts only Host 127.0.0.1:<port> and, on POST, Origin http://<Host>.
        changeOrigin: true,
        headers: { origin: API_TARGET },
      },
    },
  },
});

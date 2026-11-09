// Minimal static server with SPA fallback for the mobile build (what the Capacitor shell loads). No deps.
import { createReadStream, existsSync, statSync } from 'node:fs'
import { createServer } from 'node:http'
import { extname, join, normalize } from 'node:path'
import process from 'node:process'

const UP_RE = /^(\.\.[/\\])+/
const root = process.argv[2]
const port = Number(process.argv[3] ?? 3080)
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.woff2': 'font/woff2', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.png': 'image/png' }

createServer((req, res) => {
  const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(UP_RE, '')
  let file = join(root, path)
  if (!file.startsWith(root) || !existsSync(file) || statSync(file).isDirectory()) {
    file = join(root, '200.html') // SPA fallback, like the native WebView serving index for any route
  }
  res.writeHead(200, { 'Content-Type': types[extname(file)] ?? 'application/octet-stream' })
  createReadStream(file).pipe(res)
}).listen(port)

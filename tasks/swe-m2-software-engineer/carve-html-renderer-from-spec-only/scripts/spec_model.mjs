// Render documents with Carve's executable spec model (carve: scripts/spec/) or with djot.js.
//
// usage: node spec_model.mjs <model dir> [--djot] < requests.jsonl > replies.jsonl
//
// <model dir> is the local copy that scripts/setup_tools.py makes in experiment/specmodel:
// the pinned spec commit's scripts/spec, scripts/lib and resources, with ohm-js and
// @djot/djot installed beside them. Each request line is {"id", "source", "safe"?}; each reply
// line is {"id", "html"} (the model's HTML, trimmed, as the spec repository's own conformance
// pack compares it) or {"id", "refused": true|false, "error"} where the model refuses the input
// (outside its executable subset) or fails. With --djot, djot.js renders the source instead
// (renderHTML(parse(source))), untrimmed.
import { createInterface } from 'node:readline'
import { pathToFileURL } from 'node:url'
import { join } from 'node:path'

const base = process.argv[2]
const djotMode = process.argv.includes('--djot')
let render
if (djotMode) {
  const djot = await import(pathToFileURL(join(base, 'node_modules/@djot/djot/lib/index.js')).href)
  render = (source) => djot.renderHTML(djot.parse(source, { warn: () => {} }))
} else {
  const { parse } = await import(pathToFileURL(join(base, 'scripts/spec/layout.mjs')).href)
  const { renderDoc } = await import(pathToFileURL(join(base, 'scripts/spec/html.mjs')).href)
  render = (source, safe) => renderDoc(parse(source), { safe: Boolean(safe) }).trim()
}

const lines = createInterface({ input: process.stdin, crlfDelay: Infinity })
for await (const line of lines) {
  if (!line.trim()) continue
  const request = JSON.parse(line)
  let reply
  try {
    reply = { id: request.id, html: render(request.source, request.safe) }
  } catch (e) {
    reply = { id: request.id, refused: Boolean(e?.refuse), error: String(e?.message ?? e).slice(0, 300) }
  }
  process.stdout.write(JSON.stringify(reply) + '\n')
}

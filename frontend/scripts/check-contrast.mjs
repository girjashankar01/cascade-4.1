import { readFileSync } from 'node:fs'

// Measure actual semantic values from CSS; fail rather than silently skip a pair.
const css = readFileSync(new URL('../src/design/tokens.css', import.meta.url), 'utf8')
const pairs = []
for (const background of ['canvas', 'surface', 'recessed', 'attention-surface']) {
  for (const foreground of ['text', 'muted']) pairs.push([foreground, background, 4.5])
  pairs.push(['focus', background, 3], ['control-border', background, 3])
}
for (const state of ['action', 'action-hover', 'action-active']) pairs.push(['action-ink', state, 4.5])
for (const status of ['allowed', 'blocked', 'attention']) pairs.push([status, `${status}-surface`, 4.5])
pairs.push(['selection-ink', 'selection', 4.5])

function luminance(hex) {
  const components = hex.slice(1).match(/../g).map(part => {
    const value = parseInt(part, 16) / 255
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  })
  return components[0] * 0.2126 + components[1] * 0.7152 + components[2] * 0.0722
}

let failures = 0
console.log('| Theme | Foreground | Background | Ratio | Required | Result |')
console.log('|---|---|---|---:|---:|---|')
for (const theme of ['light', 'dark']) {
  const selector = `:root[data-theme='${theme}']`
  const start = css.indexOf(selector)
  if (start < 0) throw new Error(`Missing theme ${theme}`)
  const block = css.slice(css.indexOf('{', start) + 1, css.indexOf('}', start))
  const colors = Object.fromEntries([...block.matchAll(/--color-([\w-]+):\s*(#[0-9a-f]{6})/gi)].map(match => [match[1], match[2]]))
  for (const [foreground, background, required] of pairs) {
    if (!colors[foreground] || !colors[background]) throw new Error(`Missing color: ${theme} ${foreground}/${background}`)
    const values = [luminance(colors[foreground]), luminance(colors[background])].sort((a, b) => b - a)
    const ratio = (values[0] + 0.05) / (values[1] + 0.05)
    const passed = ratio >= required
    if (!passed) failures++
    console.log(`| ${theme} | ${foreground} ${colors[foreground]} | ${background} ${colors[background]} | ${ratio.toFixed(2)}:1 | ${required}:1 | ${passed ? 'PASS' : 'FAIL'} |`)
  }
}
console.log(`\n${pairs.length * 2} pairs measured; ${failures} failures. No alpha text, artwork, or decorative dividers are treated as control boundaries.`)
if (failures) process.exitCode = 1

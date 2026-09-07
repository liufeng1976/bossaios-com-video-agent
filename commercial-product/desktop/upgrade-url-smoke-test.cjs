// Checks the upgrade link the desktop shell actually builds.
//
// The URL is assembled in main.cjs from renderer-supplied context, so the test
// reads that source rather than a copy: the point is that a renderer cannot
// steer where the customer is sent, and a duplicate of the logic here would
// prove nothing about the file that ships.

const assert = require('assert')
const fs = require('fs')
const path = require('path')
const vm = require('vm')

const source = fs.readFileSync(path.join(__dirname, 'main.cjs'), 'utf8')

const grab = (pattern, label) => {
  const match = source.match(pattern)
  assert.ok(match, `could not find ${label} in main.cjs`)
  return match[0]
}

const sandbox = {
  URL,
  app: { getVersion: () => '0.1.0' },
  PRODUCT_ID: 'bossai-video-agent',
}
vm.createContext(sandbox)
vm.runInContext(
  [
    grab(/const UPGRADE_URL = '[^']+'/, 'UPGRADE_URL'),
    grab(/const UPGRADE_SOURCES = new Set\(\[[^\]]*\]\)/, 'UPGRADE_SOURCES'),
    grab(/const UPGRADE_LANGS = new Set\(\[[^\]]*\]\)/, 'UPGRADE_LANGS'),
    grab(/function buildUpgradeUrl\(context\) \{[\s\S]*?\n\}/, 'buildUpgradeUrl'),
    // `const` stays lexical inside the script, so hand the bindings out explicitly.
    'globalThis.extracted = { buildUpgradeUrl, UPGRADE_URL }',
  ].join('\n'),
  sandbox,
)

const { buildUpgradeUrl, UPGRADE_URL } = sandbox.extracted
const parse = (context) => new URL(buildUpgradeUrl(context))

// The destination is the pricing page, and it is fixed.
assert.strictEqual(UPGRADE_URL, 'https://bossaios.com/en/pricing.html')

// A known button is attributed as itself.
const plan = parse({ source: 'settings-plan', lang: 'zh-CN' })
assert.strictEqual(plan.origin + plan.pathname, 'https://bossaios.com/en/pricing.html')
assert.strictEqual(plan.searchParams.get('product'), 'bossai-video-agent')
assert.strictEqual(plan.searchParams.get('version'), '0.1.0')
assert.strictEqual(plan.searchParams.get('lang'), 'zh-CN')
assert.strictEqual(plan.searchParams.get('utm_source'), 'video-agent-desktop')
assert.strictEqual(plan.searchParams.get('utm_content'), 'settings-plan')

assert.strictEqual(parse({ source: 'settings-account', lang: 'en' }).searchParams.get('utm_content'), 'settings-account')

// Anything the allowlist does not recognise is reported as unspecified rather
// than echoed, so the link can never carry renderer-chosen text.
for (const bad of [undefined, '', 'made-up', '../../evil', '<script>', 'a'.repeat(500)]) {
  const url = parse({ source: bad, lang: 'en' })
  assert.strictEqual(url.searchParams.get('utm_content'), 'unspecified', `source ${JSON.stringify(bad)} leaked`)
}
for (const bad of [undefined, '', 'de-DE', 'javascript:alert(1)']) {
  assert.strictEqual(parse({ source: 'settings-plan', lang: bad }).searchParams.get('lang'), 'en')
}

// A renderer cannot redirect the customer, whatever it sends.
for (const context of [
  { source: 'settings-plan', lang: 'en', url: 'https://evil.example/' },
  { source: 'https://evil.example/', lang: 'https://evil.example/' },
  null,
  undefined,
  'settings-plan',
  42,
]) {
  const url = parse(context)
  assert.strictEqual(url.origin, 'https://bossaios.com', `origin moved for ${JSON.stringify(context)}`)
  assert.strictEqual(url.pathname, '/en/pricing.html', `path moved for ${JSON.stringify(context)}`)
}

// The link carries no identity: only constants and one of the fixed labels.
const keys = [...parse({ source: 'settings-plan', lang: 'zh-CN' }).searchParams.keys()].sort()
assert.deepStrictEqual(keys, ['lang', 'product', 'utm_campaign', 'utm_content', 'utm_medium', 'utm_source', 'version'])

console.log('RESULT: BossAI Video Agent upgrade link passed.')
console.log(
  'The destination is fixed to the pricing page, the button is attributed from an allowlist, unknown input becomes ' +
    '"unspecified" rather than being echoed, and the link carries no installation, account or device identity.',
)

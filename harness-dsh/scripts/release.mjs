import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import {
  cpSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync,
  renameSync, rmSync, writeFileSync,
} from 'node:fs'
import { stripTypeScriptTypes } from 'node:module'
import { tmpdir } from 'node:os'
import { isAbsolute, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const npmCli = process.env.npm_execpath
assert(npmCli && process.argv.length === 3, 'Usage: npm run release -- <directory outside the checkout>')

function git(args, cwd = root) {
  return execFileSync('git', args, { cwd, encoding: 'utf8' }).trim()
}

function npm(args, cwd) {
  execFileSync(process.execPath, [npmCli, ...args], { cwd, stdio: 'inherit' })
}

function json(path) {
  return JSON.parse(readFileSync(path, 'utf8'))
}

function digest(path, algorithm = 'sha256', encoding = 'hex') {
  return createHash(algorithm).update(readFileSync(path)).digest(encoding)
}

const repo = git(['rev-parse', '--show-toplevel'])
const output = resolve(process.argv[2])
const isOutsideRepo = path => {
  const fromRepo = relative(repo, path)
  return isAbsolute(fromRepo) || fromRepo.split(/[\\/]/)[0] === '..'
}
assert(isOutsideRepo(output), 'Use a release directory outside the checkout')
mkdirSync(output, { recursive: true })
assert(isOutsideRepo(realpathSync(output)), 'Release directory resolves inside the checkout')
assert.equal(git(['status', '--porcelain', '--', '.']), '', 'Commit Harness changes before packaging')
const commit = git(['rev-parse', 'HEAD'])
const manifest = json(join(root, 'package.json'))
const lock = json(join(root, 'package-lock.json'))
assert.equal(manifest.name, 'harness-dsh')
assert.match(manifest.version, /^\d+\.\d+\.\d+$/)
assert.equal(lock.version, manifest.version)
assert.equal(lock.packages[''].name, manifest.name)
assert.deepEqual(lock.packages[''].dependencies, manifest.dependencies)
assert.deepEqual(lock.packages[''].devDependencies, manifest.devDependencies)

const companionNames = ['@bpc-oss/dsh-evidence', '@bpc-oss/dsh-verification']
const sums = new Map(readFileSync(join(root, 'vendor/SHA256SUMS'), 'utf8').trim()
  .split(/\r?\n/).map(line => {
    const match = /^([a-f0-9]{64}) {2}([\w.-]+\.tgz)$/.exec(line)
    assert(match, 'Invalid vendor checksum line')
    return [match[2], match[1]]
  }))
assert.equal(sums.size, companionNames.length)
for (const name of companionNames) {
  const spec = manifest.dependencies[name]
  const entry = lock.packages['node_modules/' + name]
  assert.match(spec, /^file:vendor\/[\w.-]+\.tgz$/)
  assert.equal(entry.resolved, spec)
  const file = spec.slice('file:vendor/'.length)
  const archive = join(root, 'vendor', file)
  assert.equal(digest(archive), sums.get(file))
  assert.equal('sha512-' + digest(archive, 'sha512', 'base64'), entry.integrity)
}
for (const path of ['vendor/LICENSE-APACHE-2.0.txt', 'vendor/THIRD_PARTY_NOTICES.md',
  'vendor/UPSTREAM.md', 'src/reprolab/LICENSE']) {
  assert(readFileSync(join(root, path)).length > 0, 'Missing attribution: ' + path)
}
for (const [path, entry] of Object.entries(lock.packages)) {
  if (!path || companionNames.some(name => path === 'node_modules/' + name)) continue
  assert.equal(entry.resolved, undefined, 'Registry location must be configurable: ' + path)
  assert(entry.integrity, 'Missing registry integrity: ' + path)
}

const temp = mkdtempSync(join(tmpdir(), 'harness-dsh-release-'))
const artifacts = mkdtempSync(join(output, '.harness-dsh-'))
const installOptions = ['--no-audit', '--no-fund']
const sourceName = `Harness-DSH-source-${manifest.version}.zip`
const packageName = `${manifest.name}-${manifest.version}.tgz`
const smoke = `import assert from 'node:assert/strict';
  const plugin = await import(process.argv[1]);
  assert.equal(typeof plugin.apply, 'function');
  for (const name of ['@bpc-oss/dsh-verification', '@bpc-oss/dsh-evidence', 'stalegreen', 'fast-xml-parser']) {
    await import(name);
  }`
try {
  const source = join(temp, 'source')
  const stage = join(temp, 'package')
  const consumer = join(temp, 'consumer')
  for (const directory of [source, stage, consumer]) mkdirSync(directory)

  for (const path of ['src', 'package.json', 'package-lock.json', '.npmrc', 'vendor']) {
    cpSync(join(root, path), join(source, path), { recursive: true })
  }
  npm(['ci', '--omit=dev', '--cache', join(temp, 'source-cache'), ...installOptions], source)
  execFileSync(process.execPath, ['--input-type=module', '-e', smoke, './src/engineering.ts'],
    { cwd: source, stdio: 'inherit' })

  for (const path of ['src', 'README.md', 'INSTALL-WINDOWS.md', 'DEPENDENCIES.csv']) {
    cpSync(join(root, path), join(stage, path), { recursive: true })
  }
  const overlay = readFileSync(join(root, 'overlay.example.yml'), 'utf8')
    .replace('/Harness-DSH/src/engineering.ts', '/Harness-DSH/node_modules/harness-dsh/src/engineering.js')
    .replace('src/index.ts', 'src/index.js')
  writeFileSync(join(stage, 'overlay.example.yml'), overlay)
  mkdirSync(join(stage, 'vendor'))
  for (const path of ['LICENSE-APACHE-2.0.txt', 'THIRD_PARTY_NOTICES.md', 'UPSTREAM.md', 'SHA256SUMS']) {
    cpSync(join(root, 'vendor', path), join(stage, 'vendor', path))
  }

  // Node cannot strip TypeScript under node_modules. The deployed package uses
  // the same source and relative module graph compiled to JavaScript.
  for (const path of readdirSync(join(stage, 'src'), { recursive: true })) {
    if (!path.endsWith('.ts')) continue
    const input = join(stage, 'src', path)
    const javascript = stripTypeScriptTypes(readFileSync(input, 'utf8'))
      .replace(/(\bfrom\s+['"]\.{1,2}\/[^'"]+)\.ts(['"])/g, '$1.js$2')
    writeFileSync(input.replace(/\.ts$/, '.js'), javascript)
    rmSync(input)
  }
  const dependencies = Object.fromEntries(Object.keys(manifest.dependencies).map(name =>
    [name, lock.packages['node_modules/' + name].version]))
  const packaged = {
    name: manifest.name,
    version: manifest.version,
    description: 'Verification and engineering plugin for DeepSeek Harness',
    type: manifest.type,
    engines: manifest.engines,
    main: './src/engineering.js',
    exports: { '.': './src/engineering.js', './observer': './src/index.js' },
    files: ['src', 'vendor', 'INSTALL-WINDOWS.md', 'DEPENDENCIES.csv', 'overlay.example.yml'],
    dependencies,
  }
  writeFileSync(join(stage, 'package.json'), JSON.stringify(packaged, null, 2) + '\n')
  npm(['pack', '--pack-destination', artifacts, '--cache', join(temp, 'pack-cache')], stage)

  cpSync(join(root, '.npmrc'), join(consumer, '.npmrc'))
  writeFileSync(join(consumer, 'package.json'), '{ "private": true }\n')
  const archives = companionNames.map(name => join(root, manifest.dependencies[name].slice(5)))
  npm(['install', join(artifacts, packageName), ...archives,
    '--cache', join(temp, 'consumer-cache'), ...installOptions], consumer)
  execFileSync(process.execPath, ['--input-type=module', '-e', smoke, manifest.name],
    { cwd: consumer, stdio: 'inherit' })

  execFileSync('git', ['archive', '--format=zip', '--output=' + join(artifacts, sourceName),
    commit, '--', 'harness-dsh', ':!harness-dsh/evidence'], { cwd: repo, stdio: 'inherit' })

  const names = [sourceName, packageName]
  writeFileSync(join(artifacts, 'SHA256SUMS'), names.map(name =>
    `${digest(join(artifacts, name))}  ${name}\n`).join(''))
  for (const name of [...names, 'SHA256SUMS']) renameSync(join(artifacts, name), join(output, name))
  console.log(`Built release ${manifest.version} from ${commit} in ${output}`)
} finally {
  rmSync(temp, { recursive: true, force: true })
  rmSync(artifacts, { recursive: true, force: true })
}

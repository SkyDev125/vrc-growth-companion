/* Server-side publication only. The signing key never enters GitHub or an installer. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const os = require('node:os');
const names = {
  'windows-x64': 'mids-den-companion-windows-setup.exe',
  'macos-arm64': 'mids-den-companion-macos-arm64.dmg',
  'macos-x64': 'mids-den-companion-macos-x64.dmg',
  'linux-x64': 'mids-den-companion-linux-x64',
};
function sign(info, key) {
  const payload = Buffer.from(JSON.stringify(info));
  return { payload: payload.toString('base64'), signature: crypto.sign(null, payload, key).toString('base64') };
}
function publish(source, dataDir, build, attempt, key) {
  if (!Number.isSafeInteger(build) || build < 1 || !Number.isSafeInteger(attempt) || attempt < 1) throw Error('Invalid build');
  const version = JSON.parse(fs.readFileSync(path.join(__dirname, 'update-assets/build.json'))).version;
  const publicKey = crypto.createPublicKey(fs.readFileSync(path.join(__dirname, 'update-assets/public-key.pem')));
  if (!crypto.createPublicKey(key).export({format:'der',type:'spki'}).equals(publicKey.export({format:'der',type:'spki'}))) throw Error('Wrong signing key');
  const manifest = path.join(dataDir, 'companion-update.json');
  if (fs.existsSync(manifest)) {
    const previous = JSON.parse(Buffer.from(JSON.parse(fs.readFileSync(manifest)).payload, 'base64'));
    if (build < previous.build || (build === previous.build && attempt <= previous.attempt)) throw Error('Refusing stale release');
  }
  const generation = `${build}-${attempt}`;
  const destination = path.join(dataDir, 'companion-updates', generation);
  fs.mkdirSync(destination, {recursive:true, mode:0o700});
  const info = {schema:1, version, build, attempt, assets:{}};
  for (const [target, name] of Object.entries(names)) {
    const bytes = fs.readFileSync(path.join(source, name));
    if (!bytes.length || bytes.length > 500 * 1024 * 1024) throw Error('Invalid package size');
    const file = path.join(destination, name);
    if (fs.existsSync(file) && !fs.readFileSync(file).equals(bytes)) throw Error('Immutable release already exists');
    if (!fs.existsSync(file)) fs.writeFileSync(file, bytes, {mode:0o600, flag:'wx'});
    info.assets[target] = {size:bytes.length, sha256:crypto.createHash('sha256').update(bytes).digest('hex'),
      url:`https://mid.shardware.net/api/companion/download/${generation}/${name}`};
  }
  const temp = `${manifest}.${process.pid}.tmp`;
  fs.writeFileSync(temp, JSON.stringify(sign(info, key)), {mode:0o600});
  fs.renameSync(temp, manifest);
  return info;
}
if (require.main === module) {
  const [source, dataDir, build, attempt] = process.argv.slice(2);
  const key = crypto.createPrivateKey(fs.readFileSync(path.join(os.homedir(), '.local/share/mids-den-companion/update-signing-key.pem')));
  const result = publish(source, dataDir, Number(build), Number(attempt), key);
  console.log(`Published signed companion update ${result.version}, build ${result.build}-${result.attempt}`);
}
module.exports = {publish, sign};

/* Offline process-lifecycle fixture. Never used for inference or live acceptance. */
const fs = require('node:fs');
const path = require('node:path');
const output = process.argv[process.argv.indexOf('--output') + 1];
fs.mkdirSync(output, { recursive: true });
const source = fs.readFileSync(process.argv[process.argv.indexOf('--transcript') + 1], 'utf8');
const receipt = path.join(output, 'fixture.json');
const attempt = fs.existsSync(receipt) ? JSON.parse(fs.readFileSync(receipt)).attempt + 1 : 1;
const start = Date.now();
fs.writeFileSync(receipt, JSON.stringify({ start, attempt }));
if (source.startsWith('fixture:timeout') && attempt === 1) {
  console.log(JSON.stringify({ reason: 'ReadTimeout' })); process.exitCode = 1;
} else setTimeout(() => {
  fs.writeFileSync(receipt, JSON.stringify({ start, attempt, finish: Date.now() }));
  fs.writeFileSync(path.join(output, 'report.md'), 'Fixture draft, not medical evidence.');
}, 100);

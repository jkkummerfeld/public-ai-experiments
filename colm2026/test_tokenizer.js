// Checks the in-page tokenizer port against the Python tokenizer's output
// (cache/tokenizer_probe.json, written by build.py). Run: node test_tokenizer.js
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/template.html', 'utf8');
const code = src.slice(src.indexOf('/*TOK-START*/'), src.indexOf('/*TOK-END*/'));
const makeTokenizer = new Function(code + '; return makeTokenizer;')();
const tok = makeTokenizer(fs.readFileSync(__dirname + '/model/vocab.txt', 'utf8').split('\n'));
const probe = JSON.parse(fs.readFileSync(__dirname + '/cache/tokenizer_probe.json', 'utf8'));
let bad = 0;
probe.texts.forEach((t, i) => {
  const got = tok(t).join(','), want = probe.ids[i].join(',');
  if (got !== want) { bad++; if (bad <= 5) console.log('MISMATCH', t, '\n  js', got, '\n  py', want); }
});
console.log(`${probe.texts.length - bad}/${probe.texts.length} match`);
process.exit(bad ? 1 : 0);

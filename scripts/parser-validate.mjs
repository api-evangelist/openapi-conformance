// Adapter for the JS parser libraries that expose validate() but no CLI.
// @apidevtools/swagger-parser throws on an invalid document; @readme/openapi-parser returns {valid, errors}.
// Usage: node parser-validate.mjs <package> <doc.yaml>. Exit 0 valid, 1 invalid.
const [pkg, docPath] = process.argv.slice(2);
const mod = await import(pkg);
const validate = mod.validate ?? mod.default.validate.bind(mod.default);
try {
  const r = await validate(docPath);
  if (r && r.valid === false) { console.log(JSON.stringify(r.errors).slice(0, 800)); process.exit(1); }
  console.log('valid'); process.exit(0);
} catch (e) {
  console.log(String(e.message || e).slice(0, 800)); process.exit(1);
}

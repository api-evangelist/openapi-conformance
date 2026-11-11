// Reference baseline: validate one document against the official OAI JSON Schema for its version, the way the
// OAI's own tests/schema runner does (OAI/build-infra): hyperjump, schema-base.yaml, the OAS dialect + meta-schema
// registered so Schema Objects are validated too. 3.0 has no schema-base; its schema.yaml (draft-04) is used as is.
// Usage: node schema-check.mjs <schema dir> <doc.yaml>. Exit 0 valid, 1 invalid.
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
import YAML from 'yaml';
import { addMediaTypePlugin } from '@hyperjump/browser';
import { registerSchema, validate } from '@hyperjump/json-schema/draft-2020-12';
import '@hyperjump/json-schema/draft-04';
import '@hyperjump/json-schema/openapi-3-0';
import { buildSchemaDocument, defineVocabulary, BASIC } from '@hyperjump/json-schema/experimental';

addMediaTypePlugin('application/schema+yaml', {
  parse: async (response) => buildSchemaDocument(YAML.parse(await response.text()), response.url),
  fileMatcher: (path) => path.endsWith('.yaml'),
});

const [dir, docPath] = process.argv.slice(2);
const read = f => YAML.parse(fs.readFileSync(`${dir}/${f}`, 'utf8'));
const instance = YAML.parse(fs.readFileSync(docPath, 'utf8'));
let target = `${dir}/schema.yaml`;
if (fs.existsSync(`${dir}/schema-base.yaml`)) {
  const meta = read('meta.yaml');
  defineVocabulary(Object.keys(meta.$vocabulary)[0], Object.fromEntries(['discriminator', 'example', 'externalDocs', 'xml']
    .map(k => [k, `https://spec.openapis.org/oas/3.0/keyword/${k}`])));
  registerSchema(meta); registerSchema(read('dialect.yaml')); registerSchema(read('schema.yaml'));
  target = `${dir}/schema-base.yaml`;
}
const result = (await validate(pathToFileURL(fs.realpathSync(target)).href))(instance, BASIC);
if (result.valid) { console.log('valid'); process.exit(0); }
for (const e of (result.errors || []).slice(-10)) console.log(`${e.instanceLocation} ${e.keyword ?? e.absoluteKeywordLocation ?? ''}`);
process.exit(1);

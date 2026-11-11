#!/usr/bin/env python3
"""Generate the API Evangelist OpenAPI cases from one valid base document per version plus one mutation per case.
Each case breaks (or exercises) exactly ONE rule, and names the spec section that states it.
Writes cases/ae/<version>/<id>.openapi.yaml and cases/ae/<version>/manifest.yml. Re-run after editing CASES."""
import copy, os, yaml

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'cases', 'ae')
VERSIONS = ['3.0.4', '3.1.1', '3.2.0']
SPEC = {v: f'https://spec.openapis.org/oas/v{v}.html' for v in VERSIONS}

def base(v):
    return {
        'openapi': v,
        'info': {'title': 'Conformance base', 'version': '1.0.0'},
        'servers': [{'url': 'https://api.example.com/v1'}],
        'paths': {
            '/pets': {
                'get': {'operationId': 'listPets', 'tags': ['pets'],
                        'parameters': [{'name': 'limit', 'in': 'query', 'schema': {'type': 'integer'}}],
                        'responses': {'200': {'description': 'A list of pets',
                                              'content': {'application/json': {'schema': {'type': 'array', 'items': {'$ref': '#/components/schemas/Pet'}}}}}}},
                'post': {'operationId': 'createPet', 'tags': ['pets'],
                         'requestBody': {'required': True, 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/Pet'}}}},
                         'responses': {'201': {'description': 'Created'}}},
            },
            '/pets/{petId}': {
                'parameters': [{'name': 'petId', 'in': 'path', 'required': True, 'schema': {'type': 'string'}}],
                'get': {'operationId': 'getPet', 'tags': ['pets'], 'security': [{'apiKey': []}],
                        'responses': {'200': {'description': 'A pet', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/Pet'}}}},
                                      '404': {'description': 'Not found'}}},
            },
        },
        'components': {
            'schemas': {'Pet': {'type': 'object', 'required': ['name'], 'properties': {'id': {'type': 'string'}, 'name': {'type': 'string'}}}},
            'securitySchemes': {'apiKey': {'type': 'apiKey', 'name': 'X-API-Key', 'in': 'header'}},
        },
        'tags': [{'name': 'pets'}],
    }

# Where the official schema and the spec's prose disagree, the prose wins and the case says so.
NOTES = {
    ('invalid-component-key', '3.0.4'): 'The spec states the key pattern; the official 3.0 schema lists it as patternProperties without forbidding other keys, so for 3.0 only a validator catches it.',
}
LEVEL = {('invalid-component-key', '3.0.4'): 'semantic'}

ALL, V31UP, V32 = VERSIONS, ['3.1.1', '3.2.0'], ['3.2.0']
P, I = lambda d: d['paths']['/pets'], lambda d: d['paths']['/pets/{petId}']

def drop(d, *keys):
    for k in keys: d.pop(k)

# (id, versions, expect, level, rule, spec anchor, mutate)
# level: schema = the official JSON Schema alone decides it; semantic = only a validator that reads the spec's prose catches it
CASES = [
    # ---- valid documents
    ('valid-base', ALL, 'valid', 'schema', 'the base document: paths, path-level parameter, request body, $refs, security, tags', 'openapi-object', lambda d, v: None),
    ('valid-response-range', ALL, 'valid', 'schema', 'a response code may be a range like 4XX, and default is allowed', 'responses-object',
     lambda d, v: I(d)['get']['responses'].update({'4XX': {'description': 'Client error'}, 'default': {'description': 'Error'}})),
    ('valid-extensions', ALL, 'valid', 'schema', 'x- specification extensions are allowed on most objects', 'specification-extensions',
     lambda d, v: (d.update({'x-audience': 'public'}), P(d)['get'].update({'x-rate-limit': 100}))),
    ('valid-undeclared-operation-tag', ALL, 'valid', 'semantic', 'an operation may use a tag the top-level tags list does not declare', 'tag-object',
     lambda d, v: P(d)['get']['tags'].append('inventory')),
    ('valid-path-template-different-literal', ALL, 'valid', 'semantic', 'paths that differ in a literal segment are distinct (/pets/{petId} and /pets/mine)', 'paths-object',
     lambda d, v: d['paths'].update({'/pets/mine': {'get': {'operationId': 'myPets', 'responses': {'200': {'description': 'ok'}}}}})),
    ('valid-no-responses', V31UP, 'valid', 'schema', 'from 3.1 an operation may omit responses', 'operation-object',
     lambda d, v: P(d)['post'].pop('responses')),
    ('valid-webhooks-only', V31UP, 'valid', 'schema', 'from 3.1 a document may have webhooks and no paths', 'openapi-object',
     lambda d, v: (d.pop('paths'), d.update(webhooks={'newPet': {'post': {'requestBody': {'content': {'application/json': {'schema': {'$ref': '#/components/schemas/Pet'}}}}, 'responses': {'200': {'description': 'ok'}}}}}))),
    ('valid-type-array-null', V31UP, 'valid', 'schema', 'from 3.1 a schema type may be an array including "null"', 'schema-object',
     lambda d, v: d['components']['schemas']['Pet']['properties']['name'].update(type=['string', 'null'])),
    ('valid-license-identifier', V31UP, 'valid', 'schema', 'from 3.1 license may carry an SPDX identifier', 'license-object',
     lambda d, v: d['info'].update(license={'name': 'Apache 2.0', 'identifier': 'Apache-2.0'})),
    ('valid-path-item-ref-component', V31UP, 'valid', 'schema', 'from 3.1 components may hold pathItems', 'components-object',
     lambda d, v: (d['components'].update(pathItems={'Health': {'get': {'operationId': 'health', 'responses': {'200': {'description': 'ok'}}}}}),
                   d['paths'].update({'/health': {'$ref': '#/components/pathItems/Health'}}))),
    ('valid-nullable', ['3.0.4'], 'valid', 'schema', 'in 3.0 a schema may be nullable', 'schema-object',
     lambda d, v: d['components']['schemas']['Pet']['properties']['name'].update(nullable=True)),
    ('valid-query-method', V32, 'valid', 'schema', '3.2 adds the query operation to the Path Item', 'path-item-object',
     lambda d, v: P(d).update(query={'operationId': 'searchPets', 'requestBody': {'content': {'application/json': {'schema': {'type': 'object'}}}}, 'responses': {'200': {'description': 'ok'}}})),
    ('valid-additional-operations', V32, 'valid', 'schema', '3.2 additionalOperations carries methods outside the fixed set', 'path-item-object',
     lambda d, v: I(d).update(additionalOperations={'LINK': {'operationId': 'linkPet', 'responses': {'204': {'description': 'ok'}}}})),
    ('valid-self', V32, 'valid', 'schema', '3.2 $self gives the document its own base URI', 'openapi-object',
     lambda d, v: d.update({'$self': 'https://api.example.com/openapi.yaml'})),
    ('valid-tag-parent-kind', V32, 'valid', 'schema', '3.2 tags may name a parent and a kind', 'tag-object',
     lambda d, v: d['tags'].extend([{'name': 'animals', 'kind': 'nav'}]) or d['tags'][0].update(parent='animals', summary='Pets')),
    ('valid-item-schema', V32, 'valid', 'schema', '3.2 itemSchema describes each item of a streamed media type', 'media-type-object',
     lambda d, v: P(d)['get']['responses']['200']['content'].update({'application/jsonl': {'itemSchema': {'$ref': '#/components/schemas/Pet'}}})),
    ('valid-querystring-parameter', V32, 'valid', 'schema', '3.2 adds in: querystring, which takes content, not schema', 'parameter-object',
     lambda d, v: P(d)['get'].update(parameters=[{'name': 'q', 'in': 'querystring', 'content': {'application/x-www-form-urlencoded': {'schema': {'type': 'object'}}}}])),

    # ---- invalid: the official schema decides
    ('invalid-missing-info', ALL, 'invalid', 'schema', 'info is required', 'openapi-object', lambda d, v: d.pop('info')),
    ('invalid-missing-info-version', ALL, 'invalid', 'schema', 'info.version is required', 'info-object', lambda d, v: d['info'].pop('version')),
    ('invalid-openapi-version', ALL, 'invalid', 'schema', 'the openapi field must be a full major.minor.patch version of this line', 'openapi-object',
     lambda d, v: d.update(openapi=v.rsplit('.', 1)[0])),
    ('invalid-path-no-leading-slash', ALL, 'invalid', 'schema', 'path keys must begin with a slash', 'paths-object',
     lambda d, v: d['paths'].update({'pets/all': d['paths'].pop('/pets')})),
    ('invalid-response-code', ALL, 'invalid', 'schema', 'response keys are HTTP status codes, ranges like 2XX, or default', 'responses-object',
     lambda d, v: I(d)['get']['responses'].update({'2000': {'description': 'not a code'}})),
    ('invalid-response-no-description', ['3.0.4', '3.1.1'], 'invalid', 'schema', 'a Response Object requires description (before 3.2)', 'response-object',
     lambda d, v: P(d)['post']['responses']['201'].pop('description')),
    ('invalid-path-param-not-required', ALL, 'invalid', 'schema', 'a path parameter must have required: true', 'parameter-object',
     lambda d, v: I(d)['parameters'][0].update(required=False)),
    ('invalid-parameter-in', ALL, 'invalid', 'schema', 'parameter in must be query, header, path or cookie', 'parameter-object',
     lambda d, v: P(d)['get']['parameters'][0].update({'in': 'body'})),
    ('invalid-parameter-schema-and-content', ALL, 'invalid', 'schema', 'a parameter has schema or content, not both', 'parameter-object',
     lambda d, v: P(d)['get']['parameters'][0].update(content={'application/json': {'schema': {'type': 'integer'}}})),
    ('invalid-security-scheme-type', ALL, 'invalid', 'schema', 'security scheme type must be one of the defined types', 'security-scheme-object',
     lambda d, v: d['components']['securitySchemes']['apiKey'].update(type='token')),
    ('invalid-oauth2-no-flows', ALL, 'invalid', 'schema', 'an oauth2 security scheme requires flows', 'security-scheme-object',
     lambda d, v: d['components']['securitySchemes'].update(oauth={'type': 'oauth2'})),
    ('invalid-component-key', ALL, 'invalid', 'schema', 'component keys must match ^[a-zA-Z0-9.\\-_]+$', 'components-object',
     lambda d, v: d['components']['schemas'].update({'Pet Owner': {'type': 'object'}})),
    ('invalid-unknown-root-field', ALL, 'invalid', 'schema', 'the OpenAPI Object allows no fields beyond the spec and x- extensions', 'openapi-object',
     lambda d, v: d.update(definitions={})),
    ('invalid-schema-type', ALL, 'invalid', 'schema', 'a Schema Object type must be a JSON Schema type name', 'schema-object',
     lambda d, v: d['components']['schemas']['Pet']['properties']['name'].update(type='strng')),
    ('invalid-missing-responses', ['3.0.4'], 'invalid', 'schema', 'in 3.0 every operation requires responses', 'operation-object',
     lambda d, v: P(d)['post'].pop('responses')),
    ('invalid-webhooks-in-3-0', ['3.0.4'], 'invalid', 'schema', 'webhooks does not exist in 3.0', 'openapi-object',
     lambda d, v: d.update(webhooks={})),
    ('invalid-type-null-in-3-0', ['3.0.4'], 'invalid', 'schema', 'in 3.0 a schema type cannot be "null" or an array', 'schema-object',
     lambda d, v: d['components']['schemas']['Pet']['properties']['name'].update(type=['string', 'null'])),
    ('invalid-no-paths-3-0', ['3.0.4'], 'invalid', 'schema', 'in 3.0 paths is required', 'openapi-object', lambda d, v: d.pop('paths')),
    ('invalid-empty-document-3-1', V31UP, 'invalid', 'schema', 'from 3.1 a document needs at least one of paths, components or webhooks', 'openapi-object',
     lambda d, v: drop(d, 'paths', 'components')),
    ('invalid-query-method-before-3-2', ['3.1.1'], 'invalid', 'schema', 'the query operation does not exist before 3.2', 'path-item-object',
     lambda d, v: P(d).update(query={'responses': {'200': {'description': 'ok'}}})),
    ('invalid-additional-operations-standard-method', V32, 'invalid', 'schema', 'additionalOperations must not repeat a method that has a fixed field (GET)', 'path-item-object',
     lambda d, v: I(d).update(additionalOperations={'GET': {'responses': {'200': {'description': 'ok'}}}})),

    # ---- invalid: only the spec's prose decides
    ('invalid-duplicate-operation-id', ALL, 'invalid', 'semantic', 'operationId must be unique among all operations', 'operation-object',
     lambda d, v: P(d)['post'].update(operationId='listPets')),
    ('invalid-undeclared-path-param', ALL, 'invalid', 'semantic', 'every template expression in a path must have a matching path parameter', 'path-templating',
     lambda d, v: I(d).pop('parameters')),
    ('invalid-path-param-not-in-template', ALL, 'invalid', 'semantic', 'a path parameter must correspond to a template expression in the path', 'parameter-object',
     lambda d, v: I(d)['parameters'].append({'name': 'ownerId', 'in': 'path', 'required': True, 'schema': {'type': 'string'}})),
    ('invalid-duplicate-parameter', ALL, 'invalid', 'semantic', 'a parameter list must not hold two parameters with the same name and location', 'operation-object',
     lambda d, v: P(d)['get']['parameters'].append({'name': 'limit', 'in': 'query', 'schema': {'type': 'string'}})),
    ('invalid-equivalent-templated-paths', ALL, 'invalid', 'semantic', 'templated paths with the same hierarchy but different names are identical and must not both exist', 'paths-object',
     lambda d, v: d['paths'].update({'/pets/{id}': {'parameters': [{'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'string'}}],
                                                    'delete': {'operationId': 'deletePet', 'responses': {'204': {'description': 'gone'}}}}})),
    ('invalid-unresolved-ref', ALL, 'invalid', 'semantic', 'a $ref must resolve', 'reference-object',
     lambda d, v: P(d)['post']['requestBody']['content']['application/json']['schema'].update({'$ref': '#/components/schemas/Owner'})),
    ('invalid-undefined-security-scheme', ALL, 'invalid', 'semantic', 'a security requirement must name a scheme declared in components', 'security-requirement-object',
     lambda d, v: I(d)['get'].update(security=[{'bearerAuth': []}])),
    ('invalid-duplicate-tag-name', ALL, 'invalid', 'semantic', 'tag names must be unique', 'openapi-object',
     lambda d, v: d['tags'].append({'name': 'pets', 'description': 'again'})),
    ('invalid-server-variable-default-not-in-enum', ALL, 'invalid', 'semantic', 'a server variable default must be one of its enum values', 'server-variable-object',
     lambda d, v: d.update(servers=[{'url': 'https://{env}.example.com', 'variables': {'env': {'default': 'qa', 'enum': ['prod', 'staging']}}}])),
    ('invalid-link-unknown-operation', ALL, 'invalid', 'semantic', 'a link operationId must name an existing operation', 'link-object',
     lambda d, v: P(d)['post']['responses']['201'].update(links={'pet': {'operationId': 'fetchPet', 'parameters': {'petId': '$response.body#/id'}}})),
    ('invalid-tag-parent-unknown', V32, 'invalid', 'semantic', 'a tag parent must name a tag that exists', 'tag-object',
     lambda d, v: d['tags'][0].update(parent='animals')),
    ('invalid-tag-parent-cycle', V32, 'invalid', 'semantic', 'tag parents must not form a cycle', 'tag-object',
     lambda d, v: d['tags'][0].update(parent='animals') or d['tags'].append({'name': 'animals', 'parent': 'pets'})),
]

def main():
    for v in VERSIONS:
        out = os.path.join(OUT, v); os.makedirs(out, exist_ok=True)
        for f in os.listdir(out): os.remove(os.path.join(out, f))
        manifest = []
        for cid, versions, expect, level, rule, anchor, mutate in CASES:
            if v not in versions: continue
            d = copy.deepcopy(base(v)); mutate(d, v)
            fn = f'{cid}.openapi.yaml'
            yaml.safe_dump(d, open(os.path.join(out, fn), 'w'), sort_keys=False, allow_unicode=True)
            m = {'id': f'ae-{v}-{cid}', 'file': fn, 'version': v, 'expect': expect, 'level': LEVEL.get((cid, v), level), 'rule': rule, 'spec': f'{SPEC[v]}#{anchor}'}
            if (cid, v) in NOTES: m['note'] = NOTES[(cid, v)]
            manifest.append(m)
        yaml.safe_dump({'cases': manifest}, open(os.path.join(out, 'manifest.yml'), 'w'), sort_keys=False, width=200)
        print(v, len(manifest), 'cases')

if __name__ == '__main__':
    main()

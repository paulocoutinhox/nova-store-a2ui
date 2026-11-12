import test from 'node:test';
import assert from 'node:assert/strict';
import { BASIC_CATALOG_ID, buildAction, getPath, parseA2UI, resolveDynamic, setPath } from '../src/lib/a2ui.js';

const envelope = {
  version: '1.0',
  createSurface: {
    surfaceId: 'surface_123', catalogId: BASIC_CATALOG_ID,
    components: [
      { id: 'root', component: 'Column', children: ['name', 'submit'] },
      { id: 'name', component: 'TextField', label: 'Nome', value: { '@path': '/form/name' } },
      { id: 'submit', component: 'Button', child: 'name', action: { event: { name: 'place_order', context: { name: { '@path': '/form/name' } } } } },
    ],
    dataModel: { form: { name: 'Joana' } },
  },
};

test('parses A2UI 1.0 basic catalog with isolated surface data', () => {
  const [surface] = parseA2UI([envelope]);
  assert.equal(surface.id, 'surface_123');
  assert.equal(surface.components.get('submit').component, 'Button');
  assert.equal(getPath(surface.data, '/form/name'), 'Joana');
});

test('action is structured, preserves bound form values and NEVER fabricates userMessage', () => {
  const original = envelope.createSurface.dataModel;
  const edited = setPath(original, '/form/name', 'Maria');
  assert.equal(original.form.name, 'Joana');
  const event = buildAction('surface_123', 'submit', envelope.createSurface.components[2].action.event, edited);
  assert.equal(event.version, '1.0');
  assert.equal(event.action.name, 'place_order');
  assert.equal(event.action.context.name, 'Maria');
  assert.equal(Object.hasOwn(event.action, 'userMessage'), false);
});

test('rejects unsupported catalogs and dangerous paths', () => {
  assert.throws(() => parseA2UI([{ ...envelope, version: 'v1.0' }]));
  assert.throws(() => parseA2UI([{ ...envelope, createSurface: { ...envelope.createSurface, catalogId: 'other' } }]));
  assert.throws(() => setPath({}, '/__proto__/isAdmin', true));
  assert.equal(getPath({}, '/constructor'), undefined);
  assert.deepEqual(resolveDynamic({ test: { '@path': '/form/name' } }, envelope.createSurface.dataModel), { test: 'Joana' });
});

test('the real Python-generated product and checkout A2UI surfaces parse in React', async () => {
  const fs = await import('node:fs/promises');
  for (const name of ['product', 'checkout']) {
    const url = new URL(`./fixtures/${name}.json`, import.meta.url);
    const wires = JSON.parse(await fs.readFile(url, 'utf8'));
    const [surface] = parseA2UI(wires);
    assert.ok(surface.components.has('root'));
    assert.ok(surface.components.size > 5);
    const buttons = [...surface.components.values()].filter(node => node.component === 'Button');
    assert.ok(buttons.length > 0);
    assert.ok(buttons.every(node => node.action?.event && !('userMessage' in node.action.event)));
  }
});

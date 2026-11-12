/**
 * Small, strict React implementation of the A2UI 1.0 Basic Catalog subset used
 * by this storefront. A2UI is a wire protocol, not a CSS component library.
 * All user gestures are returned as A2UI `action` events, never chat messages.
 */
export const BASIC_CATALOG_ID = 'https://a2ui.org/specification/v1_0/catalogs/basic/catalog.json';
const ALLOWED = new Set(['Column', 'Row', 'Card', 'Image', 'Text', 'Button', 'TextField', 'ChoicePicker']);
const FORBIDDEN = new Set(['__proto__', 'prototype', 'constructor']);

export function parseA2UI(messages) {
  if (!Array.isArray(messages) || messages.length === 0) throw new Error('Empty A2UI message stream.');
  const surfaces = new Map();
  for (const wire of messages) {
    if (!wire || wire.version !== '1.0') throw new Error('Expected A2UI protocol 1.0.');
    const types = ['createSurface', 'updateComponents', 'updateDataModel', 'deleteSurface'].filter(type => type in wire);
    if (types.length !== 1) throw new Error('Invalid A2UI message envelope.');
    const kind = types[0];
    const data = wire[kind];
    if (!data || typeof data.surfaceId !== 'string') throw new Error('Missing A2UI surface ID.');
    if (kind === 'deleteSurface') { surfaces.delete(data.surfaceId); continue; }
    if (kind === 'createSurface') {
      if (data.catalogId !== BASIC_CATALOG_ID) throw new Error('Unsupported A2UI catalog.');
      surfaces.set(data.surfaceId, {
        id: data.surfaceId,
        components: new Map(),
        data: data.dataModel ?? {},
      });
    }
    const surface = surfaces.get(data.surfaceId);
    if (!surface) throw new Error('A2UI surface referenced before creation.');
    if (kind === 'createSurface' || kind === 'updateComponents') {
      for (const component of data.components ?? []) {
        if (!component || typeof component.id !== 'string' || !ALLOWED.has(component.component)) {
          throw new Error('Unsupported A2UI component.');
        }
        surface.components.set(component.id, component);
      }
    }
    if (kind === 'updateDataModel') {
      if (!data.dataModel || typeof data.dataModel !== 'object') throw new Error('Invalid A2UI data model.');
      surface.data = { ...surface.data, ...data.dataModel };
    }
  }
  return [...surfaces.values()];
}

export function getPath(data, pointer) {
  if (typeof pointer !== 'string' || !pointer.startsWith('/')) return undefined;
  let value = data;
  for (const token of pointer.slice(1).split('/').map(part => part.replace(/~1/g, '/').replace(/~0/g, '~'))) {
    if (FORBIDDEN.has(token) || value === null || typeof value !== 'object') return undefined;
    value = Object.hasOwn(value, token) ? value[token] : undefined;
  }
  return value;
}

export function setPath(data, pointer, value) {
  if (typeof pointer !== 'string' || !pointer.startsWith('/')) throw new Error('Invalid bound data path.');
  const parts = pointer.slice(1).split('/').map(part => part.replace(/~1/g, '/').replace(/~0/g, '~'));
  if (parts.some(part => FORBIDDEN.has(part))) throw new Error('Unsafe A2UI data path.');
  const root = structuredClone(data);
  let current = root;
  parts.slice(0, -1).forEach(part => {
    if (!current[part] || typeof current[part] !== 'object') current[part] = {};
    current = current[part];
  });
  current[parts.at(-1)] = value;
  return root;
}

export function resolveDynamic(input, data) {
  if (Array.isArray(input)) return input.map(value => resolveDynamic(value, data));
  if (input && typeof input === 'object') {
    if (Object.keys(input).length === 1 && Object.hasOwn(input, '@path')) {
      return getPath(data, input['@path']);
    }
    return Object.fromEntries(Object.entries(input).map(([key, value]) => [key, resolveDynamic(value, data)]));
  }
  return input;
}

export function buildAction(surfaceId, sourceComponentId, action, data) {
  if (!action || typeof action.name !== 'string') throw new Error('Invalid A2UI action.');
  return {
    version: '1.0',
    action: {
      surfaceId,
      sourceComponentId,
      timestamp: new Date().toISOString(),
      name: action.name,
      context: resolveDynamic(action.context ?? {}, data),
    },
  };
}

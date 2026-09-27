import { normalizeLightingState, buildLightingMaterialIndex, LIGHTING_MATERIAL_NAMES, resolveLightingScene } from './LightingController';

test('keeps only lighting capabilities declared by the verified asset', () => {
  expect(normalizeLightingState({
    headlights: true,
    drl: true,
    taillights: true,
    fog_lights: true,
    left_indicator: true,
    right_indicator: true,
    hazard: true,
    interior: true,
  }, ['headlights', 'hazard'])).toEqual({
    headlights: true,
    drl: false,
    taillights: false,
    fog_lights: false,
    left_indicator: false,
    right_indicator: false,
    hazard: true,
    interior: false,
  });
});

test('rejects malformed capability lists without enabling lighting', () => {
  expect(normalizeLightingState({ headlights: true, hazard: true }, null)).toEqual({
    headlights: false,
    drl: false,
    taillights: false,
    fog_lights: false,
    left_indicator: false,
    right_indicator: false,
    hazard: false,
    interior: false,
  });
});

test('indexes only verified lighting material names', () => {
  const headlight = { name: LIGHTING_MATERIAL_NAMES.HEADLIGHT, emissive: {} };
  const unknown = { name: 'MAT_UNKNOWN', emissive: {} };
  const traversed = [];
  const scene = {
    traverse(callback) {
      const nodes = [
        { isMesh: true, material: headlight },
        { isMesh: true, material: [unknown] },
      ];
      nodes.forEach((node) => { traversed.push(node); callback(node); });
    },
  };

  const index = buildLightingMaterialIndex(scene);
  expect(traversed).toHaveLength(2);
  expect(index.get(LIGHTING_MATERIAL_NAMES.HEADLIGHT)).toEqual([headlight]);
  expect(index.has('MAT_UNKNOWN')).toBe(false);
});

test('resolves a mounted scene from a ref after the React commit', () => {
  const mountedScene = { traverse: () => {} };
  expect(resolveLightingScene({ current: mountedScene })).toBe(mountedScene);
  expect(resolveLightingScene({ current: null })).toBeNull();
  expect(resolveLightingScene(mountedScene)).toBe(mountedScene);
});

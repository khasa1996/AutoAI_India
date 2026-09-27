import { applyRuntimeInteriorMaterials, buildVehicleRuntimeState, buildRuntimeNodeIndex, buildRuntimeMaterialIndex, resolveRuntimeAsset, resolveRuntimeMeshNodes, resolveRuntimeMeshSelection } from './vehicleRuntime';

test('builds a runtime state from verified manifest capabilities', () => {
  expect(buildVehicleRuntimeState({
    supportedInteractions: ['doors', 'bogus'],
    cameraPresetNames: ['exterior', 'rear'],
    paintMaterialNames: ['BodyPaint'],
    interiorMaterialNames: ['Leather'],
    interiorMaterialMappings: { leather_black: ['Leather'] },
    wheelMeshNames: { sport: 'WheelSport' },
    optionMeshNames: { roof_black: ['RoofBlack'] },
  })).toEqual({
    supportedInteractions: ['doors'],
    cameraPresetNames: ['exterior', 'rear'],
    paintMaterialNames: ['BodyPaint'],
    interiorMaterialNames: ['Leather'],
    interiorMaterialMappings: { leather_black: ['Leather'] },
    wheelMeshNames: { sport: 'WheelSport' },
    optionMeshNames: { roof_black: ['RoofBlack'] },
    interactionAnimationNames: {},
  });
});

test('does not synthesize fallback animation names when a verified mapping is absent', () => {
  expect(buildVehicleRuntimeState({
    supportedInteractions: ['doors'],
    interactionAnimationNames: {},
  }).interactionAnimationNames).toEqual({});
});

test('does not activate unsupported interaction animations', () => {
  expect(buildVehicleRuntimeState({
    supportedInteractions: ['doors'],
    interactionAnimationNames: {
      doors: { front_left_open: 'DoorFL_Open' },
      hood: { open: 'Hood_Open' },
    },
  }).interactionAnimationNames).toEqual({
    doors: { front_left_open: 'DoorFL_Open' },
  });
});

test('indexes scene nodes once and resolves only manifest-declared mesh selections', () => {
  const body = { name: 'Body', isMesh: true };
  const sportWheel = { name: 'WheelSport', isMesh: true };
  const blackRoof = { name: 'RoofBlack', isMesh: true };
  const undeclared = { name: 'SecretNode', isMesh: true };
  const traversed = [];
  const scene = {
    traverse(callback) {
      [body, sportWheel, blackRoof, undeclared].forEach((node) => {
        traversed.push(node.name);
        callback(node);
      });
    },
  };

  const index = buildRuntimeNodeIndex(scene);

  expect(traversed).toHaveLength(4);
  expect(resolveRuntimeMeshNodes(index, { sport: 'WheelSport' }, 'sport')).toEqual([sportWheel]);
  expect(resolveRuntimeMeshNodes(index, { sport: 'WheelSport' }, 'unknown')).toEqual([]);
  expect(resolveRuntimeMeshNodes(index, { roof_black: ['RoofBlack'] }, 'roof_black')).toEqual([blackRoof]);
  expect(resolveRuntimeMeshNodes(index, { secret: ['SecretNode'] }, 'secret')).toEqual([undeclared]);
});

test('does not treat an invalid or missing mesh selection as a valid mapped group', () => {
  const index = new Map([
    ['WheelSport', { name: 'WheelSport' }],
  ]);

  expect(resolveRuntimeMeshSelection(index, { sport: 'WheelSport' }, 'unknown')).toEqual({
    matched: false,
    nodes: [],
  });
  expect(resolveRuntimeMeshSelection(index, { missing: 'WheelMissing' }, 'missing')).toEqual({
    matched: false,
    nodes: [],
  });
  expect(resolveRuntimeMeshSelection(index, { sport: 'WheelSport' }, 'sport')).toEqual({
    matched: true,
    nodes: [{ name: 'WheelSport' }],
  });
});

test('uses the verified manifest as the runtime asset contract', () => {
  const asset = resolveRuntimeAsset({
    available: true,
    url: 'https://cdn.example.com/demo-car.glb?token=abc',
    version: '2026-09-14',
    supportedInteractions: ['doors', 'bogus'],
    cameraPresetNames: ['exterior', 'bogus'],
    paintMaterialNames: ['BodyPaint'],
    interiorMaterialNames: ['Leather'],
    interiorMaterialMappings: { leather_black: ['Leather'] },
    wheelMeshNames: { sport: 'WheelSport' },
    optionMeshNames: { roof_black: ['RoofBlack'] },
    interactionAnimationNames: {
      doors: { front_left_open: 'DoorFL_Open', rear_left_open: 'MissingClip' },
    },
  });

  expect(asset).toMatchObject({
    url: 'https://cdn.example.com/demo-car.glb?token=abc',
    version: '2026-09-14',
    supportedInteractions: ['doors'],
    cameraPresetNames: ['exterior'],
    paintMaterialNames: ['BodyPaint'],
    interiorMaterialNames: ['Leather'],
    interiorMaterialMappings: { leather_black: ['Leather'] },
    wheelMeshNames: { sport: 'WheelSport' },
    optionMeshNames: { roof_black: ['RoofBlack'] },
  });
  expect(asset.interactionAnimationNames).toEqual({
    doors: { front_left_open: 'DoorFL_Open', rear_left_open: 'MissingClip' },
  });
});

test('rejects a runtime asset without a verified URL and version', () => {
  expect(resolveRuntimeAsset({ available: true, url: 'https://cdn.example.com/car.png', version: '1' })).toBeNull();
  expect(resolveRuntimeAsset({ available: true, url: 'https://cdn.example.com/car.glb', version: '' })).toBeNull();
});

test('indexes only manifest-declared paint materials for fast color application', () => {
  const bodyMaterial = { name: 'BodyPaint' };
  const glassMaterial = { name: 'Glass' };
  const body = { isMesh: true, material: bodyMaterial };
  const glass = { isMesh: true, material: glassMaterial };
  const scene = {
    traverse(callback) {
      callback(body);
      callback(glass);
    },
  };

  const index = buildRuntimeMaterialIndex(scene, ['BodyPaint']);

  expect(index.get('bodypaint')).toEqual([bodyMaterial]);
  expect(index.has('glass')).toBe(false);
});

test('applies only the selected verified interior material mapping', () => {
  const black = { name: 'LeatherBlack', transparent: false, opacity: 1, depthWrite: true, needsUpdate: false, userData: {} };
  const beige = { name: 'LeatherBeige', transparent: false, opacity: 1, depthWrite: true, needsUpdate: false, userData: {} };
  const materialIndex = new Map([
    ['leatherblack', [black]],
    ['leatherbeige', [beige]],
  ]);

  applyRuntimeInteriorMaterials(
    materialIndex,
    ['LeatherBlack', 'LeatherBeige'],
    { black: ['LeatherBlack'], beige: ['LeatherBeige'] },
    'beige',
  );

  expect(black.opacity).toBe(0);
  expect(black.transparent).toBe(true);
  expect(black.depthWrite).toBe(false);
  expect(beige.opacity).toBe(1);
  expect(beige.transparent).toBe(false);
  expect(beige.depthWrite).toBe(true);

  applyRuntimeInteriorMaterials(
    materialIndex,
    ['LeatherBlack', 'LeatherBeige'],
    { black: ['LeatherBlack'], beige: ['LeatherBeige'] },
    'black',
  );

  expect(black.opacity).toBe(1);
  expect(black.transparent).toBe(false);
  expect(black.depthWrite).toBe(true);
  expect(beige.opacity).toBe(0);
  expect(beige.transparent).toBe(true);
  expect(beige.depthWrite).toBe(false);
});

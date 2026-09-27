import { api } from '../lib/api';
import { gateAssetResponse, normalizeRuntimeCapabilityContract, syncConfiguratorShareUrl, configuratorApi } from './configuratorApi';

describe('gateAssetResponse', () => {
  it('keeps a verified published asset available', () => {
    const response = { available: true, asset: { asset_id: 'asset-1' } };
    expect(gateAssetResponse(response, { ready: true, blockers: [] })).toEqual(response);
  });

  it('hides an asset when production readiness has blockers', () => {
    expect(gateAssetResponse(
      { available: true, asset: { asset_id: 'asset-1' }, status: 'AVAILABLE' },
      { ready: false, blockers: ['3D asset is not published'] },
    )).toEqual({
      available: false,
      asset: null,
      status: 'COMING_SOON',
      readiness_blockers: ['3D asset is not published'],
    });
  });

  it('fails closed when readiness cannot be verified', () => {
    expect(gateAssetResponse(
      { available: true, asset: { asset_id: 'asset-1' }, status: 'AVAILABLE' },
      null,
    )).toEqual({
      available: false,
      asset: null,
      status: 'COMING_SOON',
      readiness_blockers: ['production readiness could not be verified'],
    });
  });
});

describe('normalizeRuntimeCapabilityContract', () => {
  it('maps the backend runtime contract into the existing configurator asset shape', () => {
    const normalized = normalizeRuntimeCapabilityContract({
      variant_id: 'variant-1',
      ready: true,
      blockers: [],
      warnings: [],
      asset: {
        asset_id: 'asset-1',
        revision_id: 'rev-1',
        version: '1.0.0',
        url: 'https://cdn.example/vehicle.glb',
        format: 'glb',
        lod_level: 0,
        provenance: 'AUTO_AI_LICENSED',
        license_name: 'Production license',
        publisher: 'Auto AI India',
        checksum_sha256: 'a'.repeat(64),
        file_size_bytes: 1024,
      },
      capabilities: {
        interactions: ['doors'],
        cameras: ['front'],
        animations: { doors: { open: 'DoorsOpen' } },
        paint_materials: ['BodyPaint'],
        interior_materials: ['InteriorTrim'],
        interior_material_mappings: { black: ['InteriorTrim'] },
        wheel_mesh_mappings: { wheel: 'WheelMesh' },
        option_mesh_mappings: { roof: ['RoofMesh'] },
      },
      options: { colors: [], wheels: [], interiors: [], roofs: [], accessories: [] },
    });

    expect(normalized).toEqual(expect.objectContaining({
      available: true,
      asset_id: 'asset-1',
      revisionId: 'rev-1',
      url: 'https://cdn.example/vehicle.glb',
      version: '1.0.0',
      lodLevel: 0,
      configuratorStatus: 'AVAILABLE',
      supportedInteractions: ['doors'],
      cameraPresetNames: ['front'],
      interactionAnimationNames: { doors: { open: 'DoorsOpen' } },
      paintMaterialNames: ['BodyPaint'],
      interiorMaterialNames: ['InteriorTrim'],
      interiorMaterialMappings: { black: ['InteriorTrim'] },
      wheelMeshNames: { wheel: 'WheelMesh' },
      optionMeshNames: { roof: ['RoofMesh'] },
    }));
  });

  it('fails closed when the runtime contract is not ready', () => {
    expect(normalizeRuntimeCapabilityContract({
      variant_id: 'variant-1',
      ready: false,
      blockers: ['asset is not published'],
      warnings: [],
      asset: null,
      capabilities: null,
      options: null,
    })).toEqual({
      available: false,
      asset: null,
      status: 'COMING_SOON',
      readiness_blockers: ['asset is not published'],
    });
  });
});

describe('syncConfiguratorShareUrl', () => {
  it('adds the opaque share token to the current configurator URL without changing the path', () => {
    const replaceState = jest.spyOn(window.history, 'replaceState').mockImplementation(() => {});
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        href: 'https://autoaiindia.com/configurator/variant-1',
        origin: 'https://autoaiindia.com',
        pathname: '/configurator/variant-1',
      },
    });

    syncConfiguratorShareUrl('opaque-token');

    expect(replaceState).toHaveBeenCalledWith({}, '', 'https://autoaiindia.com/configurator/variant-1?config=opaque-token');
    replaceState.mockRestore();
  });

  it('does nothing when no share token exists', () => {
    const replaceState = jest.spyOn(window.history, 'replaceState').mockImplementation(() => {});
    syncConfiguratorShareUrl('');
    expect(replaceState).not.toHaveBeenCalled();
    replaceState.mockRestore();
  });
});

describe('runtime capability contract requests', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('deduplicates concurrent requests for the same variant contract', async () => {
    const response = {
      data: {
        variant_id: 'variant-1',
        ready: false,
        blockers: ['3D asset is not published'],
        warnings: [],
        asset: null,
        capabilities: null,
        options: null,
      },
    };
    const request = jest.spyOn(api, 'get').mockResolvedValue(response);

    const [availability, asset, options] = await Promise.all([
      configuratorApi.getAvailability('variant-1'),
      configuratorApi.getAsset('variant-1'),
      configuratorApi.getOptions('variant-1'),
    ]);

    expect(request).toHaveBeenCalledTimes(1);
    expect(availability.data.configurator_status).toBe('COMING_SOON');
    expect(asset.data.status).toBe('COMING_SOON');
    expect(options.data.variant_id).toBe('variant-1');
  });
});

/**
 * configuratorApi — backend contract for configurator workflows.
 */

import { api } from "../lib/api";

const V1 = "/v1";
const READINESS_BLOCKER = 'production readiness could not be verified';
const runtimeCapabilityRequests = new Map();

export function gateAssetResponse(assetResponse, readiness) {
  const blockers = Array.isArray(readiness?.blockers)
    ? readiness.blockers.filter((item) => typeof item === 'string' && item.trim())
    : [];
  if (readiness?.ready === true && blockers.length === 0) return assetResponse;
  return { available: false, asset: null, status: 'COMING_SOON', readiness_blockers: blockers.length ? blockers : [READINESS_BLOCKER] };
}

export function normalizeRuntimeCapabilityContract(contract) {
  const blockers = Array.isArray(contract?.blockers)
    ? contract.blockers.filter((item) => typeof item === 'string' && item.trim())
    : [];
  const asset = contract?.asset;
  const capabilities = contract?.capabilities;
  if (contract?.ready !== true || !asset || !capabilities) {
    return {
      available: false,
      asset: null,
      status: 'COMING_SOON',
      readiness_blockers: blockers.length ? blockers : [READINESS_BLOCKER],
    };
  }

  return {
    available: true,
    asset_id: asset.asset_id,
    url: asset.url,
    format: asset.format,
    version: asset.version,
    revisionId: asset.revision_id,
    lodLevel: asset.lod_level,
    provenance: asset.provenance,
    licenseName: asset.license_name,
    publisher: asset.publisher,
    checksumSha256: asset.checksum_sha256,
    fileSizeBytes: asset.file_size_bytes,
    supportedInteractions: capabilities.interactions || [],
    paintMaterialNames: capabilities.paint_materials || [],
    interiorMaterialNames: capabilities.interior_materials || [],
    interiorMaterialMappings: capabilities.interior_material_mappings || {},
    wheelMeshNames: capabilities.wheel_mesh_mappings || {},
    optionMeshNames: capabilities.option_mesh_mappings || {},
    cameraPresetNames: capabilities.cameras || [],
    interactionAnimationNames: capabilities.animations || {},
    configuratorStatus: 'AVAILABLE',
  };
}

function normalizeRuntimeOptions(contract) {
  if (contract?.ready !== true || !contract?.options) {
    return { variant_id: contract?.variant_id, colors: [], wheels: [], interiors: [], roofs: [], accessories: [] };
  }
  return { variant_id: contract.variant_id, ...contract.options };
}

async function fetchRuntimeCapabilityContract(variantId) {
  const inFlight = runtimeCapabilityRequests.get(variantId);
  if (inFlight) return inFlight;

  const request = api.get(`${V1}/configurator/${variantId}/capabilities`)
    .then((response) => ({ ...response, data: response.data }))
    .finally(() => {
      if (runtimeCapabilityRequests.get(variantId) === request) {
        runtimeCapabilityRequests.delete(variantId);
      }
    });

  runtimeCapabilityRequests.set(variantId, request);
  return request;
}

export function syncConfiguratorShareUrl(shareToken) {
  if (!shareToken || typeof window === 'undefined' || !window.history?.replaceState) return;
  const url = new URL(window.location.href);
  url.searchParams.set('config', shareToken);
  window.history.replaceState({}, '', url.toString());
}

export const configuratorApi = {
  getBrands: (activeOnly = true) => api.get(`${V1}/brands`, { params: { active_only: activeOnly } }),
  getModels: (params = {}) => api.get(`${V1}/models`, { params }),
  getModel: (modelId) => api.get(`${V1}/models/${modelId}`),
  getVariants: (params = {}) => api.get(`${V1}/variants`, { params }),
  getVariant: (variantId) => api.get(`${V1}/variants/${variantId}`),
  getAvailability: async (variantId) => {
    const response = await fetchRuntimeCapabilityContract(variantId);
    const normalized = normalizeRuntimeCapabilityContract(response.data);
    return {
      ...response,
      data: {
        variant_id: variantId,
        configurator_status: normalized.available ? 'AVAILABLE' : normalized.status,
        asset_id: normalized.asset_id || null,
        message: normalized.available ? '3D Configurator Available' : '3D Configurator Coming Soon',
        readiness_blockers: normalized.readiness_blockers || [],
      },
    };
  },
  getReadiness: (variantId) => api.get(`${V1}/configurator/variants/${variantId}/readiness`),
  getRuntimeCapabilities: async (variantId) => {
    const response = await fetchRuntimeCapabilityContract(variantId);
    return { ...response, data: normalizeRuntimeCapabilityContract(response.data) };
  },
  getAsset: async (variantId) => {
    const response = await fetchRuntimeCapabilityContract(variantId);
    const normalized = normalizeRuntimeCapabilityContract(response.data);
    return {
      ...response,
      data: normalized.available
        ? { available: true, asset: normalized, status: 'AVAILABLE' }
        : normalized,
    };
  },
  getHotspots: (variantId) => api.get(`${V1}/configurator/${variantId}/hotspots`),
  getOptions: async (variantId) => {
    const response = await fetchRuntimeCapabilityContract(variantId);
    return { ...response, data: normalizeRuntimeOptions(response.data) };
  },
  getRules: (variantId) => api.get(`${V1}/configurator/${variantId}/rules`),
  getPricingLocations: (variantId) => api.get(`${V1}/configurator/${variantId}/pricing-locations`),
  validateConfiguration: (configuration) => api.post(`${V1}/configurator/validate`, { configuration }),
  calculatePrice: (configuration, city = null) => api.post(`${V1}/configurator/price`, { configuration, city }),
  resolveWithAI: (intent) => api.post(`${V1}/configurator/ai`, intent),
  recommendVariants: (request) => api.post(`${V1}/configurator/recommendations`, request),
  calculateEMI: (payload) => api.post('/emi/calculate', payload),
  saveConfiguration: async (payload) => {
    const response = await api.post(`${V1}/configurator/configurations`, payload);
    syncConfiguratorShareUrl(response.data?.share_token);
    return response;
  },
  loadConfiguration: (configIdOrToken) => api.get(`${V1}/configurator/configurations/${configIdOrToken}`),
  getHistory: (limit = 20) => api.get(`${V1}/configurator/history`, { params: { limit } }),
  compareConfigurations: (left, right) => api.post(`${V1}/configurator/compare`, { left, right }),
  createConversionLead: (payload) => api.post(`${V1}/configurator/conversion-lead`, payload),
  createConversionHandoff: (payload, intent) => api.post(`${V1}/configurator/conversion-handoff`, { ...payload, intent }),
  validateAssetUrl: (url) => api.post(`${V1}/configurator/assets/validate-url`, { url }),
};

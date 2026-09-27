/**
 * LightingController — vehicle lighting system for the 3D configurator.
 *
 * Lighting is a SHOWROOM INTERACTION — it does NOT affect vehicle price.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';

export const LIGHTING_MATERIAL_NAMES = {
  HEADLIGHT: 'MAT_HEADLIGHT',
  DRL: 'MAT_DRL',
  TAILLIGHT: 'MAT_TAILLIGHT',
  FOG_LIGHT: 'MAT_FOGLIGHT',
  LEFT_INDICATOR: 'MAT_INDICATOR_L',
  RIGHT_INDICATOR: 'MAT_INDICATOR_R',
  INTERIOR_LIGHT: 'MAT_INTERIOR_LIGHT',
};

const INDICATOR_BLINK_MS = 500;

export function normalizeLightingState(lightingState = {}, supportedInteractions) {
  const supported = new Set(Array.isArray(supportedInteractions) ? supportedInteractions : []);
  const isSupported = (capability) => supported.has(capability);
  return {
    headlights: Boolean(lightingState.headlights && isSupported('headlights')),
    drl: Boolean(lightingState.drl && isSupported('drl')),
    taillights: Boolean(lightingState.taillights && isSupported('taillights')),
    fog_lights: Boolean(lightingState.fog_lights && isSupported('fog_lights')),
    left_indicator: Boolean(lightingState.left_indicator && isSupported('left_indicator')),
    right_indicator: Boolean(lightingState.right_indicator && isSupported('right_indicator')),
    hazard: Boolean(lightingState.hazard && isSupported('hazard')),
    interior: Boolean(lightingState.interior && isSupported('interior_lights')),
  };
}

export function buildLightingMaterialIndex(scene) {
  const index = new Map();
  if (!scene || typeof scene.traverse !== 'function') return index;
  scene.traverse((node) => {
    if (!node?.isMesh) return;
    const materials = Array.isArray(node.material) ? node.material : [node.material];
    materials.forEach((material) => {
      const name = typeof material?.name === 'string' ? material.name.trim().toUpperCase() : '';
      if (!name || !material?.emissive || !Object.values(LIGHTING_MATERIAL_NAMES).includes(name)) return;
      const bucket = index.get(name) || [];
      bucket.push(material);
      index.set(name, bucket);
    });
  });
  return index;
}

export function resolveLightingScene(sceneOrRef) {
  if (sceneOrRef && typeof sceneOrRef === 'object' && 'current' in sceneOrRef) {
    return sceneOrRef.current ?? null;
  }
  return sceneOrRef ?? null;
}

function setMaterialEmissive(materials, on, color = '#ffffff', intensity = 2) {
  if (!Array.isArray(materials)) return;
  materials.forEach((material) => {
    material.emissive.set(on ? color : '#000000');
    material.emissiveIntensity = on ? intensity : 0;
    material.needsUpdate = true;
  });
}

export function useLightingController(sceneOrRef, lightingState, supportedInteractions = []) {
  const headlightRef = useRef(null);
  const taillightRef = useRef(null);
  const indicatorTimerRef = useRef(null);
  const [scene, setScene] = useState(() => resolveLightingScene(sceneOrRef));
  const normalizedLighting = normalizeLightingState(lightingState, supportedInteractions);
  const materialIndex = useMemo(() => buildLightingMaterialIndex(scene), [scene]);

  useEffect(() => {
    setScene(resolveLightingScene(sceneOrRef));
  }, [sceneOrRef]);

  useEffect(() => {
    if (!materialIndex.size) return undefined;
    setMaterialEmissive(materialIndex.get(LIGHTING_MATERIAL_NAMES.HEADLIGHT), normalizedLighting.headlights);
    setMaterialEmissive(materialIndex.get(LIGHTING_MATERIAL_NAMES.DRL), normalizedLighting.drl);
    setMaterialEmissive(materialIndex.get(LIGHTING_MATERIAL_NAMES.TAILLIGHT), normalizedLighting.taillights);
    setMaterialEmissive(materialIndex.get(LIGHTING_MATERIAL_NAMES.FOG_LIGHT), normalizedLighting.fog_lights);
    setMaterialEmissive(materialIndex.get(LIGHTING_MATERIAL_NAMES.INTERIOR_LIGHT), normalizedLighting.interior);
    return undefined;
  }, [materialIndex, normalizedLighting.headlights, normalizedLighting.drl, normalizedLighting.taillights, normalizedLighting.fog_lights, normalizedLighting.interior]);

  useEffect(() => {
    if (!scene) return undefined;
    if (normalizedLighting.headlights && !headlightRef.current) {
      const light = new THREE.PointLight('#ffffee', 3, 8);
      light.position.set(0, 0.6, 2.5);
      scene.add(light);
      headlightRef.current = light;
    } else if (!normalizedLighting.headlights && headlightRef.current) {
      scene.remove(headlightRef.current);
      headlightRef.current = null;
    }
    return undefined;
  }, [scene, normalizedLighting.headlights]);

  useEffect(() => {
    if (!scene) return undefined;
    if (normalizedLighting.taillights && !taillightRef.current) {
      const light = new THREE.PointLight('#ff2200', 1.5, 4);
      light.position.set(0, 0.5, -2.5);
      scene.add(light);
      taillightRef.current = light;
    } else if (!normalizedLighting.taillights && taillightRef.current) {
      scene.remove(taillightRef.current);
      taillightRef.current = null;
    }
    return undefined;
  }, [scene, normalizedLighting.taillights]);

  useEffect(() => {
    if (!scene) return undefined;
    const leftOn = normalizedLighting.left_indicator || normalizedLighting.hazard;
    const rightOn = normalizedLighting.right_indicator || normalizedLighting.hazard;
    clearInterval(indicatorTimerRef.current);
    indicatorTimerRef.current = null;
    setMaterialEmissive(materialIndex.get(LIGHTING_MATERIAL_NAMES.LEFT_INDICATOR), false, '#ffaa00', 3);
    setMaterialEmissive(materialIndex.get(LIGHTING_MATERIAL_NAMES.RIGHT_INDICATOR), false, '#ffaa00', 3);
    if (!leftOn && !rightOn) return undefined;
    let blink = false;
    indicatorTimerRef.current = setInterval(() => {
      blink = !blink;
      if (leftOn) setMaterialEmissive(materialIndex.get(LIGHTING_MATERIAL_NAMES.LEFT_INDICATOR), blink, '#ffaa00', 3);
      if (rightOn) setMaterialEmissive(materialIndex.get(LIGHTING_MATERIAL_NAMES.RIGHT_INDICATOR), blink, '#ffaa00', 3);
    }, INDICATOR_BLINK_MS);
    return () => {
      clearInterval(indicatorTimerRef.current);
      indicatorTimerRef.current = null;
    };
  }, [scene, materialIndex, normalizedLighting.left_indicator, normalizedLighting.right_indicator, normalizedLighting.hazard]);

  useEffect(() => () => {
    clearInterval(indicatorTimerRef.current);
    indicatorTimerRef.current = null;
    if (scene && headlightRef.current) scene.remove(headlightRef.current);
    if (scene && taillightRef.current) scene.remove(taillightRef.current);
    headlightRef.current = null;
    taillightRef.current = null;
  }, [scene]);
}

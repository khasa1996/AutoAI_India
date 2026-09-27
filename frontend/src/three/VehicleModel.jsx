/**
 * VehicleModel — GLB/GLTF loader with semantic material and animation systems.
 *
 * The viewer receives the complete verified asset manifest. No synthetic runtime
 * asset is created here, so the runtime cannot silently bypass asset validation.
 */

import { useEffect, useMemo, useRef } from 'react';
import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import { useVehicleAnimations } from './AnimationController';
import { collectOwnedMaterialResources, disposeOwnedMaterialResources, markRuntimeOwnedMaterials } from './runtimeLifecycle';
import { applyRuntimeMeshVisibility, applyRuntimeInteriorMaterials, canRenderLoadedRuntime, resolveRuntimeAsset, buildRuntimeNodeIndex, buildRuntimeMaterialIndex } from './vehicleRuntime';
import { projectVerifiedVisualConfiguration } from '../components/configurator/runtimeVisualConfiguration';

function applyPaintColor(materialIndex, colorHex, paintMaterialNames) {
  if (!(materialIndex instanceof Map) || !colorHex || !paintMaterialNames?.length) return;
  let color;
  try { color = new THREE.Color(colorHex); } catch { return; }
  if (!Number.isFinite(color.r) || !Number.isFinite(color.g) || !Number.isFinite(color.b)) return;
  paintMaterialNames.forEach((name) => {
    const materials = materialIndex.get(name.trim().toLowerCase()) || [];
    materials.forEach((material) => { material.color.copy(color); material.needsUpdate = true; });
  });
}

function normalizeWheelMappings(wheelMeshNames) {
  return Object.fromEntries(Object.entries(wheelMeshNames || {}).map(([optionId, meshName]) => [optionId, [meshName]]));
}

function LoadedVehicle({ asset, runtime, purchasable, interaction }) {
  const { scene, animations } = useGLTF(asset.url);
  const groupRef = useRef();
  const previousInteractionRef = useRef(null);
  const visualConfiguration = useMemo(
    () => projectVerifiedVisualConfiguration(purchasable, runtime),
    [purchasable, runtime],
  );
  const clonedScene = useMemo(() => {
    const clone = scene.clone(true);
    const meshes = [];
    clone.traverse((node) => {
      if (!node.isMesh) return;
      node.material = Array.isArray(node.material)
        ? node.material.map((material) => material.clone())
        : node.material.clone();
      meshes.push(node);
    });
    markRuntimeOwnedMaterials(meshes);
    return clone;
  }, [scene]);
  const ownedMaterials = useMemo(() => {
    const meshes = [];
    clonedScene.traverse((node) => { if (node.isMesh) meshes.push(node); });
    return collectOwnedMaterialResources(meshes);
  }, [clonedScene]);
  const runtimeNodeIndex = useMemo(() => buildRuntimeNodeIndex(clonedScene), [clonedScene]);
  const runtimeMaterialIndex = useMemo(() => buildRuntimeMaterialIndex(clonedScene, [...runtime.paintMaterialNames, ...runtime.interiorMaterialNames]), [clonedScene, runtime.paintMaterialNames, runtime.interiorMaterialNames]);
  const loadedRuntimeValid = useMemo(() => canRenderLoadedRuntime(runtime, clonedScene, animations), [runtime, clonedScene, animations]);
  const { play, verifiedAnimationMappings } = useVehicleAnimations(animations, groupRef, runtime.interactionAnimationNames);

  useEffect(() => applyPaintColor(runtimeMaterialIndex, asset.paintColorHex, runtime.paintMaterialNames), [asset.paintColorHex, runtime.paintMaterialNames, runtimeMaterialIndex]);
  useEffect(() => {
    applyRuntimeMeshVisibility(runtimeNodeIndex, [visualConfiguration.wheelId], normalizeWheelMappings(runtime.wheelMeshNames));
    applyRuntimeMeshVisibility(
      runtimeNodeIndex,
      [visualConfiguration.roofId, ...visualConfiguration.accessoryIds],
      runtime.optionMeshNames,
    );
    applyRuntimeInteriorMaterials(
      runtimeMaterialIndex,
      runtime.interiorMaterialNames,
      runtime.interiorMaterialMappings,
      visualConfiguration.interiorId,
    );
  }, [visualConfiguration, runtime.optionMeshNames, runtime.wheelMeshNames, runtime.interiorMaterialNames, runtime.interiorMaterialMappings, runtimeMaterialIndex, runtimeNodeIndex]);

  useEffect(() => {
    const previous = previousInteractionRef.current;
    previousInteractionRef.current = interaction;
    if (!previous) return;
    const supported = new Set(runtime.supportedInteractions);
    const playToggle = (capability, current, before, group, openKey, closeKey) => {
      if (!supported.has(capability) || current === before) return;
      const mapping = verifiedAnimationMappings?.[group];
      const requestedKey = current ? openKey : closeKey;
      const fallback = current ? openFallback : closeFallback;
      const animationName = mapping?.[requestedKey] || null;
      if (animationName) play(animationName);
    };
    playToggle('doors', interaction.doors.frontLeft, previous.doors.frontLeft, 'doors', 'front_left_open', 'front_left_close');
    playToggle('doors', interaction.doors.frontRight, previous.doors.frontRight, 'doors', 'front_right_open', 'front_right_close');
    playToggle('doors', interaction.doors.rearLeft, previous.doors.rearLeft, 'doors', 'rear_left_open', 'rear_left_close');
    playToggle('doors', interaction.doors.rearRight, previous.doors.rearRight, 'doors', 'rear_right_open', 'rear_right_close');
    playToggle('hood', interaction.hoodOpen, previous.hoodOpen, 'hood', 'open', 'close');
    playToggle('boot', interaction.bootOpen, previous.bootOpen, 'boot', 'open', 'close');
    playToggle('frunk', interaction.frunkOpen, previous.frunkOpen, 'frunk', 'open', 'close');
    playToggle('sunroof', interaction.sunroofOpen, previous.sunroofOpen, 'sunroof', 'open', 'close');
  }, [interaction, play, runtime, verifiedAnimationMappings]);

  useEffect(() => () => disposeOwnedMaterialResources(ownedMaterials), [ownedMaterials]);

  if (!loadedRuntimeValid) {
    console.error('[VehicleModel] Loaded GLB does not satisfy its verified runtime manifest.');
    return null;
  }

  return <primitive ref={groupRef} object={clonedScene} />;
}

export default function VehicleModel({ asset, purchasable, interaction }) {
  const runtimeAsset = useMemo(() => resolveRuntimeAsset(asset), [asset]);
  if (!runtimeAsset) {
    console.error('[VehicleModel] Rejected unavailable or invalid verified runtime asset.');
    return null;
  }
  return <LoadedVehicle asset={runtimeAsset} runtime={runtimeAsset} purchasable={purchasable} interaction={interaction} />;
}

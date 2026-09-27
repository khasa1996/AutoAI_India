/**
 * CameraPresets — named camera positions for the configurator.
 *
 * Auto-rotation pauses when the user interacts (orbit drag/pinch).
 * Desktop: mouse orbit, scroll zoom, pan.
 * Mobile: one-finger orbit, pinch zoom and pan gestures supported by OrbitControls.
 */

import { useEffect, useRef } from "react";
import { OrbitControls } from "@react-three/drei";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";

export const CAMERA_PRESETS = {
  exterior: { position: [4.5, 1.6, 5.5], target: [0, 0.3, 0] },
  front: { position: [0, 1.2, 5.5], target: [0, 0.5, 0] },
  rear: { position: [0, 1.2, -5.5], target: [0, 0.5, 0] },
  left: { position: [-5.5, 1.2, 0], target: [0, 0.5, 0] },
  right: { position: [5.5, 1.2, 0], target: [0, 0.5, 0] },
  top: { position: [0, 6.0, 0.1], target: [0, 0, 0] },
  interior: { position: [0, 1.1, 0.8], target: [0, 1.0, 0] },
  cockpit: { position: [-0.4, 1.2, 0.5], target: [0, 1.1, -2] },
  boot: { position: [0, 1.2, -4.5], target: [0, 0.6, -2] },
  wheel: { position: [2.2, 0.4, 1.8], target: [1.5, 0.3, 1.5] },
};

export const CAMERA_TRANSITION_DURATION_MS = 650;

export function easeCameraTransition(progress) {
  const value = Math.min(Math.max(progress, 0), 1);
  return value < 0.5
    ? 4 * value * value * value
    : 1 - Math.pow(-2 * value + 2, 3) / 2;
}

export function getCameraTransitionDuration(reducedMotion = false) {
  return reducedMotion ? 0 : CAMERA_TRANSITION_DURATION_MS;
}

export function getConfiguratorControlSettings() {
  return {
    enablePan: true,
    enableDamping: true,
    dampingFactor: 0.08,
    autoRotateSpeed: 0.8,
    minDistance: 2.5,
    maxDistance: 10,
    minPolarAngle: Math.PI / 6,
    maxPolarAngle: Math.PI / 1.9,
    rotateSpeed: 0.7,
  };
}

export function resolveCameraPreset(preset, allowedPresetNames) {
  if (!preset || !CAMERA_PRESETS[preset]) return null;
  if (!Array.isArray(allowedPresetNames) || !allowedPresetNames.includes(preset)) return null;
  return CAMERA_PRESETS[preset];
}

export function useCameraPreset(preset, controlsRef, allowedPresetNames) {
  const { camera } = useThree();

  useEffect(() => {
    const resolvedPreset = resolveCameraPreset(preset, allowedPresetNames);
    if (!resolvedPreset) return undefined;
    const { position, target } = resolvedPreset;
    const targetPos = new THREE.Vector3(...position);
    const targetLook = new THREE.Vector3(...target);
    const startPos = camera.position.clone();
    const startTarget = controlsRef?.current?.target?.clone() || targetLook.clone();
    const reducedMotion = typeof window !== "undefined"
      && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const duration = getCameraTransitionDuration(reducedMotion);
    const startedAt = performance.now();
    let frameId;

    const apply = (progress) => {
      const ease = easeCameraTransition(progress);
      camera.position.lerpVectors(startPos, targetPos, ease);
      if (controlsRef?.current) {
        controlsRef.current.target.lerpVectors(startTarget, targetLook, ease);
        controlsRef.current.update();
      }
    };

    if (duration === 0) {
      apply(1);
      return undefined;
    }

    const animate = (now) => {
      const progress = Math.min((now - startedAt) / duration, 1);
      apply(progress);
      if (progress < 1) frameId = requestAnimationFrame(animate);
    };

    frameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameId);
  }, [allowedPresetNames, camera, controlsRef, preset]);
}

export function ConfiguratorControls({ autoRotate, onInteract, controlsRef }) {
  const internalRef = useRef();
  const resolvedRef = controlsRef || internalRef;
  const settings = getConfiguratorControlSettings();

  return (
    <OrbitControls
      ref={resolvedRef}
      makeDefault
      enablePan={settings.enablePan}
      autoRotate={autoRotate}
      autoRotateSpeed={settings.autoRotateSpeed}
      minDistance={settings.minDistance}
      maxDistance={settings.maxDistance}
      minPolarAngle={settings.minPolarAngle}
      maxPolarAngle={settings.maxPolarAngle}
      rotateSpeed={settings.rotateSpeed}
      enableDamping={settings.enableDamping}
      dampingFactor={settings.dampingFactor}
      onStart={onInteract}
    />
  );
}

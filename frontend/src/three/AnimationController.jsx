/**
 * AnimationController — semantic animation playback for vehicle interactions.
 *
 * Asset manifests may override the default semantic clip names with exact GLB
 * animation names discovered during verified ingestion.
 */

import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useAnimations } from '@react-three/drei';
import { LoopOnce } from 'three';
import { filterAvailableAnimationMappings } from './animationRuntime';

export const ANIMATION_NAMES = {
  DOOR_FL_OPEN: 'Door_FL_Open',
  DOOR_FL_CLOSE: 'Door_FL_Close',
  DOOR_FR_OPEN: 'Door_FR_Open',
  DOOR_FR_CLOSE: 'Door_FR_Close',
  DOOR_RL_OPEN: 'Door_RL_Open',
  DOOR_RL_CLOSE: 'Door_RL_Close',
  DOOR_RR_OPEN: 'Door_RR_Open',
  DOOR_RR_CLOSE: 'Door_RR_Close',
  HOOD_OPEN: 'Hood_Open',
  HOOD_CLOSE: 'Hood_Close',
  BOOT_OPEN: 'Boot_Open',
  BOOT_CLOSE: 'Boot_Close',
  SUNROOF_OPEN: 'Sunroof_Open',
  SUNROOF_CLOSE: 'Sunroof_Close',
  FRUNK_OPEN: 'Frunk_Open',
  FRUNK_CLOSE: 'Frunk_Close',
};

export function resolveAnimationName(animationMappings, group, key, fallbackName) {
  const mapping = animationMappings?.[group];
  const mapped = mapping && typeof mapping === 'object' ? mapping[key] : null;
  return typeof mapped === 'string' && mapped.trim() ? mapped : fallbackName;
}

export function useVehicleAnimations(clips, ref, animationMappings = {}) {
  const { actions, mixer } = useAnimations(clips, ref);
  const playingRef = useRef(new Set());
  const listenersRef = useRef(new Map());

  const availableAnimations = useMemo(() => new Set(Object.keys(actions)), [actions]);
  const verifiedAnimationMappings = useMemo(
    () => filterAvailableAnimationMappings(animationMappings, [...availableAnimations]),
    [animationMappings, availableAnimations],
  );

  const play = useCallback((animationName) => {
    const action = actions[animationName];
    if (!action || !mixer || playingRef.current.has(animationName)) return;

    const onFinished = (event) => {
      if (event.action !== action) return;
      playingRef.current.delete(animationName);
      mixer.removeEventListener('finished', onFinished);
      listenersRef.current.delete(animationName);
    };

    playingRef.current.add(animationName);
    listenersRef.current.set(animationName, onFinished);
    mixer.addEventListener('finished', onFinished);
    action.reset();
    action.setLoop(LoopOnce, 1);
    action.clampWhenFinished = true;
    action.play();
  }, [actions, mixer]);

  useEffect(() => {
    return () => {
      listenersRef.current.forEach((listener) => mixer?.removeEventListener('finished', listener));
      listenersRef.current.clear();
      playingRef.current.clear();
      mixer?.stopAllAction();
    };
  }, [mixer]);

  return { play, availableAnimations, verifiedAnimationMappings };
}

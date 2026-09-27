import {
  CAMERA_PRESETS,
  CAMERA_TRANSITION_DURATION_MS,
  easeCameraTransition,
  getCameraTransitionDuration,
  getConfiguratorControlSettings,
} from './CameraPresets';

describe('camera transitions', () => {
  test('defines every supported camera preset', () => {
    expect(Object.keys(CAMERA_PRESETS)).toEqual(expect.arrayContaining([
      'exterior',
      'front',
      'rear',
      'left',
      'right',
      'top',
      'interior',
      'cockpit',
      'boot',
      'wheel',
    ]));
  });

  test('clamps and eases transition progress', () => {
    expect(easeCameraTransition(-1)).toBe(0);
    expect(easeCameraTransition(0)).toBe(0);
    expect(easeCameraTransition(0.5)).toBe(0.5);
    expect(easeCameraTransition(1)).toBe(1);
    expect(easeCameraTransition(2)).toBe(1);
    expect(easeCameraTransition(0.25)).toBeLessThan(0.25);
    expect(easeCameraTransition(0.75)).toBeGreaterThan(0.75);
  });

  test('uses the cinematic duration unless reduced motion is requested', () => {
    expect(getCameraTransitionDuration()).toBe(CAMERA_TRANSITION_DURATION_MS);
    expect(getCameraTransitionDuration(false)).toBe(650);
    expect(getCameraTransitionDuration(true)).toBe(0);
  });

  test('keeps pan enabled for the Ultra 3D configurator desktop and mobile controls', () => {
    expect(getConfiguratorControlSettings()).toEqual(expect.objectContaining({
      enablePan: true,
      enableDamping: true,
    }));
  });
});

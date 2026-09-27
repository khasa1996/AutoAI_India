import React, { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { ContactShadows, Html, OrbitControls, useGLTF } from "@react-three/drei";
import * as THREE from "three";

const DEMO_ASSET_URL = "https://cdn.3dassets.dev/assets/32487/v1/model.glb";
const DEMO_SOURCE =
  "3DAssets.dev — City car (Car Park and Road Vehicle Fleet), CC0 1.0 Universal";

class DemoCanvasErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error) {
    console.error("Auto-AI demo 3D error", error);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div
        role="alert"
        style={{
          position: "absolute",
          inset: 0,
          display: "grid",
          placeItems: "center",
          padding: 24,
          textAlign: "center",
          background: "radial-gradient(circle at 50% 40%, #171717, #050505 72%)",
          color: "rgba(255,255,255,.72)",
        }}
      >
        <div style={{ maxWidth: 420 }}>
          <div
            style={{
              fontSize: 11,
              letterSpacing: ".18em",
              textTransform: "uppercase",
              color: "#f59e0b",
              marginBottom: 10,
            }}
          >
            3D preview unavailable
          </div>
          <div style={{ fontSize: 14, lineHeight: 1.6 }}>
            The demonstrator page is working, but this browser could not initialize the
            WebGL model. Try Chrome/Edge with hardware acceleration enabled.
          </div>
        </div>
      </div>
    );
  }
}

function DemoVehicle({ paint, animation }) {
  const { scene, animations } = useGLTF(DEMO_ASSET_URL);
  const mixer = useRef(null);
  const [clips, setClips] = useState([]);

  const clone = useMemo(() => {
    const next = scene.clone(true);
    next.traverse((node) => {
      if (!node.isMesh) return;
      node.castShadow = true;
      node.receiveShadow = true;
      if (node.material) {
        node.material = Array.isArray(node.material)
          ? node.material.map((material) => material.clone())
          : node.material.clone();
      }
    });
    return next;
  }, [scene]);

  useEffect(() => {
    setClips(animations.filter((clip) => /door|bonnet|boot/i.test(clip.name)));
    mixer.current?.stopAllAction();
    mixer.current = new THREE.AnimationMixer(clone);
    return () => {
      mixer.current?.stopAllAction();
      mixer.current = null;
    };
  }, [animations, clone]);

  useEffect(() => {
    mixer.current?.stopAllAction();

    const clip = clips.find((item) =>
      item.name.toLowerCase().includes(String(animation || "").toLowerCase()),
    );
    if (!clip || !mixer.current || !animation) return;

    const action = mixer.current.clipAction(clip);
    action.reset();
    action.setLoop(THREE.LoopOnce, 1);
    action.clampWhenFinished = true;
    action.play();

    return () => action.stop();
  }, [animation, clips]);

  useEffect(() => {
    clone.traverse((node) => {
      if (!node.isMesh || !node.material) return;
      const materials = Array.isArray(node.material) ? node.material : [node.material];

      materials.forEach((material) => {
        const name = String(material.name || "").toLowerCase();
        if (
          name.includes("glass") ||
          name.includes("window") ||
          name.includes("tire") ||
          name.includes("tyre") ||
          name.includes("rubber")
        ) {
          return;
        }

        if (material.color) {
          material.color.set(paint);
          material.needsUpdate = true;
        }
      });
    });
  }, [clone, paint]);

  useFrame((_, delta) => {
    mixer.current?.update(delta);
  });

  return <primitive object={clone} />;
}

function Loading() {
  return (
    <Html center>
      <div
        style={{
          padding: "10px 16px",
          borderRadius: 999,
          background: "rgba(0,0,0,.78)",
          border: "1px solid rgba(255,255,255,.12)",
          color: "#fff",
          fontSize: 11,
          letterSpacing: ".14em",
          textTransform: "uppercase",
          whiteSpace: "nowrap",
        }}
      >
        Loading 3D model…
      </div>
    </Html>
  );
}

function DemoScene({ paint, animation, autoRotate }) {
  return (
    <Canvas
      shadows
      dpr={[1, 1.5]}
      camera={{ position: [5, 2.3, 5], fov: 38 }}
      gl={{ antialias: true, powerPreference: "high-performance" }}
      onCreated={({ gl }) => {
        gl.setClearColor("#070707", 1);
      }}
    >
      <ambientLight intensity={0.8} />
      <directionalLight position={[5, 8, 5]} intensity={2.1} castShadow />
      <directionalLight position={[-4, 4, -4]} intensity={0.9} />

      <Suspense fallback={<Loading />}>
        <DemoVehicle paint={paint} animation={animation} />
      </Suspense>

      <ContactShadows
        position={[0, -1, 0]}
        opacity={0.5}
        scale={12}
        blur={2.5}
        far={5}
      />
      <OrbitControls
        enableDamping
        autoRotate={autoRotate}
        autoRotateSpeed={0.8}
        minDistance={2.5}
        maxDistance={12}
      />
    </Canvas>
  );
}

export default function DemoConfigurator() {
  const [paint, setPaint] = useState("#d8d8d8");
  const [animation, setAnimation] = useState("");
  const [autoRotate, setAutoRotate] = useState(true);

  return (
    <main className="autoai-demo-page">
      <style>{`
        .autoai-demo-page {
          min-height: 100vh;
          background: #050505;
          color: #fff;
          padding: 48px 20px 40px;
        }
        .autoai-demo-shell { max-width: 1440px; margin: 0 auto; }
        .autoai-demo-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-end;
          gap: 20px;
          flex-wrap: wrap;
          margin-bottom: 18px;
        }
        .autoai-demo-grid {
          display: grid;
          grid-template-columns: minmax(0, 1fr) 330px;
          gap: 18px;
        }
        .autoai-demo-stage {
          height: min(72vh, 760px);
          min-height: 520px;
          border: 1px solid rgba(255,255,255,.1);
          border-radius: 24px;
          overflow: hidden;
          background: radial-gradient(circle at 50% 35%, #1b1b1b, #070707 70%);
          position: relative;
        }
        .autoai-demo-panel {
          border: 1px solid rgba(255,255,255,.1);
          border-radius: 22px;
          background: #0d0d0d;
          padding: 20px;
          height: fit-content;
        }
        @media (max-width: 900px) {
          .autoai-demo-page { padding: 28px 12px 28px; }
          .autoai-demo-grid { grid-template-columns: 1fr; }
          .autoai-demo-stage { min-height: 56vh; height: 56vh; }
          .autoai-demo-panel { padding: 16px; }
        }
      `}</style>

      <div className="autoai-demo-shell">
        <header className="autoai-demo-header">
          <div>
            <div
              style={{
                fontSize: 10,
                letterSpacing: ".22em",
                textTransform: "uppercase",
                color: "#f59e0b",
              }}
            >
              Auto AI India · 3D Demonstrator
            </div>
            <h1
              style={{
                fontSize: "clamp(30px,4vw,56px)",
                fontWeight: 300,
                margin: "8px 0 4px",
              }}
            >
              Aureon GT
            </h1>
            <p style={{ margin: 0, color: "rgba(255,255,255,.45)", fontSize: 13 }}>
              Concept / Demonstrator · not an OEM vehicle
            </p>
          </div>

          <div
            style={{
              fontSize: 10,
              letterSpacing: ".12em",
              textTransform: "uppercase",
              color: "rgba(255,255,255,.35)",
              textAlign: "right",
            }}
          >
            Licensed generic asset · CC0
            <br />
            No OEM branding or sponsorship implied
          </div>
        </header>

        <div className="autoai-demo-grid">
          <section className="autoai-demo-stage" aria-label="3D vehicle viewer">
            <DemoCanvasErrorBoundary>
              <DemoScene paint={paint} animation={animation} autoRotate={autoRotate} />
            </DemoCanvasErrorBoundary>

            <div
              style={{
                position: "absolute",
                left: 16,
                bottom: 16,
                padding: "8px 12px",
                borderRadius: 999,
                border: "1px solid rgba(255,255,255,.12)",
                background: "rgba(0,0,0,.55)",
                fontSize: 10,
                letterSpacing: ".1em",
                textTransform: "uppercase",
                color: "rgba(255,255,255,.55)",
                pointerEvents: "none",
              }}
            >
              Drag · Orbit · Scroll to zoom
            </div>
          </section>

          <aside className="autoai-demo-panel">
            <div
              style={{
                fontSize: 10,
                letterSpacing: ".18em",
                textTransform: "uppercase",
                color: "#f59e0b",
              }}
            >
              Demo controls
            </div>
            <h2 style={{ fontSize: 22, fontWeight: 400, margin: "8px 0 18px" }}>
              Configure
            </h2>

            <label
              style={{
                display: "block",
                fontSize: 11,
                color: "rgba(255,255,255,.45)",
                marginBottom: 8,
              }}
            >
              Exterior colour
            </label>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(4,1fr)",
                gap: 8,
                marginBottom: 22,
              }}
            >
              {["#d8d8d8", "#111111", "#7f1016", "#123b69"].map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-label={value}
                  onClick={() => setPaint(value)}
                  style={{
                    height: 42,
                    borderRadius: 10,
                    border:
                      paint === value
                        ? "2px solid #f59e0b"
                        : "1px solid rgba(255,255,255,.15)",
                    background: value,
                    cursor: "pointer",
                  }}
                />
              ))}
            </div>

            <label
              style={{
                display: "block",
                fontSize: 11,
                color: "rgba(255,255,255,.45)",
                marginBottom: 8,
              }}
            >
              Body animation
            </label>
            <div style={{ display: "grid", gap: 8 }}>
              {[
                ["", "Reset"],
                ["door", "Doors"],
                ["bonnet", "Bonnet"],
                ["boot", "Boot"],
              ].map(([value, label]) => (
                <button
                  key={value || "reset"}
                  type="button"
                  onClick={() => setAnimation(value)}
                  style={{
                    padding: "11px 12px",
                    borderRadius: 10,
                    border: "1px solid rgba(255,255,255,.12)",
                    background:
                      animation === value
                        ? "rgba(245,158,11,.12)"
                        : "rgba(255,255,255,.03)",
                    color: "#fff",
                    textAlign: "left",
                    cursor: "pointer",
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={() => setAutoRotate((value) => !value)}
              style={{
                marginTop: 16,
                width: "100%",
                padding: "12px",
                borderRadius: 10,
                border: "1px solid rgba(255,255,255,.12)",
                background: "transparent",
                color: "#fff",
                cursor: "pointer",
              }}
            >
              {autoRotate ? "Pause auto rotation" : "Enable auto rotation"}
            </button>

            <div
              style={{
                marginTop: 22,
                paddingTop: 18,
                borderTop: "1px solid rgba(255,255,255,.08)",
                fontSize: 10,
                lineHeight: 1.6,
                color: "rgba(255,255,255,.35)",
              }}
            >
              This demonstrator is intentionally isolated from the authoritative{" "}
              <code>autoai</code> production catalog. It does not create synthetic OEM
              vehicle, pricing, or option records.
            </div>
          </aside>
        </div>

        <p style={{ marginTop: 12, fontSize: 10, color: "rgba(255,255,255,.22)" }}>
          Source: {DEMO_SOURCE}. Asset URL is pinned to the published GLB version.
        </p>
      </div>
    </main>
  );
}

useGLTF.preload(DEMO_ASSET_URL);

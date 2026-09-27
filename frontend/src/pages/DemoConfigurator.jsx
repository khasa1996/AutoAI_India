import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { Bounds, ContactShadows, Environment, Html, OrbitControls, useGLTF } from '@react-three/drei';
import * as THREE from 'three';

const DEMO_ASSET_URL = 'https://cdn.3dassets.dev/assets/32487/v1/model.glb';
const DEMO_SOURCE = '3DAssets.dev — City car (Car Park and Road Vehicle Fleet), CC0 1.0 Universal';

function DemoVehicle({ paint, animation }) {
  const { scene, animations } = useGLTF(DEMO_ASSET_URL);
  const root = useRef();
  const mixer = useRef();
  const [clips, setClips] = useState([]);

  const clone = useMemo(() => {
    const next = scene.clone(true);
    next.traverse((node) => {
      if (!node.isMesh) return;
      node.castShadow = true;
      node.receiveShadow = true;
      node.material = Array.isArray(node.material)
        ? node.material.map((m) => m.clone())
        : node.material.clone();
    });
    return next;
  }, [scene]);

  useEffect(() => {
    setClips(animations.filter((clip) => /door|bonnet|boot/i.test(clip.name)));
    mixer.current?.stopAllAction();
    mixer.current = new THREE.AnimationMixer(clone);
    return () => mixer.current?.stopAllAction();
  }, [animations, clone]);

  useEffect(() => {
    const clip = clips.find((item) => item.name.toLowerCase().includes(String(animation || '').toLowerCase()));
    if (!clip || !mixer.current || !animation) return;
    mixer.current.stopAllAction();
    const action = mixer.current.clipAction(clip);
    action.reset().setLoop(THREE.LoopOnce, 1).clampWhenFinished = true;
    action.play();
    return () => action.stop();
  }, [animation, clips]);

  useEffect(() => {
    clone.traverse((node) => {
      if (!node.isMesh) return;
      const materials = Array.isArray(node.material) ? node.material : [node.material];
      materials.forEach((material) => {
        const name = String(material.name || '').toLowerCase();
        if (name.includes('glass') || name.includes('window') || name.includes('tire') || name.includes('rubber')) return;
        if (material.color) {
          material.color.set(paint);
          material.needsUpdate = true;
        }
      });
    });
  }, [clone, paint]);

  useEffect(() => {
    let frame;
    const tick = () => { mixer.current?.update(1 / 60); frame = requestAnimationFrame(tick); };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, []);

  return <primitive ref={root} object={clone} />;
}

function Loading() {
  return <Html center><div style={{padding:'10px 16px',borderRadius:999,background:'rgba(0,0,0,.75)',color:'#fff',fontSize:11,letterSpacing:'.14em',textTransform:'uppercase'}}>Loading 3D model…</div></Html>;
}

export default function DemoConfigurator() {
  const [paint, setPaint] = useState('#d8d8d8');
  const [animation, setAnimation] = useState('');
  const [autoRotate, setAutoRotate] = useState(true);

  return (
    <main style={{minHeight:'100vh',background:'#050505',color:'#fff',padding:'96px 20px 40px'}}>
      <div style={{maxWidth:1440,margin:'0 auto'}}>
        <div style={{display:'flex',justifyContent:'space-between',gap:20,alignItems:'flex-end',flexWrap:'wrap',marginBottom:18}}>
          <div>
            <div style={{fontSize:10,letterSpacing:'.22em',textTransform:'uppercase',color:'#f59e0b'}}>Auto AI India · 3D Demonstrator</div>
            <h1 style={{fontSize:'clamp(30px,4vw,56px)',fontWeight:300,margin:'8px 0 4px'}}>Aureon GT</h1>
            <p style={{margin:0,color:'rgba(255,255,255,.45)',fontSize:13}}>Concept / Demonstrator · not an OEM vehicle</p>
          </div>
          <div style={{fontSize:10,letterSpacing:'.12em',textTransform:'uppercase',color:'rgba(255,255,255,.35)',textAlign:'right'}}>Licensed generic asset · CC0<br/>No OEM branding or sponsorship implied</div>
        </div>
        <div style={{display:'grid',gridTemplateColumns:'minmax(0,1fr) 330px',gap:18}}>
          <section style={{height:'min(72vh,760px)',minHeight:520,border:'1px solid rgba(255,255,255,.1)',borderRadius:24,overflow:'hidden',background:'radial-gradient(circle at 50% 35%,#1b1b1b,#070707 70%)',position:'relative'}}>
            <Canvas shadows dpr={[1,1.75]} camera={{position:[5,2.3,5],fov:38}}>
              <color attach="background" args={['#070707']} />
              <ambientLight intensity={0.7} />
              <directionalLight position={[5,8,5]} intensity={2.2} castShadow />
              <directionalLight position={[-4,4,-4]} intensity={0.9} />
              <Environment preset="studio" />
              <Bounds fit clip observe margin={1.25}><Suspense fallback={<Loading />}><DemoVehicle paint={paint} animation={animation} /></Suspense></Bounds>
              <ContactShadows position={[0,-1,0]} opacity={0.5} scale={12} blur={2.5} far={5} />
              <OrbitControls enableDamping autoRotate={autoRotate} autoRotateSpeed={0.8} />
            </Canvas>
            <div style={{position:'absolute',left:16,bottom:16,padding:'8px 12px',borderRadius:999,border:'1px solid rgba(255,255,255,.12)',background:'rgba(0,0,0,.55)',fontSize:10,letterSpacing:'.1em',textTransform:'uppercase',color:'rgba(255,255,255,.55)'}}>Drag · Orbit · Scroll to zoom</div>
          </section>
          <aside style={{border:'1px solid rgba(255,255,255,.1)',borderRadius:22,background:'#0d0d0d',padding:20,height:'fit-content'}}>
            <div style={{fontSize:10,letterSpacing:'.18em',textTransform:'uppercase',color:'#f59e0b'}}>Demo controls</div>
            <h2 style={{fontSize:22,fontWeight:400,margin:'8px 0 18px'}}>Configure</h2>
            <label style={{display:'block',fontSize:11,color:'rgba(255,255,255,.45)',marginBottom:8}}>Exterior colour</label>
            <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:8,marginBottom:22}}>
              {['#d8d8d8','#111111','#7f1016','#123b69'].map((value) => <button key={value} type="button" aria-label={value} onClick={() => setPaint(value)} style={{height:42,borderRadius:10,border:paint===value?'2px solid #f59e0b':'1px solid rgba(255,255,255,.15)',background:value,cursor:'pointer'}} />)}
            </div>
            <label style={{display:'block',fontSize:11,color:'rgba(255,255,255,.45)',marginBottom:8}}>Body animation</label>
            <div style={{display:'grid',gap:8}}>
              {[['','Reset'],['door','Doors'],['bonnet','Bonnet'],['boot','Boot']].map(([value,label]) => <button key={value || 'reset'} type="button" onClick={() => setAnimation(value)} style={{padding:'11px 12px',borderRadius:10,border:'1px solid rgba(255,255,255,.12)',background:animation===value?'rgba(245,158,11,.12)':'rgba(255,255,255,.03)',color:'#fff',textAlign:'left',cursor:'pointer'}}>{label}</button>)}
            </div>
            <button type="button" onClick={() => setAutoRotate((v) => !v)} style={{marginTop:16,width:'100%',padding:'12px',borderRadius:10,border:'1px solid rgba(255,255,255,.12)',background:'transparent',color:'#fff',cursor:'pointer'}}>{autoRotate ? 'Pause auto rotation' : 'Enable auto rotation'}</button>
            <div style={{marginTop:22,paddingTop:18,borderTop:'1px solid rgba(255,255,255,.08)',fontSize:10,lineHeight:1.6,color:'rgba(255,255,255,.35)'}}>This demonstrator is intentionally isolated from the authoritative <code>autoai</code> production catalog. It does not create synthetic OEM vehicle, pricing, or option records.</div>
          </aside>
        </div>
        <p style={{marginTop:12,fontSize:10,color:'rgba(255,255,255,.22)'}}>Source: {DEMO_SOURCE}. Asset URL is pinned to the published GLB version.</p>
      </div>
    </main>
  );
}

useGLTF.preload(DEMO_ASSET_URL);

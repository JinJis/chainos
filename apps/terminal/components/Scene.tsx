'use client';

import { Canvas } from '@react-three/fiber';
import { OrbitControls, Stars } from '@react-three/drei';
import type { CompanyNode, FlowEdge } from '../lib/api';
import type { Vec3 } from '../lib/layout';
import { useCanvas } from '../lib/store';
import { Nodes } from './Nodes';
import { Flows } from './Flows';

export function Scene({
  nodes,
  positions,
  edges,
}: {
  nodes: CompanyNode[];
  positions: Map<string, Vec3>;
  edges: FlowEdge[];
}) {
  const select = useCanvas((s) => s.select);
  return (
    <Canvas camera={{ position: [0, 10, 42], fov: 55 }} dpr={[1, 2]} className="canvas-root">
      <color attach="background" args={['#05070d']} />
      <fog attach="fog" args={['#05070d', 45, 110]} />
      <ambientLight intensity={0.65} />
      <pointLight position={[24, 30, 24]} intensity={1.3} />
      <pointLight position={[-30, -10, -20]} intensity={0.5} color="#4da3ff" />
      <Stars radius={140} depth={70} count={2600} factor={4} fade speed={0.4} />
      {/* Clicking empty space clears selection */}
      <mesh onPointerMissed={() => select(null)} visible={false}>
        <boxGeometry args={[0.01, 0.01, 0.01]} />
        <meshBasicMaterial />
      </mesh>
      <Nodes nodes={nodes} positions={positions} />
      <Flows edges={edges} positions={positions} />
      <OrbitControls makeDefault enablePan autoRotate autoRotateSpeed={0.22} minDistance={8} maxDistance={120} />
    </Canvas>
  );
}

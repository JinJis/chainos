'use client';

import { useFrame } from '@react-three/fiber';
import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import type { CompanyNode, PredictPayload } from '../lib/api';
import { nodeRadius, type Vec3 } from '../lib/layout';

const EXPAND = new THREE.Color('#4da3ff');
const CONTRACT = new THREE.Color('#ff5d6c');

/**
 * Predict overlay (Ghost Nodes) — a translucent aurora that expands (blue) around
 * beneficiary nodes and contracts (red) around hurt ones, pulsing. It is a SEPARATE
 * visual layer over the fixed graph and never mutates the underlying Production
 * data (PRD §7 Step 4, CLAUDE.md §6).
 */
export function GhostNodes({
  nodes,
  positions,
  predict,
}: {
  nodes: CompanyNode[];
  positions: Map<string, Vec3>;
  predict: PredictPayload;
}) {
  const groupRef = useRef<THREE.Group>(null);

  const ghosts = useMemo(() => {
    return nodes
      .filter((n) => predict.nodes[n.id])
      .map((n) => {
        const p = predict.nodes[n.id]!;
        return {
          id: n.id,
          pos: positions.get(n.id) ?? ([0, 0, 0] as Vec3),
          base: nodeRadius(n.market_cap),
          ratio: p.expansion_ratio,
          color: p.direction === 'contract' ? CONTRACT : EXPAND,
        };
      });
  }, [nodes, positions, predict]);

  useFrame((state) => {
    const g = groupRef.current;
    if (!g) return;
    const pulse = 0.5 + Math.sin(state.clock.elapsedTime * 2.2) * 0.18;
    g.children.forEach((child, i) => {
      const ghost = ghosts[i];
      if (!ghost) return;
      const mesh = child as THREE.Mesh;
      // Aurora sits just outside the node; size tracks the expansion ratio.
      const target = ghost.base * (0.9 + (ghost.ratio - 1) * 3.2) + 0.6;
      mesh.scale.setScalar(target * (1 + (pulse - 0.5) * 0.18));
      const mat = mesh.material as THREE.MeshBasicMaterial;
      mat.opacity = 0.1 + pulse * 0.22;
    });
  });

  return (
    <group ref={groupRef}>
      {ghosts.map(( g) => (
        <mesh key={g.id} position={g.pos}>
          <sphereGeometry args={[1, 20, 20]} />
          <meshBasicMaterial
            color={g.color}
            transparent
            opacity={0.2}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      ))}
    </group>
  );
}

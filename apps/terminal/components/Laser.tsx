'use client';

import { Line } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useRef } from 'react';
import * as THREE from 'three';
import type { Vec3 } from '../lib/layout';
import { useCanvas } from '../lib/store';

/** Bright neon "laser" from the selected company to the customers a chosen
 * product flows into (PRD §7 Step 3). Pulses to draw the eye. */
export function Laser({ positions }: { positions: Map<string, Vec3> }) {
  const selectedId = useCanvas((s) => s.selectedId);
  const laser = useCanvas((s) => s.laser);
  const groupRef = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (groupRef.current) {
      const pulse = 0.6 + Math.sin(state.clock.elapsedTime * 4) * 0.35;
      groupRef.current.children.forEach((child) => {
        const mat = (child as THREE.Mesh).material as THREE.Material & { opacity: number };
        if (mat) mat.opacity = pulse;
      });
    }
  });

  if (!selectedId || !laser) return null;
  const from = positions.get(selectedId);
  if (!from) return null;

  return (
    <group ref={groupRef}>
      {laser.customers.map((cid) => {
        const to = positions.get(cid);
        if (!to) return null;
        return (
          <Line
            key={cid}
            points={[from, to]}
            color="#46f0c8"
            lineWidth={3}
            transparent
            opacity={0.9}
          />
        );
      })}
    </group>
  );
}

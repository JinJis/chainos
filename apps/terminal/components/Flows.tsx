'use client';

import { useFrame } from '@react-three/fiber';
import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import type { FlowEdge } from '../lib/api';
import type { Vec3 } from '../lib/layout';

const EDGE_COLOR: Record<string, string> = {
  SUPPLIES: '#46f0c8',
  REVENUE_FLOW: '#ffcc66',
  INVESTS_IN: '#4da3ff',
  COMPETES_WITH: '#ff5d6c',
};
const PARTICLES_PER_EDGE = 5;

/** Faint connecting lines + a pool of particles streaming from supplier → customer
 * (the direction product ships and money returns). Particle count scales with the
 * visible edge set; the buffer is rebuilt only when the filtered edges change. */
export function Flows({
  edges,
  positions,
}: {
  edges: FlowEdge[];
  positions: Map<string, Vec3>;
}) {
  const pointsRef = useRef<THREE.Points>(null);

  const { lineGeo, particle } = useMemo(() => {
    const valid = edges.filter((e) => positions.has(e.from) && positions.has(e.to));
    const linePos = new Float32Array(valid.length * 6);
    const lineCol = new Float32Array(valid.length * 6);
    const c = new THREE.Color();
    valid.forEach((e, i) => {
      const a = positions.get(e.from)!;
      const b = positions.get(e.to)!;
      linePos.set([a[0], a[1], a[2], b[0], b[1], b[2]], i * 6);
      c.set(EDGE_COLOR[e.type] ?? '#6f7db0');
      lineCol.set([c.r, c.g, c.b, c.r, c.g, c.b], i * 6);
    });
    const lg = new THREE.BufferGeometry();
    lg.setAttribute('position', new THREE.BufferAttribute(linePos, 3));
    lg.setAttribute('color', new THREE.BufferAttribute(lineCol, 3));

    const count = valid.length * PARTICLES_PER_EDGE;
    const pPos = new Float32Array(count * 3);
    const pCol = new Float32Array(count * 3);
    const ends = new Float32Array(count * 6); // from xyz + to xyz
    const offset = new Float32Array(count);
    let k = 0;
    valid.forEach((e) => {
      const a = positions.get(e.from)!;
      const b = positions.get(e.to)!;
      c.set(EDGE_COLOR[e.type] ?? '#6f7db0');
      for (let j = 0; j < PARTICLES_PER_EDGE; j++) {
        ends.set([a[0], a[1], a[2], b[0], b[1], b[2]], k * 6);
        pCol.set([c.r, c.g, c.b], k * 3);
        offset[k] = j / PARTICLES_PER_EDGE;
        k++;
      }
    });
    return {
      lineGeo: lg,
      particle: { pPos, pCol, ends, offset, count },
    };
  }, [edges, positions]);

  useFrame((state) => {
    const pts = pointsRef.current;
    if (!pts || particle.count === 0) return;
    const t = state.clock.elapsedTime * 0.18;
    const { pPos, ends, offset, count } = particle;
    for (let i = 0; i < count; i++) {
      const frac = (t + offset[i]!) % 1;
      const o = i * 6;
      pPos[i * 3] = ends[o]! + (ends[o + 3]! - ends[o]!) * frac;
      pPos[i * 3 + 1] = ends[o + 1]! + (ends[o + 4]! - ends[o + 1]!) * frac;
      pPos[i * 3 + 2] = ends[o + 2]! + (ends[o + 5]! - ends[o + 2]!) * frac;
    }
    const attr = pts.geometry.getAttribute('position') as THREE.BufferAttribute;
    attr.needsUpdate = true;
  });

  return (
    <group>
      <lineSegments geometry={lineGeo}>
        <lineBasicMaterial vertexColors transparent opacity={0.22} />
      </lineSegments>
      <points ref={pointsRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[particle.pPos, 3]}
            count={particle.count}
          />
          <bufferAttribute
            attach="attributes-color"
            args={[particle.pCol, 3]}
            count={particle.count}
          />
        </bufferGeometry>
        <pointsMaterial
          size={0.34}
          vertexColors
          transparent
          opacity={0.95}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          sizeAttenuation
        />
      </points>
    </group>
  );
}

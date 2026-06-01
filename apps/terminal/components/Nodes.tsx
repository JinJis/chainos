'use client';

import { useFrame, type ThreeEvent } from '@react-three/fiber';
import { Billboard, Text } from '@react-three/drei';
import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import type { CompanyNode } from '../lib/api';
import { nodeColor, nodeRadius, type Vec3 } from '../lib/layout';
import { useCanvas } from '../lib/store';

const dummy = new THREE.Object3D();
const colorObj = new THREE.Color();

/**
 * Company nodes as a single InstancedMesh (size = market cap). The depth slider
 * toggles per-instance VISIBILITY by lerping scale to 0 — instances are never
 * remounted (PRD §6/§9.1). A subtle per-node "breathing" simulates the live feed.
 */
export function Nodes({
  nodes,
  positions,
}: {
  nodes: CompanyNode[];
  positions: Map<string, Vec3>;
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const depth = useCanvas((s) => s.depth);
  const selectedId = useCanvas((s) => s.selectedId);
  const hoveredId = useCanvas((s) => s.hoveredId);
  const select = useCanvas((s) => s.select);
  const hover = useCanvas((s) => s.hover);

  const meta = useMemo(
    () =>
      nodes.map((n) => ({
        id: n.id,
        pos: positions.get(n.id) ?? ([0, 0, 0] as Vec3),
        radius: nodeRadius(n.market_cap),
        color: nodeColor(n),
        tier: n.tier ?? 1,
      })),
    [nodes, positions],
  );
  const scales = useRef<Float32Array>(new Float32Array(nodes.length));

  // Initial colors (set once).
  useMemo(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    meta.forEach((m, i) => {
      mesh.setColorAt(i, colorObj.set(m.color));
    });
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [meta]);

  const labelled = useMemo(() => {
    const ids = new Set<string>();
    meta.forEach((m) => {
      if (m.radius > 1.5) ids.add(m.id); // always label the mega caps
    });
    if (hoveredId) ids.add(hoveredId);
    if (selectedId) ids.add(selectedId);
    return meta.filter((m) => ids.has(m.id) && m.tier <= depth);
  }, [meta, hoveredId, selectedId, depth]);

  useFrame((state) => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const t = state.clock.elapsedTime;
    meta.forEach((m, i) => {
      const visible = m.tier <= depth;
      const breath = 1 + Math.sin(t * 1.4 + i * 1.3) * 0.025; // live "breathing"
      const emphasis = m.id === selectedId ? 1.18 : m.id === hoveredId ? 1.08 : 1;
      const target = visible ? m.radius * breath * emphasis : 0.0001;
      const cur = scales.current[i] ?? target;
      const next = cur + (target - cur) * 0.18; // smooth lerp, no snap
      scales.current[i] = next;
      dummy.position.set(m.pos[0], m.pos[1], m.pos[2]);
      dummy.scale.setScalar(next);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    });
    mesh.instanceMatrix.needsUpdate = true;
  });

  return (
    <group>
      <instancedMesh
        ref={meshRef}
        args={[undefined, undefined, nodes.length]}
        onPointerMove={(e: ThreeEvent<PointerEvent>) => {
          e.stopPropagation();
          const i = e.instanceId;
          if (i != null && meta[i]) hover(meta[i].id);
        }}
        onPointerOut={() => hover(null)}
        onClick={(e: ThreeEvent<MouseEvent>) => {
          e.stopPropagation();
          const i = e.instanceId;
          if (i != null && meta[i]) select(meta[i].id);
        }}
      >
        <sphereGeometry args={[1, 24, 24]} />
        <meshStandardMaterial
          roughness={0.35}
          metalness={0.15}
          emissiveIntensity={0.4}
          vertexColors
        />
      </instancedMesh>

      {labelled.map((m) => {
        const node = nodes.find((n) => n.id === m.id)!;
        return (
          <Billboard key={m.id} position={[m.pos[0], m.pos[1] + m.radius + 0.7, m.pos[2]]}>
            <Text fontSize={0.62} color="#e6ecff" anchorX="center" anchorY="middle" outlineWidth={0.015} outlineColor="#05070d">
              {node.name}
            </Text>
          </Billboard>
        );
      })}
    </group>
  );
}

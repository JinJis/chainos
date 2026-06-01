/**
 * Code generator: emits a Pydantic mirror of the canonical graph spec into the
 * Engine. Run via `pnpm --filter @chainos/graph-schema gen`. The output is
 * checked in and imported by the Engine so both sides share one contract.
 */
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  CONFIDENCE,
  SOURCE_TYPE,
  SUPPLY_DIRECTION,
  TRUST_FIELDS,
  NODE_SPECS,
  EDGE_SPECS,
  FLOW_VIEWS,
  FLOW_VIEW_EDGES,
  type FieldSpec,
  type FieldType,
} from '../src/spec.js';

const PY_KEYWORDS = new Set(['from', 'yield', 'import', 'class', 'in', 'is', 'and', 'or', 'not']);

function pyType(t: FieldType): string {
  switch (t) {
    case 'string':
      return 'str';
    case 'number':
      return 'float';
    case 'int':
      return 'int';
    case 'boolean':
      return 'bool';
    case 'enum:confidence':
      return 'Confidence';
    case 'enum:source_type':
      return 'SourceType';
    case 'enum:supply_direction':
      return 'SupplyDirection';
  }
}

function pyField(name: string, f: FieldSpec): string {
  const safe = PY_KEYWORDS.has(name) ? `${name}_` : name;
  const t = pyType(f.type);
  const needsAlias = safe !== name;
  if (f.optional) {
    const fieldArgs = needsAlias ? `default=None, alias="${name}"` : 'default=None';
    return `    ${safe}: Optional[${t}] = Field(${fieldArgs})`;
  }
  if (needsAlias) return `    ${safe}: ${t} = Field(alias="${name}")`;
  return `    ${safe}: ${t}`;
}

function enumBlock(name: string, values: readonly string[]): string {
  const members = values
    .map((v) => `    ${v.toUpperCase().replace(/[^A-Z0-9]/g, '_')} = "${v}"`)
    .join('\n');
  return `class ${name}(str, Enum):\n${members}\n`;
}

function quantFields(fields: Record<string, FieldSpec>): string[] {
  return Object.entries(fields)
    .filter(([, f]) => f.quantitative)
    .map(([n]) => n);
}

const lines: string[] = [];
lines.push('# ─────────────────────────────────────────────────────────────────────────────');
lines.push('# AUTO-GENERATED from packages/graph-schema/src/spec.ts. DO NOT EDIT BY HAND.');
lines.push('# Regenerate: pnpm --filter @chainos/graph-schema gen');
lines.push('# ─────────────────────────────────────────────────────────────────────────────');
lines.push('from __future__ import annotations');
lines.push('');
lines.push('from enum import Enum');
lines.push('from typing import Literal, Optional, Union');
lines.push('');
lines.push('from pydantic import BaseModel, ConfigDict, Field');
lines.push('');
lines.push('');
lines.push(enumBlock('Confidence', CONFIDENCE));
lines.push('');
lines.push(enumBlock('SourceType', SOURCE_TYPE));
lines.push('');
lines.push(enumBlock('SupplyDirection', SUPPLY_DIRECTION));
lines.push('');

lines.push('class _Base(BaseModel):');
lines.push('    model_config = ConfigDict(populate_by_name=True, extra="ignore")');
lines.push('');
lines.push('');

// TrustMeta
lines.push('class TrustMeta(_Base):');
for (const [name, f] of Object.entries(TRUST_FIELDS)) lines.push(pyField(name, f));
lines.push('');
lines.push('');

// Nodes
for (const [name, spec] of Object.entries(NODE_SPECS)) {
  lines.push(`class ${name}(_Base):`);
  lines.push(`    """${spec.doc}"""`);
  lines.push(`    label: Literal["${spec.label}"] = "${spec.label}"`);
  for (const [fname, f] of Object.entries(spec.fields)) lines.push(pyField(fname, f));
  lines.push('');
  lines.push('');
}

const nodeNames = Object.keys(NODE_SPECS);
lines.push(`GraphNode = Union[${nodeNames.join(', ')}]`);
lines.push('');
lines.push('');

// Edges
for (const [name, spec] of Object.entries(EDGE_SPECS)) {
  const cls = name
    .toLowerCase()
    .split('_')
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join('');
  lines.push(`class ${cls}(_Base):`);
  lines.push(`    """${spec.doc} (${spec.from} -> ${spec.to})"""`);
  lines.push(`    type: Literal["${spec.label}"] = "${spec.label}"`);
  lines.push('    from_: str = Field(alias="from")');
  lines.push('    to: str');
  lines.push('    base_date: Optional[str] = None');
  lines.push('    next_update: Optional[str] = None');
  lines.push('    confidence: Optional[Confidence] = None');
  lines.push('    source_id: Optional[str] = None');
  for (const [fname, f] of Object.entries(spec.fields)) lines.push(pyField(fname, f));
  lines.push('');
  lines.push('');
}

// Constants used by the validation gate and graph repos.
lines.push('NODE_LABELS = [' + nodeNames.map((n) => `"${n}"`).join(', ') + ']');
const edgeLabels = Object.keys(EDGE_SPECS);
lines.push('EDGE_TYPES = [' + edgeLabels.map((n) => `"${n}"`).join(', ') + ']');
const quantEdges = Object.entries(EDGE_SPECS)
  .filter(([, s]) => s.quantitative)
  .map(([n]) => n);
lines.push('QUANTITATIVE_EDGE_TYPES = [' + quantEdges.map((n) => `"${n}"`).join(', ') + ']');
lines.push('');

// Per-entity quantitative fields (need trust meta + SOURCED_FROM before publish).
lines.push('QUANTITATIVE_NODE_FIELDS = {');
for (const [name, spec] of Object.entries(NODE_SPECS)) {
  const qf = quantFields(spec.fields);
  if (qf.length) lines.push(`    "${name}": [${qf.map((f) => `"${f}"`).join(', ')}],`);
}
lines.push('}');
lines.push('');
lines.push('QUANTITATIVE_EDGE_FIELDS = {');
for (const [name, spec] of Object.entries(EDGE_SPECS)) {
  const qf = quantFields(spec.fields);
  if (qf.length) lines.push(`    "${name}": [${qf.map((f) => `"${f}"`).join(', ')}],`);
}
lines.push('}');
lines.push('');

// Flow-filter view mapping for the Terminal.
lines.push('FLOW_VIEWS = [' + FLOW_VIEWS.map((v) => `"${v}"`).join(', ') + ']');
lines.push('FLOW_VIEW_EDGES = {');
for (const v of FLOW_VIEWS) {
  lines.push(`    "${v}": [${FLOW_VIEW_EDGES[v].map((e) => `"${e}"`).join(', ')}],`);
}
lines.push('}');
lines.push('');

const __dirname = dirname(fileURLToPath(import.meta.url));
const out = resolve(
  __dirname,
  '../../../services/engine/app/graph_schema/generated.py',
);
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, lines.join('\n'));
// eslint-disable-next-line no-console
console.log(`graph-schema → wrote ${out}`);

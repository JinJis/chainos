import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  CompanySchema,
  SuppliesSchema,
  GraphSchema,
  NODE_SPECS,
  EDGE_SPECS,
} from './index.js';

test('Company node validates a well-formed record', () => {
  const ok = CompanySchema.safeParse({
    label: 'Company',
    id: 'nvda',
    ticker: 'NVDA',
    name: 'Nvidia',
    country: 'US',
    exchange: 'NASDAQ',
    sector: 'Semiconductors',
    tier: 1,
    market_cap: 3.2e12,
    base_date: '26 Q1 filing',
    next_update: '26 Q2 earnings',
  });
  assert.ok(ok.success, ok.success ? '' : JSON.stringify(ok.error.issues));
});

test('SUPPLIES edge accepts optional trust meta', () => {
  const ok = SuppliesSchema.safeParse({
    type: 'SUPPLIES',
    from: 'samsung',
    to: 'nvda',
    product_ref: 'HBM3E',
    allocation_pct: 30,
    confidence: 'verified',
    base_date: '26 Q1 filing',
    next_update: '26 Q2 earnings',
    source_id: 'src-1',
  });
  assert.ok(ok.success, ok.success ? '' : JSON.stringify(ok.error.issues));
});

test('bad enum value is rejected', () => {
  const bad = CompanySchema.safeParse({
    label: 'Company',
    id: 'x',
    ticker: 'X',
    name: 'X',
    country: 'US',
    exchange: 'NYSE',
    sector: 'S',
    tier: 'one',
    base_date: 'a',
    next_update: 'b',
  });
  assert.equal(bad.success, false);
});

test('Graph payload round-trips', () => {
  const g = GraphSchema.parse({ nodes: [], edges: [] });
  assert.deepEqual(g, { nodes: [], edges: [] });
});

test('spec exposes the canonical node and edge set', () => {
  assert.deepEqual(Object.keys(NODE_SPECS).sort(), [
    'Company',
    'Division',
    'Product',
    'Source',
    'Theme',
  ]);
  assert.ok('SOURCED_FROM' in EDGE_SPECS);
});

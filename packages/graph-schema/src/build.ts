/**
 * Derives Zod validators from the canonical spec. Types are inferred from the
 * Zod schemas so the TS surface can never drift from the spec.
 */
import { z, type ZodTypeAny } from 'zod';
import {
  CONFIDENCE,
  SOURCE_TYPE,
  SUPPLY_DIRECTION,
  TRUST_FIELDS,
  NODE_SPECS,
  EDGE_SPECS,
  type FieldSpec,
  type FieldType,
} from './spec.js';

export const ConfidenceSchema = z.enum(CONFIDENCE);
export const SourceTypeSchema = z.enum(SOURCE_TYPE);
export const SupplyDirectionSchema = z.enum(SUPPLY_DIRECTION);

export type Confidence = z.infer<typeof ConfidenceSchema>;
export type SourceType = z.infer<typeof SourceTypeSchema>;
export type SupplyDirection = z.infer<typeof SupplyDirectionSchema>;

function baseFor(type: FieldType): ZodTypeAny {
  switch (type) {
    case 'string':
      return z.string();
    case 'number':
      return z.number();
    case 'int':
      return z.number().int();
    case 'boolean':
      return z.boolean();
    case 'enum:confidence':
      return ConfidenceSchema;
    case 'enum:source_type':
      return SourceTypeSchema;
    case 'enum:supply_direction':
      return SupplyDirectionSchema;
  }
}

function fieldToZod(field: FieldSpec): ZodTypeAny {
  const base = baseFor(field.type);
  return field.optional ? base.optional() : base;
}

function shapeFromFields(fields: Record<string, FieldSpec>): z.ZodRawShape {
  const shape: z.ZodRawShape = {};
  for (const [name, field] of Object.entries(fields)) {
    shape[name] = fieldToZod(field);
  }
  return shape;
}

/** Trust metadata required on every quantitative value (PRD §5.3). */
export const TrustMetaSchema = z.object(shapeFromFields(TRUST_FIELDS));
export type TrustMeta = z.infer<typeof TrustMetaSchema>;

function buildNode(name: string) {
  const spec = NODE_SPECS[name];
  if (!spec) throw new Error(`Unknown node spec: ${name}`);
  return z.object({ label: z.literal(spec.label), ...shapeFromFields(spec.fields) });
}

function buildEdge(name: string) {
  const spec = EDGE_SPECS[name];
  if (!spec) throw new Error(`Unknown edge spec: ${name}`);
  return z.object({
    type: z.literal(spec.label),
    from: z.string(),
    to: z.string(),
    // Trust meta is optional at the schema layer; the publish validation gate
    // enforces its presence on quantitative edges. See publish/validate.
    base_date: z.string().optional(),
    next_update: z.string().optional(),
    confidence: ConfidenceSchema.optional(),
    source_id: z.string().optional(),
    ...shapeFromFields(spec.fields),
  });
}

// ── Node schemas ─────────────────────────────────────────────────────────────
export const ThemeSchema = buildNode('Theme');
export const CompanySchema = buildNode('Company');
export const DivisionSchema = buildNode('Division');
export const ProductSchema = buildNode('Product');
export const SourceSchema = buildNode('Source');

export type Theme = z.infer<typeof ThemeSchema>;
export type Company = z.infer<typeof CompanySchema>;
export type Division = z.infer<typeof DivisionSchema>;
export type Product = z.infer<typeof ProductSchema>;
export type Source = z.infer<typeof SourceSchema>;

export const NodeSchema = z.discriminatedUnion('label', [
  ThemeSchema,
  CompanySchema,
  DivisionSchema,
  ProductSchema,
  SourceSchema,
]);
export type GraphNode = z.infer<typeof NodeSchema>;

// ── Edge schemas ─────────────────────────────────────────────────────────────
export const HasDivisionSchema = buildEdge('HAS_DIVISION');
export const ProducesSchema = buildEdge('PRODUCES');
export const SuppliesSchema = buildEdge('SUPPLIES');
export const RevenueFlowSchema = buildEdge('REVENUE_FLOW');
export const InvestsInSchema = buildEdge('INVESTS_IN');
export const CompetesWithSchema = buildEdge('COMPETES_WITH');
export const SourcedFromSchema = buildEdge('SOURCED_FROM');

export const EdgeSchema = z.discriminatedUnion('type', [
  HasDivisionSchema,
  ProducesSchema,
  SuppliesSchema,
  RevenueFlowSchema,
  InvestsInSchema,
  CompetesWithSchema,
  SourcedFromSchema,
]);
export type GraphEdge = z.infer<typeof EdgeSchema>;

/** A full graph payload as exchanged between Engine and the front-ends. */
export const GraphSchema = z.object({
  theme: ThemeSchema.optional(),
  nodes: z.array(NodeSchema),
  edges: z.array(EdgeSchema),
});
export type Graph = z.infer<typeof GraphSchema>;

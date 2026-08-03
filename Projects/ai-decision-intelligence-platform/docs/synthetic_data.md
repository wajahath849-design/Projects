# Synthetic enterprise data

## Disclosure

All Phase 3 suppliers, warehouses, transportation lanes, purchase orders,
inventory snapshots, and constraints are generated portfolio data. They do not
represent actual Walmart facilities, suppliers, costs, policies, or operations.
M5-derived identifiers are used only to connect operational simulations to the
historical demand grain.

## Reproducibility

Generation uses the configured `RANDOM_SEED` and stable input ordering. Every
generated table is canonicalized and SHA-256 hashed in memory; a second run with
the same seed and inputs must produce identical hashes before data is loaded.

## Logical relationships

- Every product receives three feasible supplier relationships.
- Every supplier has a lane to each generated warehouse.
- Purchase quantities obey relationship-level minimum, maximum, and capacity
  values.
- Completed, partial, delayed, cancelled, and open order states have consistent
  received and cancelled quantities.
- Inventory receipts originate from actual purchase-order deliveries.
- Daily stock follows `closing = opening + received - sold - damaged - reserved`.
- Unfulfilled demand is recorded as lost sales; closing stock is never negative.
- Daily inventory is checked against warehouse capacity.

## SQL schema extension

Phase 3 migration `008_create_enterprise_operational_tables.sql` adds:

- `BridgeSupplierProduct`, which carries product-specific cost, order quantity,
  capacity, lead-time, and preference attributes.
- `BusinessConstraint`, which stores global budget and warehouse-capacity inputs.

The migration is idempotent and does not remove or rename existing objects.

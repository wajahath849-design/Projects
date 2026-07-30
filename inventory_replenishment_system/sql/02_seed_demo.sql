SET search_path TO inventory, public;

INSERT INTO dim_supplier (supplier_code, supplier_name, contact_email, contractual_lead_time_days)
VALUES
    ('SUP-001', 'NorthStar Electronics', 'orders@northstar.example', 8),
    ('SUP-002', 'Continental Components', 'supply@continental.example', 12)
ON CONFLICT (supplier_code) DO NOTHING;

INSERT INTO dim_warehouse (warehouse_code, warehouse_name, region, timezone)
VALUES
    ('WH-HAM', 'Hamburg Distribution Center', 'North', 'Europe/Berlin'),
    ('WH-MUC', 'Munich Distribution Center', 'South', 'Europe/Berlin')
ON CONFLICT (warehouse_code) DO NOTHING;

INSERT INTO dim_sku (sku_code, sku_name, category, unit_cost, minimum_order_qty, order_multiple)
VALUES
    ('ELEC-1001', 'Industrial Sensor A', 'Electronics', 42.50, 20, 10),
    ('ELEC-1002', 'Gateway Module B', 'Electronics', 88.00, 10, 5),
    ('MECH-2001', 'Mounting Bracket', 'Mechanical', 7.25, 50, 25)
ON CONFLICT (sku_code) DO NOTHING;

INSERT INTO supplier_sku (supplier_id, sku_id, priority_rank, unit_purchase_cost)
SELECT sup.supplier_id, sku.sku_id, 1, sku.unit_cost * 0.85
FROM dim_supplier sup
CROSS JOIN dim_sku sku
WHERE sup.supplier_code = CASE WHEN sku.sku_code = 'MECH-2001' THEN 'SUP-002' ELSE 'SUP-001' END
ON CONFLICT (supplier_id, sku_id) DO NOTHING;

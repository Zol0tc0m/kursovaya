from django.db import migrations

SQL = r"""
-- === Представления (VIEW) ===

CREATE OR REPLACE VIEW ElShop_vw_product_inventory AS
SELECT
  p.id AS product_id,
  p.sku,
  p.name,
  COALESCE(SUM(i.quantity),0) AS total_quantity,
  COALESCE(SUM(i.reserved),0) AS total_reserved
FROM ElShop_product p
LEFT JOIN ElShop_inventory i ON p.id = i.product_id
GROUP BY p.id, p.sku, p.name;

CREATE OR REPLACE VIEW ElShop_vw_sales_by_product AS
SELECT
  oi.product_id,
  p.sku,
  p.name,
  SUM(oi.quantity) AS qty_sold,
  SUM(oi.line_total) AS revenue
FROM ElShop_order_item oi
JOIN ElShop_product p ON p.id = oi.product_id
JOIN ElShop_order o ON o.id = oi.order_id AND o.status IN ('paid','shipped','completed')
GROUP BY oi.product_id, p.sku, p.name;

-- === Триггер аудита ===

CREATE OR REPLACE FUNCTION ElShop_fn_audit_log() RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    INSERT INTO ElShop_audit_log(table_name, operation, row_data, changed_by)
    VALUES (TG_TABLE_NAME, TG_OP, to_jsonb(OLD), current_setting('app.current_user', true));
    RETURN OLD;
  ELSIF TG_OP = 'UPDATE' THEN
    INSERT INTO ElShop_audit_log(table_name, operation, row_data, changed_by)
    VALUES (TG_TABLE_NAME, TG_OP, jsonb_build_object('old', to_jsonb(OLD), 'new', to_jsonb(NEW)), current_setting('app.current_user', true));
    RETURN NEW;
  ELSIF TG_OP = 'INSERT' THEN
    INSERT INTO ElShop_audit_log(table_name, operation, row_data, changed_by)
    VALUES (TG_TABLE_NAME, TG_OP, to_jsonb(NEW), current_setting('app.current_user', true));
    RETURN NEW;
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_products AFTER INSERT OR UPDATE OR DELETE ON ElShop_product
  FOR EACH ROW EXECUTE FUNCTION ElShop_fn_audit_log();

CREATE TRIGGER trg_audit_orders AFTER INSERT OR UPDATE OR DELETE ON ElShop_order
  FOR EACH ROW EXECUTE FUNCTION ElShop_fn_audit_log();

-- === Валидация заказа ===

CREATE OR REPLACE FUNCTION ElShop_fn_order_item_line_total_check() RETURNS TRIGGER AS $$
BEGIN
  IF NEW.line_total <> (NEW.unit_price * NEW.quantity - NEW.discount) THEN
    RAISE EXCEPTION 'Invalid line_total';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_check_line_total
  BEFORE INSERT OR UPDATE ON ElShop_order_item
  FOR EACH ROW EXECUTE FUNCTION ElShop_fn_order_item_line_total_check();

-- === Процедуры ===

CREATE OR REPLACE FUNCTION ElShop_sp_calculate_order_total(p_order_id INT, p_tax_rate NUMERIC DEFAULT 0.2)
RETURNS NUMERIC LANGUAGE plpgsql AS $$
DECLARE
  s_subtotal NUMERIC := 0;
  s_tax NUMERIC := 0;
  s_shipping NUMERIC := 0;
  s_total NUMERIC := 0;
BEGIN
  SELECT COALESCE(SUM(line_total),0) INTO s_subtotal FROM ElShop_order_item WHERE order_id = p_order_id;

  IF s_subtotal > 500 THEN
    s_shipping := 0;
  ELSE
    s_shipping := 9.99;
  END IF;

  s_tax := ROUND(s_subtotal * p_tax_rate, 2);
  s_total := ROUND(s_subtotal + s_tax + s_shipping, 2);

  UPDATE ElShop_order SET subtotal = s_subtotal, tax = s_tax,
      shipping_cost = s_shipping, total = s_total
  WHERE id = p_order_id;

  RETURN s_total;
END;
$$;

CREATE TYPE ElShop_restock_item AS (product_id INT, warehouse_id INT, qty INT);

CREATE OR REPLACE FUNCTION ElShop_sp_bulk_restock(items ElShop_restock_item[])
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
  it ElShop_restock_item;
BEGIN
  FOREACH it IN ARRAY items LOOP
    INSERT INTO ElShop_inventory(product_id, warehouse_id, quantity, last_restocked)
    VALUES (it.product_id, it.warehouse_id, GREATEST(it.qty,0), now())
    ON CONFLICT (product_id, warehouse_id)
    DO UPDATE SET quantity = ElShop_inventory.quantity + GREATEST(it.qty,0),
                  last_restocked = now();
  END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION ElShop_sp_generate_monthly_sales(p_year INT, p_month INT)
RETURNS TABLE(year INT, month INT, total_sales NUMERIC, total_orders INT)
LANGUAGE plpgsql AS $$
DECLARE
  start_dt TIMESTAMP := make_timestamp(p_year, p_month, 1, 0, 0, 0);
  end_dt TIMESTAMP := (start_dt + INTERVAL '1 month');
  s_total NUMERIC := 0;
  s_count INT := 0;
BEGIN
  SELECT COALESCE(SUM(total),0), COUNT(*) INTO s_total, s_count
  FROM ElShop_order
  WHERE created_at >= start_dt AND created_at < end_dt
    AND status IN ('paid','shipped','completed');

  RETURN QUERY SELECT p_year, p_month, s_total, s_count;
END;
$$;
"""

class Migration(migrations.Migration):

    dependencies = [
        ('ElShop', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(SQL),
    ]
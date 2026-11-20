-- Rights of role printuchet_app (table 21). Run as printuchet_owner.

GRANT USAGE ON SCHEMA public TO printuchet_app;

-- 1. Base rights on everything that exists now
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO printuchet_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO printuchet_app;

-- 2. Same rights for future tables created by printuchet_owner
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO printuchet_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO printuchet_app;

-- 3. Restrictions from table 21
-- orders, clients, users, materials, product types are never deleted (FT-24)
REVOKE DELETE ON orders, client, app_user, material, product_type FROM printuchet_app;
-- comments and log cannot be changed or deleted (FT-05, ZI-08)
REVOKE UPDATE, DELETE ON order_comment, action_log FROM printuchet_app;
-- reference tables are read-only
REVOKE INSERT, UPDATE, DELETE ON order_status, role FROM printuchet_app;
-- report view is read-only
REVOKE INSERT, UPDATE, DELETE ON v_order_report FROM printuchet_app;
-- NOTE: this file is the ORIGINAL TARGET DESIGN (MVP + later phases). It is a reference only.
-- The schema that actually runs is defined by the Django models/migrations in backend/*/migrations.
-- Tables here with no Django model yet (group buying, inventory, subscriptions, commissions, ratings, ...) are not built.

-- GetbyFarm — PostgreSQL schema (MVP + Phase 2 placeholders)
-- Conventions: UUID PKs, created_at/updated_at on every table, soft-delete via deleted_at,
-- explicit FKs + indexes, money stored as NUMERIC(14,2) to avoid float rounding errors.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============ CORE / IDENTITY ============

CREATE TABLE countries (
    id SERIAL PRIMARY KEY,
    code CHAR(2) UNIQUE NOT NULL,          -- ISO 3166-1 alpha-2, e.g. 'KE'
    name VARCHAR(100) NOT NULL,
    currency_code CHAR(3) NOT NULL,        -- ISO 4217, e.g. 'KES'
    default_tax_rate NUMERIC(5,2) NOT NULL DEFAULT 16.00,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,      -- 'buyer_user','buyer_manager','enterprise_admin',
                                            -- 'supplier_staff','supplier_admin','delivery_partner','platform_admin'
    name VARCHAR(100) NOT NULL
);

CREATE TABLE permissions (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,     -- 'order.approve', 'supplier.verify', ...
    description TEXT
);

CREATE TABLE role_permissions (
    role_id INT REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INT REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE organizations (               -- a buyer business (may have many branches)
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    country_id INT NOT NULL REFERENCES countries(id),
    kra_pin VARCHAR(20),
    registration_number VARCHAR(50),
    subscription_tier VARCHAR(20) NOT NULL DEFAULT 'starter', -- starter/business/professional/enterprise
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE branches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(150) NOT NULL,            -- e.g. "Nairobi CBD"
    address TEXT,
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    monthly_budget NUMERIC(14,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_branches_org ON branches(organization_id);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_users_org ON users(organization_id);
CREATE INDEX idx_users_branch ON users(branch_id);

CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id INT REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

-- ============ SUPPLIERS ============

CREATE TABLE supplier_organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_name VARCHAR(200) NOT NULL,
    country_id INT NOT NULL REFERENCES countries(id),
    kra_pin VARCHAR(20),
    registration_number VARCHAR(50),
    operating_location TEXT,
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    verification_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (verification_status IN ('pending','under_review','verified','suspended','rejected')),
    reliability_score NUMERIC(5,2) NOT NULL DEFAULT 0,   -- 0-100, computed from order history
    quality_rating NUMERIC(3,2) NOT NULL DEFAULT 0,      -- 0-5 stars
    on_time_delivery_rate NUMERIC(5,2) NOT NULL DEFAULT 0,
    payout_details JSONB,                                 -- encrypted at rest / access-controlled
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_supplier_status ON supplier_organizations(verification_status);

CREATE TABLE supplier_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_id UUID NOT NULL REFERENCES supplier_organizations(id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL,    -- 'kra_cert','business_permit','food_handling_cert',...
    file_url TEXT NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    verified_at TIMESTAMPTZ
);

CREATE TABLE supplier_users (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    supplier_id UUID NOT NULL REFERENCES supplier_organizations(id) ON DELETE CASCADE
);
CREATE INDEX idx_supplier_users_supplier ON supplier_users(supplier_id);

-- ============ CATALOGUE & PRICING ============

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    parent_id INT REFERENCES categories(id),
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(120) UNIQUE NOT NULL
);

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id INT NOT NULL REFERENCES categories(id),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    default_unit VARCHAR(20) NOT NULL,     -- 'kg','litre','crate','tray','piece'
    image_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_name_trgm ON products USING gin (name gin_trgm_ops);  -- requires pg_trgm

CREATE TABLE product_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,            -- e.g. "50kg bag", "Grade A"
    unit VARCHAR(20) NOT NULL,
    pack_size NUMERIC(10,2) NOT NULL DEFAULT 1
);

CREATE TABLE supplier_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_id UUID NOT NULL REFERENCES supplier_organizations(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    variant_id UUID REFERENCES product_variants(id),
    unit_price NUMERIC(14,2) NOT NULL,
    currency_code CHAR(3) NOT NULL DEFAULT 'KES',
    stock_quantity NUMERIC(14,2) NOT NULL DEFAULT 0,
    minimum_order_quantity NUMERIC(14,2) NOT NULL DEFAULT 1,
    delivery_areas TEXT[],                 -- simple MVP representation; Phase 2: geofenced zones table
    delivery_cost_flat NUMERIC(14,2) NOT NULL DEFAULT 0,
    lead_time_days NUMERIC(4,1) NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_supplier_prices_product ON supplier_prices(product_id);
CREATE INDEX idx_supplier_prices_supplier ON supplier_prices(supplier_id);

CREATE TABLE price_history (
    id BIGSERIAL PRIMARY KEY,
    product_id UUID NOT NULL REFERENCES products(id),
    supplier_id UUID NOT NULL REFERENCES supplier_organizations(id),
    unit_price NUMERIC(14,2) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_price_history_product_date ON price_history(product_id, recorded_at);

-- ============ INVENTORY (Phase 2) ============

CREATE TABLE inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    current_stock NUMERIC(14,2) NOT NULL DEFAULT 0,
    minimum_stock NUMERIC(14,2) NOT NULL DEFAULT 0,
    maximum_stock NUMERIC(14,2),
    reorder_level NUMERIC(14,2),
    average_daily_usage NUMERIC(14,2) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (branch_id, product_id)
);

-- ============ SHOPPING LISTS & CART ============

CREATE TABLE shopping_lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    name VARCHAR(150) NOT NULL,
    is_recurring BOOLEAN NOT NULL DEFAULT FALSE,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE shopping_list_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shopping_list_id UUID NOT NULL REFERENCES shopping_lists(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    quantity NUMERIC(14,2) NOT NULL
);

CREATE TABLE carts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open','checked_out','abandoned')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cart_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cart_id UUID NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
    supplier_price_id UUID NOT NULL REFERENCES supplier_prices(id),
    quantity NUMERIC(14,2) NOT NULL,
    locked_unit_price NUMERIC(14,2) NOT NULL,   -- snapshot at add-to-cart time
    recommendation_reason TEXT                  -- why the engine picked this supplier
);

-- ============ ORDERS, PAYMENTS, INVOICES ============

CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    order_number VARCHAR(30) UNIQUE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','submitted','confirmed','processing',
                           'ready_for_dispatch','in_transit','delivered','completed','cancelled')),
    subtotal NUMERIC(14,2) NOT NULL DEFAULT 0,
    delivery_fee NUMERIC(14,2) NOT NULL DEFAULT 0,
    tax_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    placed_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_orders_branch ON orders(branch_id);
CREATE INDEX idx_orders_status ON orders(status);

CREATE TABLE order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    supplier_id UUID NOT NULL REFERENCES supplier_organizations(id),
    quantity NUMERIC(14,2) NOT NULL,
    unit_price NUMERIC(14,2) NOT NULL,
    line_total NUMERIC(14,2) NOT NULL
);

CREATE TABLE order_allocations (         -- one order can split across suppliers
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    supplier_id UUID NOT NULL REFERENCES supplier_organizations(id),
    status VARCHAR(20) NOT NULL DEFAULT 'new'
        CHECK (status IN ('new','accepted','preparing','ready','dispatched','delivered','cancelled')),
    subtotal NUMERIC(14,2) NOT NULL DEFAULT 0
);

CREATE TABLE purchase_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    approver_role VARCHAR(30) NOT NULL,     -- 'manager','procurement','finance'
    approver_id UUID REFERENCES users(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
    threshold_amount NUMERIC(14,2),
    decided_at TIMESTAMPTZ
);

CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id),
    provider VARCHAR(30) NOT NULL DEFAULT 'mpesa',   -- configurable: mpesa, card, bank
    provider_reference VARCHAR(100),                  -- e.g. M-Pesa receipt number
    amount NUMERIC(14,2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','success','failed','refunded')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id),
    invoice_number VARCHAR(30) UNIQUE NOT NULL,
    subtotal NUMERIC(14,2) NOT NULL,
    tax_amount NUMERIC(14,2) NOT NULL,
    discount_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    delivery_fee NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_amount NUMERIC(14,2) NOT NULL,
    payment_status VARCHAR(20) NOT NULL DEFAULT 'unpaid' CHECK (payment_status IN ('unpaid','paid','partial')),
    etims_reference VARCHAR(100),           -- placeholder only; [Future]
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ DELIVERY ============

CREATE TABLE delivery_partners (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    phone VARCHAR(20),
    is_internal BOOLEAN NOT NULL DEFAULT FALSE   -- false = 3rd-party logistics provider
);

CREATE TABLE deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_allocation_id UUID NOT NULL REFERENCES order_allocations(id) ON DELETE CASCADE,
    delivery_partner_id UUID REFERENCES delivery_partners(id),
    delivery_address TEXT NOT NULL,
    scheduled_slot TSTZRANGE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','dispatched','in_transit','delivered','failed')),
    proof_of_delivery_url TEXT,
    delivered_at TIMESTAMPTZ
);

CREATE TABLE delivery_tracking (
    id BIGSERIAL PRIMARY KEY,
    delivery_id UUID NOT NULL REFERENCES deliveries(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL,
    note TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ GROUP BUYING (Phase 2) ============

CREATE TABLE demand_pools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id),
    target_quantity NUMERIC(14,2) NOT NULL,
    committed_quantity NUMERIC(14,2) NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed','fulfilled','cancelled')),
    closes_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE group_buying_commitments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    demand_pool_id UUID NOT NULL REFERENCES demand_pools(id) ON DELETE CASCADE,
    branch_id UUID NOT NULL REFERENCES branches(id),
    quantity NUMERIC(14,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE supplier_quotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    demand_pool_id UUID NOT NULL REFERENCES demand_pools(id) ON DELETE CASCADE,
    supplier_id UUID NOT NULL REFERENCES supplier_organizations(id),
    quoted_unit_price NUMERIC(14,2) NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ TRUST, NOTIFICATIONS, PLATFORM OPS ============

CREATE TABLE ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id),
    supplier_id UUID NOT NULL REFERENCES supplier_organizations(id),
    rated_by UUID NOT NULL REFERENCES users(id),
    score NUMERIC(3,2) NOT NULL CHECK (score BETWEEN 0 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('email','sms','in_app','whatsapp')),
    title VARCHAR(150) NOT NULL,
    body TEXT NOT NULL,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    supplier_id UUID REFERENCES supplier_organizations(id),
    plan_code VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','past_due','cancelled')),
    renews_at TIMESTAMPTZ,
    CHECK (num_nonnulls(organization_id, supplier_id) = 1)
);

CREATE TABLE commissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id),
    rate_percent NUMERIC(5,2) NOT NULL,
    amount NUMERIC(14,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE promotions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(30) UNIQUE NOT NULL,
    discount_type VARCHAR(10) NOT NULL CHECK (discount_type IN ('percent','flat')),
    discount_value NUMERIC(14,2) NOT NULL,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ
);

CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);

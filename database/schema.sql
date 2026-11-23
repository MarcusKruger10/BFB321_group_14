SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP VIEW  IF EXISTS v_product_stock;
DROP TABLE IF EXISTS alerts;
DROP TABLE IF EXISTS stock_movements;
DROP TABLE IF EXISTS purchase_order_lines;
DROP TABLE IF EXISTS purchase_orders;
DROP TABLE IF EXISTS batches;
DROP TABLE IF EXISTS product_suppliers;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS users;

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE users (
    user_id        INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    username       VARCHAR(50)   NOT NULL,
    password_hash  VARCHAR(255)  NOT NULL,
    full_name      VARCHAR(100)  NOT NULL,
    role           ENUM('admin','pharmacist','assistant') NOT NULL DEFAULT 'assistant',
    is_active      BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id),
    CONSTRAINT uq_users_username UNIQUE (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE suppliers (
    supplier_id    INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    name           VARCHAR(120)  NOT NULL,
    contact_name   VARCHAR(100)  NULL,
    phone          VARCHAR(30)   NULL,
    email          VARCHAR(120)  NULL,
    is_active      BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (supplier_id),
    CONSTRAINT uq_suppliers_name UNIQUE (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE categories (
    category_id    INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    name           VARCHAR(80)   NOT NULL,
    description    VARCHAR(255)  NULL,
    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (category_id),
    CONSTRAINT uq_categories_name UNIQUE (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE products (
    product_id             INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    sku                    VARCHAR(30)   NOT NULL,
    name                   VARCHAR(120)  NOT NULL,
    strength               VARCHAR(40)   NULL,           -- e.g. 500mg
    dosage_form            ENUM('tablet','capsule','syrup','suspension','inhaler','cream','injection','other')
                                         NOT NULL DEFAULT 'tablet',
    pack_size              INT UNSIGNED  NOT NULL DEFAULT 1,  -- units per pack (orders are rounded to packs)
    category_id            INT UNSIGNED  NOT NULL,
    unit_cost              DECIMAL(10,2) NOT NULL,       -- ZAR cost per unit
    unit_price             DECIMAL(10,2) NOT NULL,       -- ZAR selling price per unit
    service_level          DECIMAL(4,3)  NOT NULL DEFAULT 0.950, -- chance of not running out (z-score input)
    reorder_point_override INT UNSIGNED  NULL,           -- pharmacist's threshold; NULL = use calculated reorder point
    ordering_cost          DECIMAL(10,2) NOT NULL DEFAULT 150.00, -- ZAR per order (EOQ S)
    holding_cost_rate      DECIMAL(5,4)  NOT NULL DEFAULT 0.2000, -- annual share of unit cost (EOQ H = rate x unit_cost)
    shelf_life_days        SMALLINT UNSIGNED NOT NULL DEFAULT 730, -- caps the order so stock is used before expiry
    is_active              BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at             DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id),
    CONSTRAINT uq_products_sku UNIQUE (sku),
    CONSTRAINT fk_products_category FOREIGN KEY (category_id)
        REFERENCES categories (category_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT ck_products_cost      CHECK (unit_cost  >= 0),
    CONSTRAINT ck_products_price     CHECK (unit_price >= 0),
    CONSTRAINT ck_products_pack      CHECK (pack_size  >= 1),
    CONSTRAINT ck_products_service   CHECK (service_level > 0 AND service_level < 1),
    CONSTRAINT ck_products_ordercost CHECK (ordering_cost >= 0),
    CONSTRAINT ck_products_holding   CHECK (holding_cost_rate > 0 AND holding_cost_rate <= 1),
    CONSTRAINT ck_products_shelf     CHECK (shelf_life_days > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_products_category ON products (category_id);
CREATE INDEX ix_products_name     ON products (name);

CREATE TABLE product_suppliers (
    product_id       INT UNSIGNED  NOT NULL,
    supplier_id      INT UNSIGNED  NOT NULL,
    supplier_sku     VARCHAR(40)   NULL,
    lead_time_days   SMALLINT UNSIGNED NOT NULL DEFAULT 3,
    supplier_cost    DECIMAL(10,2) NOT NULL,
    is_preferred     BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id, supplier_id),
    CONSTRAINT fk_ps_product  FOREIGN KEY (product_id)
        REFERENCES products (product_id)   ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_ps_supplier FOREIGN KEY (supplier_id)
        REFERENCES suppliers (supplier_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT ck_ps_cost     CHECK (supplier_cost >= 0),
    CONSTRAINT ck_ps_leadtime CHECK (lead_time_days BETWEEN 0 AND 120)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_ps_supplier ON product_suppliers (supplier_id);

CREATE TABLE purchase_orders (
    po_id          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    po_number      VARCHAR(20)   NOT NULL,
    supplier_id    INT UNSIGNED  NOT NULL,
    status         ENUM('draft','ordered','received','cancelled') NOT NULL DEFAULT 'draft',
    ordered_at     DATETIME      NULL,
    expected_date  DATE          NULL,
    received_at    DATETIME      NULL,
    created_by     INT UNSIGNED  NOT NULL,
    notes          VARCHAR(255)  NULL,
    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (po_id),
    CONSTRAINT uq_po_number UNIQUE (po_number),
    CONSTRAINT fk_po_supplier FOREIGN KEY (supplier_id)
        REFERENCES suppliers (supplier_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_po_user     FOREIGN KEY (created_by)
        REFERENCES users (user_id)         ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_po_status   ON purchase_orders (status);
CREATE INDEX ix_po_supplier ON purchase_orders (supplier_id);

CREATE TABLE purchase_order_lines (
    po_line_id     INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    po_id          INT UNSIGNED  NOT NULL,
    product_id     INT UNSIGNED  NOT NULL,
    quantity       INT UNSIGNED  NOT NULL,
    unit_cost      DECIMAL(10,2) NOT NULL,
    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (po_line_id),
    CONSTRAINT uq_pol_po_product UNIQUE (po_id, product_id),
    CONSTRAINT fk_pol_po      FOREIGN KEY (po_id)
        REFERENCES purchase_orders (po_id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_pol_product FOREIGN KEY (product_id)
        REFERENCES products (product_id)   ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT ck_pol_qty  CHECK (quantity > 0),
    CONSTRAINT ck_pol_cost CHECK (unit_cost >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_pol_product ON purchase_order_lines (product_id);

CREATE TABLE batches (
    batch_id           INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    product_id         INT UNSIGNED  NOT NULL,
    supplier_id        INT UNSIGNED  NOT NULL,
    po_id              INT UNSIGNED  NULL,          -- NULL if received without a PO
    batch_number       VARCHAR(40)   NOT NULL,      -- manufacturer lot number
    expiry_date        DATE          NOT NULL,
    quantity_received  INT UNSIGNED  NOT NULL,
    quantity_on_hand   INT UNSIGNED  NOT NULL,
    unit_cost          DECIMAL(10,2) NOT NULL,
    received_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (batch_id),
    CONSTRAINT uq_batches_product_lot UNIQUE (product_id, batch_number),
    CONSTRAINT fk_batches_product  FOREIGN KEY (product_id)
        REFERENCES products (product_id)   ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_batches_supplier FOREIGN KEY (supplier_id)
        REFERENCES suppliers (supplier_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_batches_po       FOREIGN KEY (po_id)
        REFERENCES purchase_orders (po_id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT ck_batches_received CHECK (quantity_received > 0),
    CONSTRAINT ck_batches_onhand   CHECK (quantity_on_hand <= quantity_received),
    CONSTRAINT ck_batches_cost     CHECK (unit_cost >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_batches_product_expiry ON batches (product_id, expiry_date);
CREATE INDEX ix_batches_expiry         ON batches (expiry_date);
CREATE INDEX ix_batches_supplier       ON batches (supplier_id);
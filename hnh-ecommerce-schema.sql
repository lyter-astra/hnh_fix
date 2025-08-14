-- Categories Table
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    image_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Subcategories Table
CREATE TABLE IF NOT EXISTS subcategories (
    id SERIAL PRIMARY KEY,
    category_id INT REFERENCES categories(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    description TEXT,
    image_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(category_id, name),
    UNIQUE(category_id, slug)
);

-- Products Table
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    short_description TEXT,
    price NUMERIC(10,2) NOT NULL,
    original_price NUMERIC(10,2),
    cost_price NUMERIC(10,2),
    rating NUMERIC(3,2) DEFAULT 0,
    review_count INT DEFAULT 0,
    stock_quantity INT DEFAULT 0,
    low_stock_threshold INT DEFAULT 10,
    sku VARCHAR(50) UNIQUE NOT NULL,
    barcode VARCHAR(50),
    weight NUMERIC(8,2),
    dimensions VARCHAR(100),
    category_id INT REFERENCES categories(id),
    subcategory_id INT REFERENCES subcategories(id),
    brand VARCHAR(100),    
    status VARCHAR(20) DEFAULT 'active', -- active, inactive, discontinued
    is_featured BOOLEAN DEFAULT FALSE,
    meta_title VARCHAR(255),
    meta_description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Product Images Table
CREATE TABLE IF NOT EXISTS product_images (
    id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    alt_text VARCHAR(255),
    sort_order INT DEFAULT 0,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Product Variants Table
CREATE TABLE IF NOT EXISTS product_variants (
    id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL, -- e.g., "Red Large", "Blue Small"    
    sku VARCHAR(50) UNIQUE NOT NULL,
    price NUMERIC(10,2),
    stock_quantity INT DEFAULT 0,
    color_name VARCHAR(50),
    color_hex VARCHAR(7),
    size_name VARCHAR(50),
    weight NUMERIC(8,2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Brands Table
CREATE TABLE IF NOT EXISTS brands (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    logo TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    featured BOOLEAN DEFAULT FALSE,
    partner_since DATE,
    rating NUMERIC(2,1),
    growth TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Stores Table
CREATE TABLE IF NOT EXISTS stores (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(50),
    zip VARCHAR(20),
    phone VARCHAR(50),
    hours_weekday VARCHAR(100),
    hours_weekend VARCHAR(100),
    services TEXT[],              -- array of services
    rating NUMERIC(2,1),
    reviews INTEGER,
    distance VARCHAR(50),
    latitude NUMERIC(10,7),       -- latitudes with precision
    longitude NUMERIC(10,7),
    is_open BOOLEAN DEFAULT FALSE,
    featured BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Product Attributes Table
CREATE TABLE IF NOT EXISTS product_attributes (
    id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL, -- e.g., "Material", "Care Instructions"    
    value TEXT NOT NULL,
    type VARCHAR(50) DEFAULT 'text', -- text, number, boolean, list    
    is_filterable BOOLEAN DEFAULT FALSE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone_number VARCHAR(20),
    password_hash TEXT NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    date_of_birth DATE,
    gender VARCHAR(20),
    profile_picture TEXT,
    email_verified BOOLEAN DEFAULT FALSE,
    phone_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Product Reviews Table
CREATE TABLE IF NOT EXISTS product_reviews (
    id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(id) ON DELETE CASCADE,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    rating INT CHECK (rating BETWEEN 1 AND 5) NOT NULL,
    title VARCHAR(200),
    comment TEXT,
    is_verified_purchase BOOLEAN DEFAULT FALSE,
    is_approved BOOLEAN DEFAULT FALSE,
    helpful_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Addresses Table
CREATE TABLE IF NOT EXISTS addresses (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,    
    label VARCHAR(50) NOT NULL, -- Home, Work, etc.
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    company VARCHAR(100),
    address_line1 TEXT NOT NULL,
    address_line2 TEXT,
    city VARCHAR(100) NOT NULL,
    province VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20) NOT NULL,
    country VARCHAR(50) DEFAULT 'Zimbabwe',
    phone VARCHAR(20),
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Cart Items Table
CREATE TABLE IF NOT EXISTS cart_items (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    product_id INT REFERENCES products(id) ON DELETE CASCADE,
    variant_id INT REFERENCES product_variants(id) ON DELETE CASCADE,
    quantity INT NOT NULL CHECK (quantity > 0),
    price NUMERIC(10,2) NOT NULL, -- Price at time of adding to cart
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, product_id, variant_id)
);

-- Wishlist Table
CREATE TABLE IF NOT EXISTS wishlist (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    product_id INT REFERENCES products(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, product_id)
);

-- Orders Table
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    order_number VARCHAR(50) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- pending, confirmed, processing, shipped, delivered, cancelled
    payment_status VARCHAR(50) DEFAULT 'pending', -- pending, paid, failed, refunded
    currency VARCHAR(3) DEFAULT 'USD',
    subtotal NUMERIC(10,2) NOT NULL,
    tax_amount NUMERIC(10,2) DEFAULT 0,
    shipping_cost NUMERIC(10,2) DEFAULT 0,
    discount_amount NUMERIC(10,2) DEFAULT 0,
    total_amount NUMERIC(10,2) NOT NULL,
    
    -- Shipping Address (snapshot)
    shipping_first_name VARCHAR(100),
    shipping_last_name VARCHAR(100),
    shipping_company VARCHAR(100),
    shipping_address_line1 TEXT,
    shipping_address_line2 TEXT,
    shipping_city VARCHAR(100),
    shipping_province VARCHAR(100),
    shipping_postal_code VARCHAR(20),
    shipping_country VARCHAR(50),
    shipping_phone VARCHAR(20),
    
    -- Billing Address (snapshot)
    billing_first_name VARCHAR(100),
    billing_last_name VARCHAR(100),
    billing_company VARCHAR(100),
    billing_address_line1 TEXT,
    billing_address_line2 TEXT,
    billing_city VARCHAR(100),
    billing_province VARCHAR(100),
    billing_postal_code VARCHAR(20),
    billing_country VARCHAR(50),
    billing_phone VARCHAR(20),
    
    notes TEXT,
    shipped_at TIMESTAMP,
    delivered_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Order Items Table
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(id) ON DELETE CASCADE,
    product_id INT REFERENCES products(id),
    variant_id INT REFERENCES product_variants(id),
    product_name VARCHAR(255) NOT NULL, -- Snapshot
    variant_name VARCHAR(100), -- Snapshot
    sku VARCHAR(50) NOT NULL, -- Snapshot
    quantity INT NOT NULL,
    unit_price NUMERIC(10,2) NOT NULL,
    total_price NUMERIC(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Payments Table
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(id) ON DELETE CASCADE,
    payment_method VARCHAR(50) NOT NULL, -- ecocash, visa, mastercard, paypal
    payment_provider VARCHAR(50), -- stripe, paypal, ecocash
    transaction_id VARCHAR(255),
    amount NUMERIC(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    status VARCHAR(50) DEFAULT 'pending', -- pending, completed, failed, refunded
    gateway_response TEXT,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Coupons Table
CREATE TABLE IF NOT EXISTS coupons (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    type VARCHAR(20) NOT NULL, -- percentage, fixed_amount, free_shipping
    value NUMERIC(10,2) NOT NULL,
    minimum_amount NUMERIC(10,2),
    maximum_discount NUMERIC(10,2),
    usage_limit INT,
    usage_count INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    starts_at TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Analytics Events Table
CREATE TABLE IF NOT EXISTS analytics_events (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    session_id VARCHAR(100),
    event_type VARCHAR(50) NOT NULL, -- page_view, product_view, add_to_cart, purchase
    event_data JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Search Logs Table
CREATE TABLE IF NOT EXISTS search_logs (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    query VARCHAR(255) NOT NULL,
    results_count INT DEFAULT 0,
    filters_applied JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Notifications Table
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL, -- order_update, promotion, review_reminder
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    meta_data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Features Table
CREATE TABLE IF NOT EXISTS features (
    id SERIAL PRIMARY KEY,
    icon VARCHAR(50) NOT NULL,
    text VARCHAR(100) NOT NULL,
    subtext VARCHAR(100),
    bg_color VARCHAR(50),
    icon_color VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Stats Table
CREATE TABLE IF NOT EXISTS stats (
    id SERIAL PRIMARY KEY,
    icon VARCHAR(50) NOT NULL,
    number VARCHAR(20) NOT NULL,
    label VARCHAR(100) NOT NULL,
    color VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Social Links Table
CREATE TABLE IF NOT EXISTS social_links (
    id SERIAL PRIMARY KEY,
    icon VARCHAR(50) NOT NULL,
    href VARCHAR(255) NOT NULL,
    label VARCHAR(50) NOT NULL,
    color VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Quick Links Categories Table
CREATE TABLE IF NOT EXISTS quick_link_categories (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    icon VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Quick Links Table
CREATE TABLE IF NOT EXISTS quick_links (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES quick_link_categories(id),
    name VARCHAR(100) NOT NULL,
    icon VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Payment Methods Table
CREATE TABLE IF NOT EXISTS payment_methods (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Contact Info Table
CREATE TABLE IF NOT EXISTS contact_info (
    id SERIAL PRIMARY KEY,
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    weekday_hours VARCHAR(100),
    weekend_hours VARCHAR(100),
    phone VARCHAR(50),
    phone_href VARCHAR(50),
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Promo Messages Table
CREATE TABLE IF NOT EXISTS promo_messages (
    id SERIAL PRIMARY KEY,
    icon VARCHAR(50),
    text TEXT NOT NULL,
    cta VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Suppliers Table
CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    logo VARCHAR(500),
    category VARCHAR(100),
    featured BOOLEAN DEFAULT false,
    partner_since VARCHAR(20),
    rating DECIMAL(2,1),
    growth VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Store Services Table (Many-to-Many relationship)
CREATE TABLE IF NOT EXISTS store_services (
    id SERIAL PRIMARY KEY,
    store_id INTEGER REFERENCES stores(id),
    service_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Search Queries Table
CREATE TABLE IF NOT EXISTS search_queries (
    id SERIAL PRIMARY KEY,
    query_text VARCHAR(500) NOT NULL,
    user_id INTEGER,
    session_id VARCHAR(100),
    results_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Traffic Sources Table
CREATE TABLE IF NOT EXISTS traffic_sources (
    id SERIAL PRIMARY KEY,
    source VARCHAR(100) NOT NULL,
    medium VARCHAR(100),
    campaign VARCHAR(200),
    sessions INTEGER DEFAULT 0,
    users INTEGER DEFAULT 0,
    bounce_rate DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Recent Activity Table
CREATE TABLE IF NOT EXISTS recent_activity (
    id SERIAL PRIMARY KEY,
    activity_type VARCHAR(50) NOT NULL,
    description TEXT,
    user_id INTEGER,
    meta_data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Newsletter Subscribers Table
CREATE TABLE IF NOT EXISTS newsletter_subscribers (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    subscribed_at TIMESTAMP DEFAULT NOW(),
    unsubscribed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Event Types Table
CREATE TABLE IF NOT EXISTS event_types (
    id SERIAL PRIMARY KEY,
    event_name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Events Table
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    event_type_id INTEGER REFERENCES event_types(id),
    user_id INTEGER,
    session_id VARCHAR(100),
    meta_data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Conversion Funnel Table
CREATE TABLE IF NOT EXISTS conversion_funnel (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    visitors INTEGER DEFAULT 0,
    product_views INTEGER DEFAULT 0,
    add_to_cart INTEGER DEFAULT 0,
    add_to_wishlist INTEGER DEFAULT 0,
    checkout INTEGER DEFAULT 0,
    purchase INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Hero Images Table
CREATE TABLE IF NOT EXISTS hero_images (
    id SERIAL PRIMARY KEY,
    image_url TEXT NOT NULL,
    alt_text VARCHAR(255),
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Hero Config Table
CREATE TABLE IF NOT EXISTS hero_config (
    id SERIAL PRIMARY KEY,
    config_name VARCHAR(100) UNIQUE NOT NULL, -- e.g., 'main_hero', 'seasonal_hero'
    title_primary VARCHAR(255) NOT NULL,
    title_secondary VARCHAR(255) NOT NULL,
    subtitle VARCHAR(255),
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Hero Buttons Table
CREATE TABLE IF NOT EXISTS hero_buttons (
    id SERIAL PRIMARY KEY,
    hero_config_id INTEGER REFERENCES hero_config(id) ON DELETE CASCADE,
    button_type VARCHAR(50) NOT NULL, -- 'primary' or 'secondary'
    button_text VARCHAR(100) NOT NULL,
    button_icon VARCHAR(50), -- icon name/identifier
    button_url VARCHAR(500),
    button_action VARCHAR(100), -- e.g., 'shop_now', 'view_showcase'
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Hero Price Tags Table
CREATE TABLE IF NOT EXISTS hero_price_tags (
    id SERIAL PRIMARY KEY,
    hero_config_id INTEGER REFERENCES hero_config(id) ON DELETE CASCADE,
    label VARCHAR(50) NOT NULL,
    price VARCHAR(20) NOT NULL,
    currency_code VARCHAR(3) DEFAULT 'USD',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_products_search 
ON products USING gin(to_tsvector('english', name || ' ' || description));

CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id, is_active);
CREATE INDEX IF NOT EXISTS idx_products_price ON products(price) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_products_rating ON products(rating DESC) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders(user_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cart_items_user ON cart_items(user_id);
CREATE INDEX IF NOT EXISTS idx_addresses_user_default ON addresses(user_id, is_default);
CREATE INDEX IF NOT EXISTS idx_hero_images_active_order ON hero_images(is_active, display_order);
CREATE INDEX IF NOT EXISTS idx_hero_config_active ON hero_config(is_active);
CREATE INDEX IF NOT EXISTS idx_hero_buttons_config_type ON hero_buttons(hero_config_id, button_type);

-- Set sequence starting values
SELECT setval('categories_id_seq', 1, false);
SELECT setval('subcategories_id_seq', 1, false);
SELECT setval('products_id_seq', 1, false);
SELECT setval('product_images_id_seq', 1, false);
SELECT setval('product_variants_id_seq', 1, false);
SELECT setval('brands_id_seq', 1, false);
SELECT setval('stores_id_seq', 1, false);
SELECT setval('product_attributes_id_seq', 1, false);
SELECT setval('users_id_seq', 1, false);
SELECT setval('product_reviews_id_seq', 1, false);
SELECT setval('addresses_id_seq', 1, false);
SELECT setval('cart_items_id_seq', 1, false);
SELECT setval('wishlist_id_seq', 1, false);
SELECT setval('orders_id_seq', 1, false);
SELECT setval('order_items_id_seq', 1, false);
SELECT setval('payments_id_seq', 1, false);
SELECT setval('coupons_id_seq', 1, false);
SELECT setval('analytics_events_id_seq', 1, false);
SELECT setval('search_logs_id_seq', 1, false);
SELECT setval('notifications_id_seq', 1, false);
SELECT setval('features_id_seq', 1, false);
SELECT setval('stats_id_seq', 1, false);
SELECT setval('social_links_id_seq', 1, false);
SELECT setval('quick_link_categories_id_seq', 1, false);
SELECT setval('quick_links_id_seq', 1, false);
SELECT setval('payment_methods_id_seq', 1, false);
SELECT setval('contact_info_id_seq', 1, false);
SELECT setval('promo_messages_id_seq', 1, false);
SELECT setval('suppliers_id_seq', 1, false);
SELECT setval('store_services_id_seq', 1, false);
SELECT setval('search_queries_id_seq', 1, false);
SELECT setval('traffic_sources_id_seq', 1, false);
SELECT setval('recent_activity_id_seq', 1, false);
SELECT setval('newsletter_subscribers_id_seq', 1, false);
SELECT setval('event_types_id_seq', 1, false);
SELECT setval('events_id_seq', 1, false);
SELECT setval('conversion_funnel_id_seq', 1, false);
SELECT setval('hero_images_id_seq', 1, false);
SELECT setval('hero_config_id_seq', 1, false);
SELECT setval('hero_buttons_id_seq', 1, false);
SELECT setval('hero_price_tags_id_seq', 1, false);
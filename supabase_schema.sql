-- SQL Schema for Peucar App (Supabase)

-- 1. Table: Pedidos
CREATE TABLE IF NOT EXISTS pedidos (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    fecha TEXT NOT NULL,
    proveedor TEXT NOT NULL,
    repuesto TEXT NOT NULL, -- New mandatory column
    estado TEXT DEFAULT 'Pendiente' CHECK (estado IN ('Pendiente', 'Parcial', 'Completado')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Table: Items (Order items)
CREATE TABLE IF NOT EXISTS items (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    pedido_id BIGINT REFERENCES pedidos(id) ON DELETE CASCADE,
    codigo TEXT NOT NULL,
    cantidad_pedida NUMERIC NOT NULL,
    cantidad_entregada NUMERIC DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Table: Documentos (History of scanned invoices/remitos)
CREATE TABLE IF NOT EXISTS documentos_historia (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    proveedor TEXT,
    documento_id TEXT UNIQUE, -- number of invoice/remito
    fecha TEXT,
    monto TEXT,
    estado TEXT,
    is_remito BOOLEAN DEFAULT FALSE,
    remito_vinculado TEXT,
    items_json JSONB, -- list of items scanned
    totals_json JSONB, -- subtotal/total info
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Realtime: Enable for orders to sync PC/Mobile
-- (Requires manual check in Supabase dashboard for standard usage, but these hints help)
-- ALTER PUBLICATION supabase_realtime ADD TABLE pedidos;
-- ALTER PUBLICATION supabase_realtime ADD TABLE items;
-- ALTER PUBLICATION supabase_realtime ADD TABLE documentos_historia;
-- ALTER PUBLICATION supabase_realtime ADD TABLE ocr_tasks;

-- 4. Table: OCR Tasks (Queue for Local processing)
CREATE TABLE IF NOT EXISTS ocr_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'error')),
    image_url TEXT NOT NULL, -- Path in Supabase Storage bucket 'scans'
    result_json JSONB, -- Final parsed result for UI
    error_msg TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Note: In Supabase Dashboard, create a PUBLIC bucket named 'scans'.
-- No RLS needed for now if public, but for production use 'authenticated' only.

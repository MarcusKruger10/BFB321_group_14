-- =====================================================================
-- Pharmaceutical Stock Level Tracker - seed / demo data
-- Load AFTER schema.sql. All dates are relative to the day you load it.
-- Demo login for every user: password  Pharma@2026
-- =====================================================================
SET NAMES utf8mb4;
START TRANSACTION;

INSERT INTO users (user_id, username, password_hash, full_name, role) VALUES
  (1, 'admin',      'scrypt:32768:8:1$BtC42vSoM66xHnXA$ad9fbe11213b7a237fd6f975ade20fe5407a989c98d5a3551d64031cf2e839b9d167e837534c2af9c4625a3f9197d9a3547f0cf05bd151dba1211d7969181701', 'System Administrator', 'admin'),
  (2, 'pharmacist', 'scrypt:32768:8:1$BtC42vSoM66xHnXA$ad9fbe11213b7a237fd6f975ade20fe5407a989c98d5a3551d64031cf2e839b9d167e837534c2af9c4625a3f9197d9a3547f0cf05bd151dba1211d7969181701', 'Thandi Mokoena',       'pharmacist'),
  (3, 'assistant',  'scrypt:32768:8:1$BtC42vSoM66xHnXA$ad9fbe11213b7a237fd6f975ade20fe5407a989c98d5a3551d64031cf2e839b9d167e837534c2af9c4625a3f9197d9a3547f0cf05bd151dba1211d7969181701', 'Pieter van Wyk',       'assistant');

  INSERT INTO categories (category_id, name, description) VALUES
  (1, 'Antibiotics', 'Anti-infective agents'),
  (2, 'Analgesics', 'Pain and fever relief'),
  (3, 'Antidiabetics', 'Blood-glucose control'),
  (4, 'Antihistamines', 'Allergy relief'),
  (5, 'Cardiovascular', 'Blood pressure and cholesterol'),
  (6, 'Gastrointestinal', 'Acid reflux and ulcer treatment'),
  (7, 'Respiratory', 'Asthma and COPD'),
  (8, 'Cough & Cold', 'Cough, cold and flu preparations');

INSERT INTO suppliers (supplier_id, name, contact_name, phone, email) VALUES
  (1, 'Highveld Pharmaceutical Wholesalers', 'Sipho Ndlovu', '011 555 0142', 'orders@highveldpharma.example'),
  (2, 'Coastal Medical Distributors', 'Anika Pillay', '031 555 0178', 'sales@coastalmed.example'),
  (3, 'Jacaranda Pharma Supply', 'Lerato Khumalo', '012 555 0199', 'supply@jacarandapharma.example');

  -- reorder_point_override is NULL (use the calculated reorder point) except where a pharmacist set one
INSERT INTO products (product_id, sku, name, strength, dosage_form, pack_size, category_id, unit_cost, unit_price,
  service_level, reorder_point_override, ordering_cost, holding_cost_rate, shelf_life_days) VALUES
  (1, 'AMX-500', 'Amoxicillin', '500mg', 'capsule', 15, 1, 1.85, 3.40, 0.950, NULL, 150.00, 0.2000, 404),
  (2, 'PCM-500', 'Paracetamol', '500mg', 'tablet', 20, 2, 0.32, 0.75, 0.950, NULL, 150.00, 0.2000, 627),
  (3, 'MET-850', 'Metformin', '850mg', 'tablet', 30, 3, 0.55, 1.10, 0.950, NULL, 150.00, 0.2000, 405),
  (4, 'IBU-200', 'Ibuprofen', '200mg', 'tablet', 24, 2, 0.48, 1.05, 0.950, 120, 150.00, 0.2000, 695),
  (5, 'CTZ-010', 'Cetirizine', '10mg', 'tablet', 10, 4, 0.90, 2.20, 0.950, NULL, 150.00, 0.2000, 340),
  (6, 'ATV-020', 'Atorvastatin', '20mg', 'tablet', 30, 5, 1.20, 2.60, 0.950, NULL, 150.00, 0.2000, 632),
  (7, 'AML-005', 'Amlodipine', '5mg', 'tablet', 30, 5, 0.40, 0.95, 0.950, NULL, 150.00, 0.2000, 693),
  (8, 'ENA-010', 'Enalapril', '10mg', 'tablet', 30, 5, 0.35, 0.85, 0.950, NULL, 150.00, 0.2000, 456),
  (9, 'OMP-020', 'Omeprazole', '20mg', 'capsule', 28, 6, 0.60, 1.45, 0.950, NULL, 150.00, 0.2000, 396),
  (10, 'SAL-100', 'Salbutamol Inhaler', '100mcg', 'inhaler', 1, 7, 38.00, 72.00, 0.990, NULL, 250.00, 0.2000, 473),
  (11, 'LOS-050', 'Losartan', '50mg', 'tablet', 30, 5, 0.70, 1.60, 0.950, NULL, 150.00, 0.2000, 528),
  (12, 'CGH-100', 'Dextromethorphan Cough Syrup', '100ml', 'syrup', 1, 8, 24.50, 49.90, 0.950, NULL, 250.00, 0.2000, 438);

INSERT INTO product_suppliers (product_id, supplier_id, supplier_sku, lead_time_days, supplier_cost, is_preferred) VALUES
  (1, 1, 'S1-AMX-500', 2, 1.85, TRUE),   (1, 2, 'S2-AMX-500', 4, 1.96, FALSE),
  (2, 1, 'S1-PCM-500', 2, 0.32, TRUE),   (2, 3, 'S3-PCM-500', 3, 0.34, FALSE),
  (3, 2, 'S2-MET-850', 5, 0.55, TRUE),   (4, 1, 'S1-IBU-200', 2, 0.48, TRUE),
  (5, 3, 'S3-CTZ-010', 4, 0.90, TRUE),   (6, 2, 'S2-ATV-020', 5, 1.20, TRUE),
  (6, 1, 'S1-ATV-020', 3, 1.27, FALSE),  (7, 2, 'S2-AML-005', 5, 0.40, TRUE),
  (8, 3, 'S3-ENA-010', 4, 0.35, TRUE),   (9, 1, 'S1-OMP-020', 3, 0.60, TRUE),
  (9, 3, 'S3-OMP-020', 4, 0.64, FALSE),  (10, 2, 'S2-SAL-100', 7, 38.00, TRUE),
  (11, 3, 'S3-LOS-050', 4, 0.70, TRUE),  (12, 1, 'S1-CGH-100', 3, 24.50, TRUE);
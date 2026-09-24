import { CapacitorSQLite, SQLiteConnection } from '@capacitor-community/sqlite';

const sqlite = new SQLiteConnection(CapacitorSQLite);
let db = null;

async function ensureColumn(table, column, definition) {
  const rows = await query(`PRAGMA table_info(${table})`);
  if (!rows.some(row => row.name === column)) {
    await execute(`ALTER TABLE ${table} ADD COLUMN ${column} ${definition}`);
  }
}

function newSyncId(prefix) {
  return `${prefix}-${crypto.randomUUID()}`;
}

const SCHEMA = `
CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  phone TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY,
  contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK(type IN ('lent', 'borrowed')),
  amount REAL NOT NULL CHECK(amount > 0),
  currency TEXT NOT NULL DEFAULT 'USD',
  date TEXT NOT NULL,
  due_date TEXT,
  note TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY,
  transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
  amount REAL NOT NULL CHECK(amount > 0),
  date TEXT NOT NULL,
  note TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_contact ON transactions(contact_id);
CREATE INDEX IF NOT EXISTS idx_payments_transaction ON payments(transaction_id);
CREATE TABLE IF NOT EXISTS sync_queue (id INTEGER PRIMARY KEY AUTOINCREMENT, entity TEXT NOT NULL, entity_id INTEGER NOT NULL, action TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

INSERT OR IGNORE INTO app_settings (key, value) VALUES
  ('feature_contacts', '1'),
  ('feature_debts', '1'),
  ('feature_payments', '1'),
  ('feature_history', '1'),
  ('feature_delete', '1'),
  ('feature_multi_currency', '1'),
  ('feature_due_dates', '1');
`;

export async function initDB() {
  if (db) return;
  await sqlite.createConnection('carnet-dettes', false, 'no-encryption', 1, false);
  db = await sqlite.retrieveConnection('carnet-dettes', false);
  await db.open();
  await db.execute('PRAGMA foreign_keys = ON;');
  await db.execute(SCHEMA);
  await ensureColumn('contacts', 'updated_at', 'DATETIME');
  await ensureColumn('contacts', 'sync_id', 'TEXT');
  await ensureColumn('transactions', 'sync_id', 'TEXT');
  await ensureColumn('payments', 'sync_id', 'TEXT');
}

export async function getSetting(key, fallback = null) {
  const rows = await query('SELECT value FROM app_settings WHERE key = ?', [key]);
  return rows.length ? rows[0].value : fallback;
}

export async function setSetting(key, value) {
  await execute('INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', [key, String(value)]);
}

export async function getSettings() {
  const rows = await query('SELECT key, value FROM app_settings ORDER BY key');
  return Object.fromEntries(rows.map(r => [r.key, r.value]));
}

export async function closeDB() {
  if (db) {
    await sqlite.closeConnection('carnet-dettes', false);
    db = null;
  }
}

export async function execute(sql, values = []) {
  if (!db) throw new Error('DB not initialized');
  return db.run(sql, values, false);
}

export async function query(sql, values = []) {
  if (!db) throw new Error('DB not initialized');
  const result = await db.query(sql, values);
  return result.values || [];
}

export async function createContact(name, phone = '') {
  const result = await execute(
    'INSERT INTO contacts (name, phone) VALUES (?, ?)',
    [name.trim(), phone.trim()]
  );
  return result.lastID;
}

export async function getContacts() {
  return query('SELECT * FROM contacts ORDER BY name COLLATE NOCASE ASC');
}

export async function updateContact(id, name, phone = '') {
  await execute(
    'UPDATE contacts SET name = ?, phone = ? WHERE id = ?',
    [name.trim(), phone.trim(), id]
  );
}

export async function deleteContact(id) {
  await execute('DELETE FROM contacts WHERE id = ?', [id]);
}

export async function createTransaction(contactId, type, amount, currency, date, dueDate, note = '') {
  const result = await execute(
    `INSERT INTO transactions
      (contact_id, type, amount, currency, date, due_date, note, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)`,
    [contactId, type, amount, currency.trim().toUpperCase(), date, dueDate || null, note.trim()]
  );
  return result.lastID;
}

export async function getTransactions(contactId = null) {
  let sql = `
    SELECT t.*, c.name AS contact_name,
           COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.transaction_id = t.id), 0) AS paid_amount
    FROM transactions t
    JOIN contacts c ON c.id = t.contact_id
  `;
  const values = [];
  if (contactId !== null) {
    sql += ' WHERE t.contact_id = ?';
    values.push(contactId);
  }
  sql += ' ORDER BY t.date DESC, t.id DESC';
  return query(sql, values);
}

export async function getTransaction(id) {
  const rows = await getTransactions();
  return rows.find(t => Number(t.id) === Number(id)) || null;
}

export async function addPayment(transactionId, amount, date, note = '') {
  const transaction = await getTransaction(transactionId);
  if (!transaction) throw new Error('Dette introuvable');

  const remaining = Number(transaction.amount) - Number(transaction.paid_amount || 0);
  if (amount <= 0) throw new Error('Le montant doit être supérieur à zéro');
  if (amount > remaining + 0.005) {
    throw new Error(`Le paiement dépasse le solde restant de ${remaining.toFixed(2)} ${transaction.currency}`);
  }

  const result = await execute(
    'INSERT INTO payments (transaction_id, amount, date, note) VALUES (?, ?, ?, ?)',
    [transactionId, amount, date, note.trim()]
  );
  await execute('UPDATE transactions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?', [transactionId]);
  return result.lastID;
}

export async function getPayments(transactionId) {
  return query(
    'SELECT * FROM payments WHERE transaction_id = ? ORDER BY date DESC, id DESC',
    [transactionId]
  );
}

export async function deletePayment(id) {
  await execute('DELETE FROM payments WHERE id = ?', [id]);
}

export async function deleteTransaction(id) {
  await execute('DELETE FROM transactions WHERE id = ?', [id]);
}

export async function getSummary() {
  const rows = await query(`
    SELECT t.currency, t.type, t.amount,
           COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.transaction_id = t.id), 0) AS paid_amount
    FROM transactions t
  `);

  const summary = {};
  for (const row of rows) {
    const remaining = Math.max(0, Number(row.amount) - Number(row.paid_amount || 0));
    if (remaining <= 0.005) continue;
    const currency = row.currency || 'USD';
    if (!summary[currency]) {
      summary[currency] = { currency, to_receive: 0, to_pay: 0 };
    }
    if (row.type === 'lent') summary[currency].to_receive += remaining;
    else summary[currency].to_pay += remaining;
  }

  return Object.values(summary).map(item => ({
    ...item,
    to_receive: Number(item.to_receive.toFixed(2)),
    to_pay: Number(item.to_pay.toFixed(2)),
    net: Number((item.to_receive - item.to_pay).toFixed(2))
  }));
}

export async function getDashboardStats() {
  const transactions = await getTransactions();
  const today = new Date().toISOString().slice(0, 10);
  let overdue = 0;
  let totalOpen = 0;

  for (const t of transactions) {
    const remaining = Number(t.amount) - Number(t.paid_amount || 0);
    if (remaining > 0.005) {
      totalOpen++;
      if (t.due_date && t.due_date < today) overdue++;
    }
  }

  return { contacts: (await getContacts()).length, transactions: transactions.length, open: totalOpen, overdue };
}

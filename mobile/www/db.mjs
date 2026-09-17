import { CapacitorSQLite, SQLiteConnection } from '@capacitor-community/sqlite';

const sqlite = new SQLiteConnection(CapacitorSQLite);
let db = null;

const SCHEMA = `
CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  phone TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  pending_create INTEGER DEFAULT 0,
  pending_update INTEGER DEFAULT 0,
  pending_delete INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY,
  contact_id INTEGER NOT NULL REFERENCES contacts(id),
  type TEXT NOT NULL,
  amount REAL NOT NULL,
  currency TEXT DEFAULT 'USD',
  date TEXT NOT NULL,
  due_date TEXT,
  note TEXT,
  status TEXT DEFAULT 'unpaid',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  pending_create INTEGER DEFAULT 0,
  pending_update INTEGER DEFAULT 0,
  pending_delete INTEGER DEFAULT 0
);
`;

export async function initDB() {
  try {
    await sqlite.createConnection('carnet-dettes', false, 'no-encryption', 1, false);
    db = await sqlite.retrieveConnection('carnet-dettes', false);
    await db.open();
    await db.execute(SCHEMA);
    console.log('Database initialized');
  } catch (error) {
    console.error('Failed to init DB:', error);
    throw error;
  }
}

export async function closeDB() {
  if (db) await sqlite.closeConnection('carnet-dettes', false);
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

// CRUD operations
export async function createContact(name, phone) {
  const result = await execute(
    'INSERT INTO contacts (name, phone, pending_create) VALUES (?, ?, 1)',
    [name, phone]
  );
  return result.lastID;
}

export async function getContacts() {
  return query('SELECT * FROM contacts WHERE pending_delete = 0 ORDER BY name ASC');
}

export async function updateContact(id, name, phone) {
  await execute(
    'UPDATE contacts SET name = ?, phone = ?, pending_update = 1 WHERE id = ?',
    [name, phone, id]
  );
}

export async function deleteContact(id) {
  await execute('UPDATE contacts SET pending_delete = 1 WHERE id = ?', [id]);
}

export async function createTransaction(contactId, type, amount, currency, date, dueDate, note) {
  const result = await execute(
    `INSERT INTO transactions (contact_id, type, amount, currency, date, due_date, note, pending_create)
     VALUES (?, ?, ?, ?, ?, ?, ?, 1)`,
    [contactId, type, amount, currency, date, dueDate, note]
  );
  return result.lastID;
}

export async function getTransactions(contactId = null) {
  let sql = 'SELECT * FROM transactions WHERE pending_delete = 0';
  const values = [];
  if (contactId) {
    sql += ' AND contact_id = ?';
    values.push(contactId);
  }
  sql += ' ORDER BY date DESC';
  return query(sql, values);
}

export async function updateTransaction(id, status, amount = null) {
  let sql = 'UPDATE transactions SET pending_update = 1';
  const values = [];
  if (status) {
    sql += ', status = ?';
    values.push(status);
  }
  if (amount !== null) {
    sql += ', amount = ?';
    values.push(amount);
  }
  sql += ' WHERE id = ?';
  values.push(id);
  await execute(sql, values);
}

export async function getPending() {
  const contacts = await query(
    'SELECT * FROM contacts WHERE pending_create = 1 OR pending_update = 1 OR pending_delete = 1'
  );
  const transactions = await query(
    'SELECT * FROM transactions WHERE pending_create = 1 OR pending_update = 1 OR pending_delete = 1'
  );
  return { contacts, transactions };
}

export async function clearPending(type, id) {
  await execute(
    `UPDATE ${type} SET pending_create = 0, pending_update = 0, pending_delete = 0 WHERE id = ?`,
    [id]
  );
}

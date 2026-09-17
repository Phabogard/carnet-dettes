# Offline-First Architecture

Carnet de Dettes uses an offline-first design with local SQLite + cloud sync.

## How It Works

### Local SQLite
All data lives in a local SQLite database on the device (via `@capacitor-community/sqlite`):
- Contacts
- Transactions (debts, payments)
- Sync flags (pending_create, pending_update, pending_delete)

### Sync Mechanism
**Write-through pattern:**
1. User action → Write to local SQLite immediately
2. Sync manager detects `pending_*` flags
3. Async push to backend API (batched)
4. On success: clear pending flags, refresh UI
5. On failure: retry with exponential backoff

### Reconnection Logic
1. App detects network state (Capacitor Network plugin)
2. On reconnect: fetch server state (GET /summary)
3. Merge strategy: Server always wins for missing data; local pending changes are retried
4. Resolved conflicts show in logs and UI toast

## Network Status Handling

```javascript
// sync.mjs monitors Capacitor.Network
Network.addListener('networkStatusChange', (status) => {
  if (status.connected) {
    syncManager.pushPending(); // Retry pending changes
  }
});
```

## Configuration

Server API URL is configurable in-app:
1. Click the status indicator (top-right corner)
2. Enter API base URL (e.g., `http://10.0.2.2:8000`)
3. Click "Test & Sync" to verify
4. Stored in localStorage as `API_URL`

## Guarantees

- **Eventually consistent**: All local changes sync when network is available
- **No data loss**: Pending operations are persisted before marking as synced
- **Readable offline**: View all data, make changes, sync later
- **Single source of truth**: Server is the authority for conflict resolution

## Data Schema

Local tables match the backend schema:
- `contacts` (id, name, phone, created_at, pending_create, pending_update, pending_delete)
- `transactions` (id, contact_id, type, amount, currency, date, due_date, note, status, created_at, updated_at, pending_*)

Pending flags are booleans; the sync manager checks them on startup and every 30 seconds.

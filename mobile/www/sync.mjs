import * as db from './db.mjs';
import { Network } from '@capacitor/network';

let API_URL = localStorage.getItem('API_URL') || 'http://localhost:8000';
let syncInProgress = false;
let retryCount = 0;
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000;

export function setApiUrl(url) {
  API_URL = url;
  localStorage.setItem('API_URL', url);
}

export function getApiUrl() {
  return API_URL;
}

export async function testConnection() {
  try {
    const response = await fetch(`${API_URL}/summary`);
    return response.ok;
  } catch (error) {
    return false;
  }
}

export async function initSyncMonitor() {
  // Check network status on start
  await checkAndSync();

  // Monitor network changes
  Network.addListener('networkStatusChange', async (status) => {
    if (status.connected && !syncInProgress) {
      await checkAndSync();
    }
  });

  // Periodic sync every 30 seconds
  setInterval(async () => {
    if (!syncInProgress) {
      await checkAndSync();
    }
  }, 30000);
}

async function checkAndSync() {
  const pending = await db.getPending();
  if (pending.contacts.length > 0 || pending.transactions.length > 0) {
    await pushChanges();
  }
}

export async function pushChanges() {
  if (syncInProgress) return;
  syncInProgress = true;

  try {
    const pending = await db.getPending();

    // Push contact changes
    for (const contact of pending.contacts) {
      if (contact.pending_delete) {
        await apiCall(`DELETE /contacts/${contact.id}`);
      } else if (contact.pending_create) {
        await apiCall(`POST /contacts`, { name: contact.name, phone: contact.phone });
      } else if (contact.pending_update) {
        await apiCall(`PUT /contacts/${contact.id}`, { name: contact.name, phone: contact.phone });
      }
      await db.clearPending('contacts', contact.id);
    }

    // Push transaction changes
    for (const txn of pending.transactions) {
      if (txn.pending_delete) {
        await apiCall(`DELETE /transactions/${txn.id}`);
      } else if (txn.pending_create) {
        await apiCall(`POST /transactions`, {
          contact_id: txn.contact_id,
          type: txn.type,
          amount: txn.amount,
          currency: txn.currency,
          date: txn.date,
          due_date: txn.due_date,
          note: txn.note
        });
      } else if (txn.pending_update) {
        await apiCall(`PUT /transactions/${txn.id}`, { status: txn.status, amount: txn.amount });
      }
      await db.clearPending('transactions', txn.id);
    }

    retryCount = 0;
    console.log('Sync complete');
    updateSyncStatus('✓ Synced');
  } catch (error) {
    console.error('Sync failed:', error);
    if (retryCount < MAX_RETRIES) {
      retryCount++;
      setTimeout(() => {
        syncInProgress = false;
        pushChanges();
      }, RETRY_DELAY * Math.pow(2, retryCount));
    }
    updateSyncStatus('✗ Offline');
  } finally {
    syncInProgress = false;
  }
}

async function apiCall(method, data = null) {
  const [httpMethod, endpoint] = method.split(' ');
  const url = `${API_URL}${endpoint}`;

  const options = {
    method: httpMethod,
    headers: { 'Content-Type': 'application/json' }
  };

  if (data) options.body = JSON.stringify(data);

  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

export async function pullSummary() {
  try {
    const summary = await apiCall('GET /summary');
    return summary;
  } catch (error) {
    console.error('Failed to fetch summary:', error);
    return null;
  }
}

function updateSyncStatus(status) {
  const badge = document.getElementById('sync-status');
  if (badge) badge.textContent = status;
}

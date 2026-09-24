# Carnet de Dettes

Suivi offline-first des prêts et emprunts : contacts, dettes multi-devises, règlements partiels, détection automatique des retards.

## Stack

**Backend** : Python + FastAPI + SQLite (SQLAlchemy & Pydantic)
**App Mobile** : Capacitor + Vanilla JS + SQLite local
**Mobile autonome** : SQLite local, fonctionnement hors ligne sans serveur ni API externe\n**Backend optionnel** : Python + FastAPI + SQLite pour une future synchronisation

## Structure

```
carnet-dettes/
├── app/
│   ├── database.py     # SQLite engine, sessions, Base
│   ├── models.py       # Contact → Debt → Payment en cascade
│   ├── schemas.py      # Pydantic v2 : validation & serialisation
│   └── main.py         # Routes FastAPI + assets statiques
├── mobile/             # Wrapper Capacitor Android
│   ├── www/
│   │   ├── index.html  # UI responsive (40KB minifiée)
│   │   ├── db.mjs      # Driver SQLite + CRUD local
│   │   └── sync.mjs    # Orchestration push/pull serveur
│   ├── package.json
│   ├── capacitor.config.json
│   ├── README-ANDROID.md
│   └── README-OFFLINE.md
├── static/             # Assets servés par FastAPI
├── requirements.txt
└── README.md
```

## Démarrer

### Backend

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# En dev
uvicorn app.main:app --reload --host 0.0.0.0

# Interface : http://127.0.0.1:8000/
# Docs API  : http://127.0.0.1:8000/docs
```

Le backend est facultatif pour l'application Android autonome.

### App Android

```bash
cd mobile
npm install

# Générer le projet Capacitor Android
npm run android:add

# Appliquer les patchs réseau (voir README-ANDROID.md)

# Compiler et lancer sur appareil/émulateur
npm run run
```

**Première ouverture** : Configuration serveur (clic sur le badge d'état en haut à gauche).
- Émulateur : `http://10.0.2.2:8000`
- Téléphone réel : `http://IP-DU-PC:8000`

## Architecture

### Données

**Tables** : contacts, debts, payments

**Champs de sync** :
- `local_id` : UUID temporaire, persistant en SQLite
- `server_id` : ID du serveur une fois synchée
- `synced` : 0 = change local, 1 = synchronisé
- `deleted_at` : soft delete, marque l'entité pour suppression

**Dérivées** (jamais stockées) :
- Statut dette : `paid`, `unpaid`, `partial`, `overdue` (calcul depuis remboursements + échéance)
- Solde par devise : jamais additionnées, groupées
- Retard : jours après l'échéance

### Offline-first

1. **Write-through local** : tout est d'abord écrit en SQLite
2. **Async push** : envoie au serveur en arrière-plan
3. **Guaranteed delivery** : rejeu à la reconnexion si échec

```
UI → Store local → DB SQLite (immédiat, visible)
              ↓
              Sync (async) → API FastAPI → SQLite serveur
```

**Badge d'état** :
- Hors ligne : aucune connexion, données locales uniquement
- En ligne : serveur joignable, synchro en cours ou idle
- Synchro… : push/pull en cours

**Badges « local »** : sur chaque entité non encore synchronisée.

### API

| Méthode | Route | Rôle |
|---------|-------|------|
| GET | `/api/contacts?q=` | Lister, chercher |
| POST | `/api/contacts` | Créer |
| PUT | `/api/contacts/{id}` | Modifier |
| DELETE | `/api/contacts/{id}?force=` | Supprimer |
| GET | `/api/debts?contact_id=&direction=&status=&currency=` | Lister, filtrer |
| POST | `/api/debts` | Enregistrer |
| PUT | `/api/debts/{id}` | Modifier |
| DELETE | `/api/debts/{id}` | Supprimer |
| POST | `/api/debts/{id}/payments` | Reglement partiel |
| POST | `/api/debts/{id}/settle` | Solder d'un coup |
| DELETE | `/api/payments/{id}` | Annuler reglement |
| GET | `/api/summary` | Totaux par devise |

## Choix techniques

- **Montants en Float** : suffisant pour un carnet perso ; pass to `Numeric(12,2)` + `Decimal` pour une compta réelle
- **Statut dérivé** : jamais stocké, donc impossible de desynchroniser
- **Devises jamais additionnées** : groupées par devise, pas de taux de change
- **Cascade ORM+SQL** : Contact → Debt → Payment, suppressions en cascade
- **CORS ouvert en dev** : restreignez `allow_origins` en production
- **SQLite local** : via `@capacitor-community/sqlite` (6.4.0+)
- **Sync simple** : "server wins" pour les conflits d'edit ; voir TODO pour CRDT

## Limitations actuelles

1. Pas de gestion elaborée des conflits (2 edits concurrents)
2. Pas de pagination en sync (tous les débts à chaque fois)
3. Pas de "last sync window" (charge tout depuis le début)
4. Schema locale figée (edit = delete/recreate l'app)
5. Mode offline sans serveur : démo en mémoire seulement (pas de persistance sans SQLite)

## Roadmap

- [ ] CRDT ou 3-way merge pour les conflits
- [ ] Pagination + "last sync" pour grandes bases
- [ ] Authentification (JWT + OAuth)
- [ ] Webhook pour push notifications
- [ ] Biais horaire : timestamps UTC rigoreux
- [ ] Tests (unittest backend, Jest UI)
- [ ] iOS via Capacitor iOS
- [ ] Déploiement Docker

## Development

### Backend

```bash
# Lancer les tests
python -m pytest  # TODO

# Format code
python -m black app/
python -m isort app/
```

### Mobile

```bash
# Après modif de www/index.html, sync avec static/
npm run sync:web

# Recharger l'app
npm run sync

# Ouvrir Android Studio
npm run open
```

## Licence

MIT

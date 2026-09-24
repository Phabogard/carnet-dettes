# Mode autonome hors ligne

L'application Android peut fonctionner **sans serveur, sans API externe, sans compte bancaire et sans carte bancaire**.

## Architecture

```
Interface Android
      |
      v
Capacitor
      |
      v
SQLite local du téléphone
      |
      +--> contacts
      +--> dettes
      +--> remboursements
```

Toutes les opérations principales sont locales :

- création et suppression de contacts ;
- création de dettes (« j'ai prêté » / « j'ai emprunté ») ;
- plusieurs devises ;
- échéances et détection des retards ;
- remboursements partiels ;
- historique des remboursements ;
- calcul des montants à recevoir et à payer.

Aucune requête HTTP n'est nécessaire pour utiliser ces fonctions.

## Persistance

La base SQLite est ouverte avec `@capacitor-community/sqlite`. Les données sont conservées sur l'appareil après fermeture de l'application.

Le schéma local utilise :

- `contacts`
- `transactions`
- `payments`

Les montants restant dus sont calculés à partir des remboursements ; l'application n'a donc pas besoin d'un serveur pour déterminer le statut d'une dette.

## Serveur FastAPI

Le backend Python présent dans le dépôt reste disponible comme **option séparée** pour une future synchronisation ou une utilisation multi-appareils.

Le mode autonome de l'application Android ne l'utilise pas.

## Dépendances

Le code mobile ne charge plus de script JavaScript depuis un CDN et ne nécessite pas d'API de paiement, de banque, de Firebase, de Supabase ou de service cloud pour son fonctionnement normal.

Pour compiler l'APK, il faut toujours l'environnement de développement Android/Capacitor ; cela ne signifie pas qu'un compte bancaire ou une carte bancaire est nécessaire.

## Test

Après installation :

1. Ouvrir l'application.
2. Ajouter un contact.
3. Ajouter une dette.
4. Fermer complètement l'application.
5. La rouvrir.
6. Vérifier que le contact et la dette sont toujours présents.
7. Ajouter un remboursement et vérifier que le solde diminue.


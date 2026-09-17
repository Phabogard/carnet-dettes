# Contributing to Carnet de Dettes

Thank you for your interest in contributing! Here's how to get started.

## Development Setup

### Backend
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Mobile (Capacitor)
```bash
cd mobile
npm install
npm run build:web
npx cap add android
npx cap sync
```

## Code Style

- Python: Follow PEP 8. Use type hints.
- JavaScript: Use ES modules, const/let (no var).
- SQL: Use SQLAlchemy ORM, avoid raw SQL.

## Testing

Before submitting a PR:
1. Verify all routes with the Swagger UI at http://localhost:8000/docs
2. Test sync logic: offline mode, reconnect, partial sync
3. Check Android APK builds without errors

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit with clear messages
4. Push and open a PR with a description of changes
5. Respond to review feedback

## Issues

Report bugs with:
- Reproduction steps
- OS and version
- Stack trace or error logs

## License

All contributions are under MIT license.

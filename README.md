# Stream Station Rewrite - v2
- Dev Env
    ` source .venv/bin/activate.fish `

- Run App
    `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

## NOTE:
- if changing the model, recreate the table, or just delete the existing `app.db`
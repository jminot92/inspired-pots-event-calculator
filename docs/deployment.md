# Streamlit Community Cloud deployment

Repository: `jminot92/inspired-pots-event-calculator` (private).
Branch: `main`. Entrypoint: `app.py`. Python: `3.12`.

Use Advanced settings on the Streamlit deployment form to set secrets:

```toml
APP_MODE = "simple"
AUTH_MODE = "password"
BOOTSTRAP_ADMIN_NAME = "Inspired Pots"
BOOTSTRAP_ADMIN_EMAIL = "your-sign-in-email"
BOOTSTRAP_ADMIN_PASSWORD = "your-unique-password-at-least-12-characters"
```

Replace the placeholders in Streamlit's secrets editor, never in Git. The first
admin is created from these settings when the database is empty. Keep these
secrets set: a sleeping/recreated hosted instance may create its database again.
Use Streamlit's app access settings to keep the internal calculator private.
Shopify and Google Maps API keys are not needed for the simple calculator.

`data/pottery_catalogue.json` is included as an indicative bundled catalogue.
Local databases, generated exports and secrets are excluded. Save/reopen remains
hidden; pottery choices and revised prices last only for the current session.

Local use: `run.ps1` or `python -m streamlit run app.py --server.address=127.0.0.1`.
The local launcher binds to loopback explicitly. Hosted use requires password
mode; local administrator access is rejected on a non-loopback server.

Pushes to the deployed branch automatically update the hosted app.

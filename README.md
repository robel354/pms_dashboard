# Recipient Dashboard

Recipient Dashboard is a modular Streamlit application for internal tracking across recipients, plots, trees and seedlings, training, documents, grievances, and nursery operations.

## Project structure

```text
recipient-dashboard/
  app.py                  # Streamlit entry point and top-level tab navigation
  requirements.txt        # Python dependencies
  .env.example            # Example environment variables
  startup.sh              # Azure App Service startup command
  tabs/                   # One module per dashboard section
  utils/                  # Shared config, auth, loaders, transforms, storage
  data/                   # Local CSV files for development
  .streamlit/
    config.toml           # Streamlit runtime defaults
```

Key modules:

- `tabs/`: dashboard UI per section
- `utils/config.py`: environment-driven settings
- `utils/auth.py`: login and authorization checks
- `utils/loaders.py`: cached CSV loading and validation
- `utils/storage.py`: local filesystem or Azure Blob Storage backend
- `utils/transforms.py`: shared cleaning and summary helpers

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env`.
4. Keep `AUTH_ENABLED=false` for local development unless you are configuring OIDC.
5. Start the app:

```bash
streamlit run app.py
```

## Local CSV files

By default, the app reads local CSV files from `data/`.

Place your files in [data](C:\Users\RobelBerhanu\Desktop\PMS dashboard\recipient-dashboard\data) using these names:

- `recipients.csv`
- `plots.csv`
- `training.csv`
- `documents.csv`
- `grievance_intake.csv`
- `grievance_resolution.csv`
- `nursery_batch_intake.csv`
- `nursery_qaqc.csv`

The loaders validate required columns and return empty DataFrames with warnings if a file is missing or malformed.

## Environment variables

The app reads configuration from `.env` and process environment variables.

Common settings:

- `APP_TITLE`: app title shown in Streamlit
- `DATA_DIR`: local directory for CSV files, default `data`
- `APP_ENV`: environment label such as `development` or `production`
- `AUTH_ENABLED`: set to `true` to require login
- `ALLOWED_EMAILS`: comma-separated allowlist of user emails
- `ALLOWED_DOMAINS`: comma-separated allowlist of email domains
- `USE_AZURE_STORAGE`: set to `true` to read files from Azure Blob Storage
- `AZURE_STORAGE_ACCOUNT_URL`: storage account URL
- `AZURE_BLOB_CONTAINER`: blob container name

Secrets such as OIDC client secrets should not go in `.env.example` or source control.

## Authentication setup

The app is prepared for Streamlit OIDC login with Microsoft Entra ID.

High-level flow:

1. Set `AUTH_ENABLED=true`.
2. Configure authorization rules with `ALLOWED_EMAILS` and/or `ALLOWED_DOMAINS`.
3. Add Streamlit OIDC settings to `.streamlit/secrets.toml`.
4. Register the correct redirect URI in Microsoft Entra ID.

Example `secrets.toml` shape:

```toml
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "strong-random-secret"

[auth.microsoft]
client_id = "your-client-id"
client_secret = "your-client-secret"
server_metadata_url = "https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration"
```

If the user is not signed in, the app shows a login prompt. If the user is signed in but not on the allowlist, the app shows an access denied message.

## Azure App Service deployment

The app is structured for Azure App Service with:

- `startup.sh` to bind Streamlit to `0.0.0.0:$PORT`
- `.streamlit/config.toml` for headless defaults
- environment-driven configuration

High-level deployment steps:

1. Deploy the app code to App Service.
2. Set App Settings for environment variables.
3. Add Streamlit OIDC secrets through your deployment secret store.
4. Set the startup command to `bash startup.sh`.

Typical App Settings:

- `SCM_DO_BUILD_DURING_DEPLOYMENT=true`
- `WEBSITES_PORT=8000`
- `AUTH_ENABLED=true`
- `USE_AZURE_STORAGE=true`
- `AZURE_STORAGE_ACCOUNT_URL=<account-url>`
- `AZURE_BLOB_CONTAINER=<container-name>`

## Azure Blob Storage integration

The app supports two storage modes:

1. Local filesystem via `DATA_DIR`
2. Azure Blob Storage via `utils/storage.py`

When `USE_AZURE_STORAGE=true`, CSV reads go through the Azure storage backend. The code is prepared for managed identity using `DefaultAzureCredential`, so credentials do not need to be hardcoded in the app.

Document links are also routed through the storage layer so private blob access can be implemented without changing the tab code.

## Sensitive data handling

- Keep OIDC secrets, cookie secrets, and any storage credentials out of source control.
- Prefer managed identity for Azure access instead of embedding secrets.
- Grievance screens hide sensitive complainant fields by default.
- Document access should be treated as private by default; do not assume blob URLs are public.
- Use allowlists with `ALLOWED_EMAILS` and `ALLOWED_DOMAINS` to restrict internal access.

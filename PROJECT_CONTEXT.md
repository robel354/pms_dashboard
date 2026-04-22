# Project Context

## Project

Recipient Dashboard is an internal Streamlit application for operational monitoring across recipients, plots, trees and seedlings, training, documents, grievances, and nursery workflows.

## Core entities

- `recipient_id`: primary recipient key used across recipient-centric views
- `plot_id`: used for plot records and linked documents
- `grievance_id`: links grievance intake and grievance resolution
- `batch_id`: links nursery batch intake and nursery QA/QC

## Required tabs

1. Recipient Overview
2. Trees & Seedlings
3. Training
4. Documents
5. Grievances
6. Nursery

## Architecture

- `app.py`: main Streamlit entry point with top-level tab navigation
- `tabs/`: one module per tab
- `utils/config.py`: environment-driven configuration
- `utils/auth.py`: authentication and authorization helpers
- `utils/loaders.py`: cached CSV loaders with validation
- `utils/storage.py`: storage abstraction for local files or Azure Blob Storage
- `utils/transforms.py`: shared normalization and summary helpers
- `data/`: local CSVs for development

## Storage model

The app is designed to support two storage modes:

1. Local filesystem via `DATA_DIR`
2. Private Azure Blob Storage via `utils/storage.py`

The rest of the app should use loaders and storage helpers rather than reading files directly.

## Authentication and access

Security expectations:

- authenticated users only
- authorized users only
- authorization via `ALLOWED_EMAILS` and `ALLOWED_DOMAINS`
- Streamlit OIDC login prepared for Microsoft Entra ID
- no secrets in source control

Current auth behavior:

- `require_login()` gates the app
- `user_is_authorized()` enforces allowlist/domain rules
- local development can run with `AUTH_ENABLED=false`

## Sensitive data handling

This app handles sensitive internal operational data.

Sensitive fields include:

- `complainant_name`
- `complainant_phone`
- `complainant_email`
- `complainant_meeting_place`
- `grievance_description`
- grievance photos
- signatures
- FCA scans
- GPS-linked plot records

Current handling rules:

- personal grievance data is masked by default in the UI
- grievance descriptions, photo references, signature references, and scan references are masked by default
- raw document and photo URLs are not exposed in the UI
- GPS-linked plot maps are hidden by default and require explicit reveal
- document access should assume private storage, not public URLs

## Important implementation notes

- Keep the MVP simple and readable
- Prefer defensive handling of missing columns and missing files
- All tabs should fail gracefully with helpful empty-state messages
- Avoid over-engineering
- Do not introduce public raw document access patterns
- Keep naming aligned with the core entity keys above

## Current datasets expected

- `recipients.csv`
- `plots.csv`
- `training.csv`
- `documents.csv`
- `grievance_intake.csv`
- `grievance_resolution.csv`
- `nursery_batch_intake.csv`
- `nursery_qaqc.csv`

## Good prompt to reuse in another tool

Use this project context:

- Internal Streamlit dashboard called Recipient Dashboard
- Tabs: Recipient Overview, Trees & Seedlings, Training, Documents, Grievances, Nursery
- Core keys: `recipient_id`, `plot_id`, `grievance_id`, `batch_id`
- Security-sensitive app: authenticated users only, authorized users only
- No public raw document URLs
- Private Azure Blob Storage design
- Mask personal and grievance-sensitive data by default
- Keep code modular, typed where reasonable, defensive, and MVP-simple

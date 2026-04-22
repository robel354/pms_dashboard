# Cursor Prompt

Use this as the working context for the project.

Recipient Dashboard is an internal Streamlit application for operational monitoring.

Required tabs:

1. Recipient Overview
2. Trees & Seedlings
3. Training
4. Documents
5. Grievances
6. Nursery

Core entity keys:

- `recipient_id`
- `plot_id`
- `grievance_id`
- `batch_id`

Important architecture:

- `app.py` is the main entry point
- `tabs/` contains one module per tab
- `utils/config.py` handles env-based settings
- `utils/auth.py` handles login and authorization
- `utils/loaders.py` handles cached CSV loading and validation
- `utils/storage.py` abstracts local files vs Azure Blob Storage
- `utils/transforms.py` contains shared cleanup and summary helpers

Security requirements:

- authenticated users only
- authorized users only
- no public raw document URLs
- private Azure storage model
- mask personal data by default in the UI

Sensitive fields and records:

- `complainant_name`
- `complainant_phone`
- `complainant_email`
- `complainant_meeting_place`
- `grievance_description`
- grievance photos
- signatures
- FCA scans
- GPS-linked plot records

Current expectations:

- keep the MVP simple
- fail gracefully when CSV files or columns are missing
- do not over-engineer
- preserve naming consistency around the core keys
- do not expose sensitive raw references in tables or links

Expected datasets:

- `recipients.csv`
- `plots.csv`
- `training.csv`
- `documents.csv`
- `grievance_intake.csv`
- `grievance_resolution.csv`
- `nursery_batch_intake.csv`
- `nursery_qaqc.csv`

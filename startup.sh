#!/usr/bin/env bash
set -e

PORT_VALUE="${PORT:-8000}"
exec python -m streamlit run app.py --server.port "${PORT_VALUE}" --server.address 0.0.0.0

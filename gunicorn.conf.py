import os

# Dynamic port binding from Render environment variable, fallback to 5000/8000
port = os.environ.get("PORT", "5000")
bind = f"0.0.0.0:{port}"

# Maintain configuration alignment with Procfile/render.yaml
workers = 2
threads = 4
timeout = 120

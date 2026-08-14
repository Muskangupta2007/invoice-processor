import os

# Dynamic port binding from Render environment variable, fallback to 5000/8000
port = os.environ.get("PORT", "5000")
bind = f"0.0.0.0:{port}"

# Dynamic workers/threads based on the environment to control RAM usage
if os.environ.get("RENDER") == "true":
    workers = 1
    threads = 4
else:
    workers = 2
    threads = 4
    
timeout = 120

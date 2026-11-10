import os

bind = "0.0.0.0:5000"
workers = 1
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gthread")
threads = int(os.environ.get("GUNICORN_THREADS", "400"))
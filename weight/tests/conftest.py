import os

# Force test DB overrides — these must win over whatever is in .env
os.environ.setdefault("DB_PORT", "3307")
os.environ.setdefault("DB_NAME", "weight_test")
os.environ["IN_FOLDER"] = "/tmp"  # unit tests use tmp_path anyway

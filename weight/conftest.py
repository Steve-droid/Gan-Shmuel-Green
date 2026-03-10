import sys, os
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_USER", "root")
os.environ.setdefault("DB_PASSWORD", "root")
os.environ.setdefault("DB_NAME", "weight_db")
os.environ.setdefault("DB_PORT", "3306")
sys.path.insert(0, os.path.dirname(__file__))
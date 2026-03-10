FROM mysql:8.0

# The SQL file is copied from the project root (build context = Gan-Shmuel-Green/).
# MySQL automatically runs any *.sql file found in /docker-entrypoint-initdb.d/
# the first time the container starts with an empty data volume.
COPY resources/db_schemas/multi-db/weightdb.sql /docker-entrypoint-initdb.d/01-weightdb.sql

#!/usr/bin/bash
set -e

# Create multiple databases if they don't exist
function create_db_if_not_exists() {
    local db_name="$1"
    echo "Checking if database '$db_name' exists..."
    if psql -U "$POSTGRES_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db_name'" | grep -q 1; then
        echo "Database '$db_name' already exists, skipping."
    else
        echo "Creating database '$db_name'..."
        psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE \"$db_name\";"
        echo "Database '$db_name' created successfully!"
    fi
}


function create_user() {
    local user="$1"
    local database="$2"
    local schema="public"

    psql -U "$POSTGRES_USER" -d postgres -c "CREATE USER \"$user\" WITH PASSWORD '$POSTGRES_PASSWORD' SUPERUSER;"
    psql -U "$POSTGRES_USER" -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE $database TO \"$user\";"
    psql -U "$POSTGRES_USER" -d postgres -c "GRANT ALL PRIVILEGES ON SCHEMA ${schema} TO ${user};"
}

create_db_if_not_exists "inngest"
create_db_if_not_exists "lang3s"
create_user "inngest" "inngest"
#!/usr/bin/bash
set -e

function create_db_if_not_exists() {
    local db_name="$1"
    echo "Checking if database '$db_name' exists..."

    if psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db_name'" | grep -q 1; then
        echo "Database '$db_name' already exists, skipping."
    else
        echo "Creating database '$db_name'..."
        psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE \"$db_name\";"
        echo "Database '$db_name' created successfully!"
    fi
}

function create_user() {
    local user="$1"
    local database="$2"
    local secret_file="$3"
    local schema="public"

    if [ ! -f "$secret_file" ]; then
        echo "Error: Secret file $secret_file not found!"
        exit 1
    fi
    local app_password=$(cat "$secret_file" | tr -d '\r\n')

    echo "Checking if user '$user' exists..."
    if psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$user'" | grep -q 1; then
        echo "User '$user' already exists, skipping creation."
    else
        echo "Creating user '$user'..."
        psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres -c "CREATE USER \"$user\" WITH PASSWORD '$app_password';"
    fi

    echo "Granting privileges to '$user' on database '$database'..."
    psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE \"$database\" TO \"$user\";"

    psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$database" -c "GRANT ALL PRIVILEGES ON SCHEMA ${schema} TO \"${user}\";"
}

create_db_if_not_exists "inngest"
create_db_if_not_exists "lang3s"
create_user "inngest" "inngest" "/run/secrets/inngest_db_password"
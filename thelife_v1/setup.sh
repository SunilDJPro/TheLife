#!/usr/bin/env bash
# ============================================
# TheLife — Setup Script
# Run this on your Ubuntu machine to get started.
# ============================================
set -e

echo "╔══════════════════════════════════════════╗"
echo "║        TheLife — Setup Script             ║"
echo "║  Live your life. Own every hour.          ║"
echo "╚══════════════════════════════════════════╝"
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# --- 1. System Dependencies ---
echo "→ Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip \
    postgresql postgresql-contrib redis-server libpq-dev

# --- 2. Python Virtual Environment ---
echo "→ Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  ✓ Python dependencies installed"

# --- 3. PostgreSQL Setup ---
echo "→ Setting up PostgreSQL..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='sunilprasath'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER sunilprasath WITH PASSWORD 'ros123456';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='thelife_db'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE thelife_db OWNER sunilprasath;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE thelife_db TO sunilprasath;"
echo "  ✓ PostgreSQL ready (thelife_db / sunilprasath)"

# --- 4. Environment File ---
if [ ! -f ".env" ]; then
    echo "→ Creating .env file..."
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    cat > .env << EOF
SECRET_KEY=${SECRET_KEY}
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=thelife_db
DB_USER=sunilprasath
DB_PASSWORD=ros123456
DB_HOST=localhost
DB_PORT=5432

REDIS_URL=redis://localhost:6379/0
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=ollama/gemma3:12b

VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_ADMIN_EMAIL=admin@thelife.local
FIELD_ENCRYPTION_KEY=${ENCRYPTION_KEY}
EOF
    echo "  ✓ .env created with generated keys"
else
    echo "  ✓ .env already exists"
fi

# --- 5. Django Migrations ---
echo "→ Running migrations..."
source venv/bin/activate
python manage.py makemigrations accounts activities work skills entertainment scoring --noinput
python manage.py migrate --noinput
echo "  ✓ Database migrated"

# --- 6. Seed Data ---
echo "→ Seeding activity categories..."
python manage.py seed_activities
echo "  ✓ Categories seeded"

# --- 7. Collect Static ---
echo "→ Collecting static files..."
python manage.py collectstatic --noinput -q
echo "  ✓ Static files collected"

# --- 8. Create Superuser ---
echo ""
echo "→ Creating admin user..."
echo "  (This will be the first user who can log in)"
python manage.py createsuperuser

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║            Setup Complete!                ║"
echo "╠══════════════════════════════════════════╣"
echo "║                                          ║"
echo "║  Start the server:                       ║"
echo "║    source venv/bin/activate               ║"
echo "║    python manage.py runserver             ║"
echo "║                                          ║"
echo "║  Start Celery (for background scoring):  ║"
echo "║    celery -A thelife worker -l info       ║"
echo "║    celery -A thelife beat -l info         ║"
echo "║                                          ║"
echo "║  Open: http://localhost:8000              ║"
echo "║                                          ║"
echo "║  Optional — Pull Ollama model:           ║"
echo "║    ollama pull gemma3:12b                 ║"
echo "║                                          ║"
echo "╚══════════════════════════════════════════╝"

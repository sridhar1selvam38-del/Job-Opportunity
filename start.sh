#!/bin/bash

# Ensure python_packages is in PYTHONPATH for all subshells and users
export PYTHONPATH="$(pwd)/python_packages:/python_packages:${PYTHONPATH:-}"

# 1. Support container policy-rc.d if running as root
if [ -f /usr/sbin/policy-rc.d ] && [ "$(id -u)" = "0" ]; then
  echo '#!/bin/sh' > /usr/sbin/policy-rc.d
  echo 'exit 0' >> /usr/sbin/policy-rc.d
  chmod +x /usr/sbin/policy-rc.d 2>/dev/null || true
fi

# 2. Check and auto-install Python dependencies if missing and root is available
if ! python3 -c "import flask, pymysql" >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
  echo "Installing Python & MariaDB packages..."
  DEBIAN_FRONTEND=noninteractive apt-get update -qq && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
    python3-flask python3-pymysql python3-werkzeug mariadb-server </dev/null >/dev/null 2>&1 || true
fi

# 3. If MariaDB is present and we have root privileges, ensure it is running
if command -v mariadbd >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
  service mariadb status >/dev/null 2>&1 || service mariadb start 2>/dev/null || true
  mysql -e "CREATE DATABASE IF NOT EXISTS jobpost_aggregator; CREATE USER IF NOT EXISTS 'jobuser'@'localhost' IDENTIFIED BY 'jobpass123'; ALTER USER 'jobuser'@'localhost' IDENTIFIED BY 'jobpass123'; GRANT ALL PRIVILEGES ON jobpost_aggregator.* TO 'jobuser'@'localhost'; FLUSH PRIVILEGES;" 2>/dev/null || true
fi

# 4. Ensure permissions for SQLite database and uploads directory
chmod 666 jobpost_aggregator.sqlite 2>/dev/null || true
chmod -R 777 static/uploads 2>/dev/null || true

# 5. Run database setup (works with MySQL if active, or ensures SQLite replica is ready)
python3 db_setup.py || true

# 6. Start web application
export PORT="${PORT:-3000}"
exec python3 app.py

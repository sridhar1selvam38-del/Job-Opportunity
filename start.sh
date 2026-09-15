#!/bin/bash
service mariadb status >/dev/null 2>&1 || service mariadb start
python3 db_setup.py
python3 app.py

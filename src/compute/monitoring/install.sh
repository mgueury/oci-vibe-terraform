#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR

. $HOME/compute/shared_compute.sh

# Schema
install_instant_client
sqlplus -L $DB_USER/$DB_PASSWORD@DB @monitoring.sql

install_python
install_cline_cli

install_linux_service /home/opc/monitoring monitoring
./restart.sh
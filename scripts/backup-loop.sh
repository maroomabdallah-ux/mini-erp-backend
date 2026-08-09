#!/bin/sh
set -eu

while true; do
  /bin/sh /backup.sh
  sleep 86400
done

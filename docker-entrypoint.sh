#!/bin/bash
set -e

if [[ "$1" == "cron" ]]; then
    exec pretix cron
fi

if [[ "$AUTOMIGRATE" != "skip" ]]; then
    pretix migrate
fi

if [[ "$1" == "all" ]]; then
    exec sudo -u pretixuser supervisord -n -c /etc/supervisord.all.conf
fi

exec pretix "$@"

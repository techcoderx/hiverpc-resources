## Disable syslog

Disable syslog to prevent `/var/log/syslog` from filling up disk.
```
sudo systemctl disable --now syslog.socket rsyslog.service
```

## Disable logging `x does not exist` PostgreSQL errors

In `/etc/postgresql/<version>/main/postgresql.conf`:
```
log_min_messages = fatal
```

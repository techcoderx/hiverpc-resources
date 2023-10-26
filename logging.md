## Disable syslog

Disable syslog to prevent `/var/log/syslog` from filling up disk.
```
sudo systemctl disable --now syslog.socket rsyslog.service
```

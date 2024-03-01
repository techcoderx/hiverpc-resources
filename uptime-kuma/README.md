# `hived` Monitor for Uptime Kuma

Simple script that sends a `push` event to an Uptime Kuma instance every few seconds when `hived` node is in sync.

## Requirements

* `curl` and `jq`

## Run script
```bash
./run.sh --rpc='http://hivedurl:8091' --push-url='https://yourpushurl.example'
```

## Crontab

Run every minute:
```cron
* * * * * /path/to/run.sh --rpc='http://hivedurl:8091' --push-url='https://yourpushurl.example'
```
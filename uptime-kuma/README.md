# `hived` Monitor for Uptime Kuma

Simple script that sends a `push` event to an Uptime Kuma instance every few seconds when `hived` node is in sync.

## Requirements

* NodeJS >=18

## Configuration

Copy the example config first:
```bash
cp config.example.json config.json
```

* `rpc`: `hived` JSON RPC URL to monitor
* `intervalSeconds`: Number of seconds between push events
* `pushUrl`: The push URL from Uptime Kuma

## Run script
```bash
node index.js
```
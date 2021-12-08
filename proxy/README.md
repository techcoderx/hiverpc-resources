# hive-proxy

A dead simple hive JSON-RPC proxy powered by 69 lines of NodeJS code (excluding empty lines and comments). Only use when Jussi doesn't work.

[Full post](https://peakd.com/general/@techcoderx/the-dead-simple-proxy)

## Installation

```
git clone https://github.com/techcoderx/hiverpc-resources
cd hiverpc-resources/proxy
npm i
```

## Run

```
node index.js
```

## Environment variables

* `PORT`: HTTP port to listen to. Default: 3030
* `PROXY_INFO`: Info to be displayed in the `/` GET API response. Default: `This is a dead simple hive JSON-RPC proxy powered by 69 lines of NodeJS node.`

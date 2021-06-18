# Replay notes

## `block_log` catch up

```
wget -c https://gtg.openhive.network/get/blockchain/block_log
```

## CMake Build

Valid as of v1.25.

#### AH node
```
cmake -DCMAKE_BUILD_TYPE=Release -DCOLLECT_ACCOUNT_METADATA=ON -DSKIP_BY_TX_ID=OFF ..
```

#### Consensus node
```
cmake -DCMAKE_BUILD_TYPE=Release -DCOLLECT_ACCOUNT_METADATA=OFF -DSKIP_BY_TX_ID=ON ..
```

## Plugins
```
# Basic
plugin = witness webserver p2p json_rpc database_api network_broadcast_api condenser_api block_api rc_api

# Account history
plugin = account_history_rocksdb account_history_api

# Reputation
plugin = reputation reputation_api

# Get accounts/witness
plugin = account_by_key account_by_key_api

# Internal market
plugin = market_history market_history_api

# Transaction status
plugin = transaction_status transaction_status_api
```

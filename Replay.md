# Replay notes

## `block_log` catch up

```
wget -c https://gtg.openhive.network/get/blockchain/block_log
```

## Dependencies

```
sudo apt-get install -y \
    autoconf \
    automake \
    cmake \
    g++ \
    git \
    zlib1g-dev \
    libbz2-dev \
    libsnappy-dev \
    libssl-dev \
    libtool \
    make \
    pkg-config \
    doxygen \
    libncurses5-dev \
    libreadline-dev \
    perl \
    python3 \
    python3-jinja2 \
    libboost-chrono-dev \
    libboost-context-dev \
    libboost-coroutine-dev \
    libboost-date-time-dev \
    libboost-filesystem-dev \
    libboost-iostreams-dev \
    libboost-locale-dev \
    libboost-program-options-dev \
    libboost-serialization-dev \
    libboost-system-dev \
    libboost-test-dev \
    libboost-thread-dev
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

## One-liner clone
```
git clone https://gitlab.syncad.com/hive/hive; cd hive; git submodule update --init --recursive; mkdir build; cd build; cmake -DCMAKE_BUILD_TYPE=Release -DCOLLECT_ACCOUNT_METADATA=ON -DSKIP_BY_TX_ID=OFF ..; make -j$(nproc); sudo make install;
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

## Increase open file limit

1. Append this to `/etc/security/limits.conf`:
```
* soft     nproc          999999    
* hard     nproc          999999   
* soft     nofile         999999   
* hard     nofile         999999
root soft     nproc          999999    
root hard     nproc          999999   
root soft     nofile         999999   
root hard     nofile         999999
```

2. Append this to `/etc/pam.d/common-session`:
```
session required pam_limits.so
```

3. Logout and log back in.

## Create ramdisk

```
cd ~
mkdir ramdisk
sudo mount -t tmpfs -o rw,size=23G tmpfs ~/ramdisk
```

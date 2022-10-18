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
    libboost-all-dev
```

## HAF additional dependencies
```
sudo apt-get install -y postgresql-server-dev-14 libpqxx-dev
```

## HAF configure database
As `postgres` user:
```
# Roles
CREATE ROLE hived_group WITH NOLOGIN;
CREATE ROLE hive_applications_group WITH NOLOGIN;
CREATE ROLE hived LOGIN PASSWORD 'hivedpass' INHERIT IN ROLE hived_group;
CREATE ROLE application LOGIN PASSWORD 'applicationpass' INHERIT IN ROLE hive_applications_group;
CREATE ROLE haf_app_admin WITH LOGIN CREATEROLE INHERIT IN ROLE hive_applications_group;

# Set password if needed
ALTER ROLE role_name WITH PASSWORD 'rolepass';

# Database used by hived
CREATE DATABASE block_log;

# Use database
\c block_log

# sql_serializer plugin on db
CREATE EXTENSION hive_fork_manager CASCADE;
```

## Hafah required permissions
For Hafah python.
```
GRANT USAGE ON SCHEMA hafah_python TO haf_app_admin;
GRANT SELECT ON ALL TABLES IN SCHEMA hafah_python TO haf_app_admin;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA hafah_python TO haf_app_admin;
GRANT USAGE ON SCHEMA hive TO haf_app_admin;
GRANT SELECT ON ALL TABLES IN SCHEMA hive TO haf_app_admin;
```

## CMake Build

Valid as of v1.26.

#### AH node
```
cmake -DCMAKE_BUILD_TYPE=Release -DCOLLECT_ACCOUNT_METADATA=ON ..
```

#### Consensus node
```
cmake -DCMAKE_BUILD_TYPE=Release -DCOLLECT_ACCOUNT_METADATA=OFF ..
```

## One-liner clone
```
git clone https://gitlab.syncad.com/hive/hive; cd hive; git submodule update --init --recursive; mkdir build; cd build; cmake -DCMAKE_BUILD_TYPE=Release -DCOLLECT_ACCOUNT_METADATA=ON ..; make -j$(nproc); sudo make install;
```

## Plugins
```
# Basic
plugin = witness webserver p2p json_rpc database_api network_broadcast_api condenser_api block_api rc_api wallet_bridge_api

# Reputation
plugin = reputation reputation_api

# Get accounts/witness
plugin = account_by_key account_by_key_api

# Internal market
plugin = market_history market_history_api

# Transaction status
plugin = transaction_status transaction_status_api

# SQL serializer
plugin = sql_serializer
```

## SQL serializer
```
psql-url = dbname=block_log user=hived password=hivedpass hostaddr=127.0.0.1 port=5432
psql-index-threshold = 1000000
psql-operations-threads-number = 5
psql-transactions-threads-number = 2
psql-account-operations-threads-number = 2
psql-enable-account-operations-dump = true
psql-force-open-inconsistent = false
psql-livesync-threshold = 10000
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
sudo mount -t tmpfs -o rw,size=24G tmpfs ~/ramdisk
```

## Compress `block_log`
Located in `programs/util/compress_block_log`.
```
./compress_block_log -j $(nproc) -i /src/uncompressed/blocklog/folder -o /dest/blocklog/folder
```

## Postgresql db size
```
SELECT pg_size_pretty(pg_database_size('dbname'));
```

## ⚠️ Warning

**Do not** place the data directory on a partition that is formatted with exFAT as this will cause the disk to be unresponsive with `mount.exfat` using 100% CPU on single core. Stick with ext4 on Linux. Not sure if this is a bug or a feature.

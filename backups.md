# Making backups

#### hivemind
0. Shutdown Hivemind and Postgresql
1. Compress Postgresql database files
2. Move compressed file

#### hived
0. Shutdown hived
1. Resume copy block_log, block_log.artifacts
2. Copy shared_memory.bin

## Useful commands

#### Parallel directory compression with pigz
```
tar --use-compress-program="pigz -k -9" -cf destination.tar.gz sourcedir
```

#### Parallel directory decompression with pigz
```
tar --use-compress-program="pigz -d" -xvf compressed.tar.gz -C destinationfolder
```

#### Single file compression
```
pigz -k -9 filename
```

#### Single file decompression
```
pigz -dk filename.gz
```

#### Using `pg_dump`
```
pg_dump -U <postgres_username> -Fc <db_name> > filename.dump
```

#### HAF DB
https://gitlab.syncad.com/hive/haf/-/tree/develop/src/hive_fork_manager/tools/pg_dump

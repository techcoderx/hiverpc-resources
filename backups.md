# Making backups

#### hivemind
0. Shutdown Hivemind and Postgresql
1. Compress Postgresql database files
2. Move compressed file

#### hived
0. Shutdown hived
1. Copy block_log, block_log.index
2. Compress rocksdb state files
3. Move compressed rocksdb state file
4. Compress rocksdb account history files
5. Move compressed rocksdb account history file

## Useful commands

#### Parallel directory compression with pigz
```
tar --use-compress-program="pigz -k -9" -cf destination.tar.gz sourcedir
```

#### Parallel directory decompression with pigz
```
tar --use-compress-program="pigz -d" -xvf compressed.tar.gz destinationfolder
```

#### Single file compression
```
pigz -k -9 filename
```

#### Single file decompression
```
pigz -dk filename.gz
```

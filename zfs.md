# ZFS

## Disk ID
`/dev/nvme1n1` in the below example. Replace with appropriate disk according to output.
```
$ lsblk

NAME        MAJ:MIN RM   SIZE RO TYPE MOUNTPOINTS
loop0         7:0    0    62M  1 loop /snap/core20/1581
loop1         7:1    0  61.9M  1 loop /snap/core20/1405
loop2         7:2    0  79.9M  1 loop /snap/lxd/22923
loop3         7:3    0  44.7M  1 loop /snap/snapd/15534
loop4         7:4    0    47M  1 loop /snap/snapd/16292
nvme0n1     259:0    0 465.8G  0 disk 
├─nvme0n1p1 259:1    0     1G  0 part /boot/efi
└─nvme0n1p2 259:2    0 464.7G  0 part /
nvme1n1     259:3    0   1.9T  0 disk 
├─nvme1n1p1 259:4    0   1.9T  0 part 
└─nvme1n1p9 259:5    0     8M  0 part 
```

Detailed disks info: `sudo fdisk -l`.

## Create pool
Multiple drives indicate RAID 0 by default.
```
sudo zpool create -f <pool_name> <disk_id1> <disk_id2> ...
```

## Unmount pool
Run when moving to another server or just ejecting the disk.
```
sudo zpool export <pool_name>
```

## Mount pool
Restore ZFS pool after unmounting (can be from another server).
```
sudo zpool import <pool_name> [new_pool_name]
```

## Get pool status
```
sudo zpool status
```

## Enable compression
```
sudo zfs set compression=on <pool_name>
```

## Get compression status
```
sudo zfs get compression <pool_name>
```

## Get compression ratio
```
sudo zfs get compressratio <pool_name>
```

## Get ARC RAM usage
```
awk '/^size/ { print $1 " " $3 / 1048576 }' < /proc/spl/kstat/zfs/arcstats
```

## Set ARC RAM limit
8GB in this example in bytes.
```
echo "options zfs zfs_arc_max=8589934592" | sudo tee -a /etc/modprobe.d/zfs.conf
```

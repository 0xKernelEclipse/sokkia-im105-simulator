# Sokkia IM-series firmware — findings

Source: `im_series_optical_firmware_v32/GMiM100_50_Update_Ver32.bin`
Size: 85,020,004 bytes
SHA-256: `bf2589bdb157d4211076c7dc6f36644c94d98a2726c7ed19d1d31dc85f50a36a`
Header: `T200FF`, model tag `G1006`, build stamp `[Jan 10 2023 11:00:57]`

Everything below was read from the file. No claims are carried over from the
earlier `firmware_report.txt` where it was later shown to be wrong.

## The question

Which files contain the actual onboard surveying application?

## Answer

**Partly answered, and my first answer was wrong.** This is a multi-component
firmware update package for the Sokkia/Topcon IM-series. It does contain
firmware payloads — but they are in an **encrypted `.sbc` container**, not in
any of the filesystem images, and the container walk missed them entirely.

What holds up:

- The **Linux rootfs contains no survey application.** `app` is an empty
  directory and `starter.conf` is absent. That is still true and still the
  reason the field application is delivered separately.
- The **rootfs is not the only payload in this file.** A 7.46 MiB encrypted
  component region sits at the tail, past every container that was decoded.
  Its one plaintext name is `Swallow_EDM_9-1_04_03(CD34).sbc` — the EDM
  (distance measurement) firmware, version 9-1.04.03, build CD34.

What I got wrong: the first pass only inspected streams that `unpack_payloads.py`
had already extracted. That script never looks at the outer file past the third
stream, so the tail was never examined and I wrongly concluded the package held
nothing but the TSCOMM update.

## Container map

The outer file is not a sequence of containers — it is a header, an updater,
three compressed payloads, a second ELF, and then a component region.

| Offset | Size | What |
|---|---|---|
| `0x00000000` | 100 | header, see below |
| `0x00000064` | 89,888 | ELF #1, the updater |
| `0x00342980` | — | gzip → `gzip_00342980.bin`, 22.62 MiB, `UBI#`, **format unresolved** |
| `0x01B949E8` | — | gzip → `gzip_01B949E8.bin`, 34.53 MiB, CPIO newc rootfs |
| `0x04964C84` | 236,848 | ELF #2, the TSCOMM binary |
| `0x0499E9B4` | 16 | component table header |
| `0x0499E9C4` | 33 | `Swallow_EDM_9-1_04_03(CD34).sbc` + version `9-1.04_03` |
| `0x0499EA00` | 7,824,228 | **encrypted component payload, EOF** |

The `xz` stream at `0x4A1A760` → `xz_04A1A760.bin` (tar `tsc4bsp43t/`,
17.23 MiB) sits *inside* the region spanned by the ELF #2 and the component
header, which is consistent with it being a nested member rather than a
separate top-level section.

### Header

```
0000  54 32 30 30 46 46 0a  "T200FF\n"
0010  47 31 30 30 36         "G1006"
0018  30 30 30               "000"
0028  5b 4a 61 6e 20 ...     "[Jan 10 2023 11:00:57]"
0042  d8 23 49 2d 64 4d ...  16-byte identifier
005a  53 53 65 74 75 70      "SSetup"
0064  7f 45 4c 46            ELF magic — updater starts here
```

`T200FF` is the package type, `G1006` the hardware target, `000` a revision
field, and the bracketed string is the build timestamp.

## The encrypted component region

The 7,824,228 bytes from `0x0499EA00` to EOF:

- entropy **7.9992 bits/byte**, all 256 byte values present
- `0x00` and `0xFF` each at 0.38%
- no ELF, gzip, XZ, ZIP, SquashFS, UBI, CPIO or ustar magic in the first 4 KiB

Entropy that high is encryption-grade, not compression-grade: xz and gzip
practically top out near 7.9 on real data. So this is an encrypted payload, and
the `.sbc` extension is consistent with a signed binary container.

The plaintext component record immediately before it:

```
0499e9b4  8c bd 07 00   0x0007BD8C = 509,068
0499e9b8  5c bd 07 00   0x0007BD5C = 509,020
0499e9bc  64 0a 6c 98
0499e9c0  20 00 00 00   32
0499e9c4  "Swallow_EDM_9-1_04_03(CD34).sbc\0"
0499e9e9  "9-1.04_03"
0499e9f4  3c 03 02 4b 32 01 80 20 02 08 85 ...   -> high entropy begins
```

Only one `.sbc` name is stored in plaintext anywhere in the file, so either
this update carries a single component or the remaining component records live
inside the encrypted region.

## The updater knows the component names

ELF #1's string table, at `0x15204` onward:

```
Swallow100
SwallowGM
Magpie
```

Bird codenames, almost certainly the product and variant identifiers. Subsystem
tags alongside them:

```
update   fpga   tscbsp   tscfw
TSC4BSP   WKTSCOMM
```

And the flash partitions it writes:

```
/dev/mtd0 .. /dev/mtd8,  /dev/mtd14,  /dev/mtd15
```

plus the update state machine:

```
Update...1/3   Update...2/3   Update...3/3
TSCOMM BSP Update error - %s
TSCOMM FW  Update error - %s
echo 1 > /sys/class/boot/bootset/update_flag
Skip Bad block Offset=0
USB media check
Dir Found = %s
```

So the package is a three-stage update across several MTD partitions, and
`Swallow_EDM_*` is the EDM subsystem component of it.


## Container 1 — the CPIO rootfs (live system)

6,758 entries: 242 directories, 6,516 files, 606 symlinks.

- Kernel modules for `4.1.18-gbbe8cfc`, target **AM335x** (Cortex-A8).
- Stock Debian/OpenEmbedded userspace: busybox, bash, perl, dbus, iptables,
  thttpd, tcpdump, strace, `libcrypto.so.1.0.0`.
- Third-party CA certificates under `etc/ssl/certs/Starfield_*`.
- Proprietary kernel modules: `ts_bm.ko`, `ts_fsm.ko`, `ts_kmp.ko`,
  `drivers/mfd/ti_am335x_tscadc.ko`.
- Proprietary userspace binary `bin/uploader` (38,457 bytes).
- **The full NAND/UBI management toolchain**: `mkfs.ubifs`, `ubiformat`,
  `ubinize`, `nandwrite`, `nanddump`, `mtdinfo`.
- **`app` is a single empty directory** (mode `0775`, zero entries). It is a
  mount point, not a payload.

The presence of the flash toolchain alongside an empty `app` mount point is
the first real evidence that the application arrives from outside this image.

## Container 2 — `tsc4bsp43t/` (the BSP update)

A tar containing exactly two members:

- `rootfs.tar` — 18,053,120 bytes
- `rootfs.tar.md5` — 45 bytes

The nested `rootfs.tar` holds 1,351 members / 707 files:

- `boot/zImage` — 2,533,358 bytes, kernel **4.3.3**
- `usr/sbin/init_for_update` — 486,528 bytes, the update installer
- `/root/TScomm4default` — 236,848 bytes
- dropbear SSH, `wpa_supplicant`
- `/root/.ssh/id_rsa` — an SSH private key shipped inside the image
- `etc/fstab` mounts `/dev/mmcblk0p7` → `/mnt/mmcp7` (ext3)
- `etc/init.d/tscomm.sh` → launches `/root/starter.sh`
- `etc/init.d/mountnfs.sh` — stock Debian script; fstab contains no NFS or
  SMB entries, so on this image it starts `rpcbind` and mounts nothing.

## The ELF at `0x4964C84` is the TSCOMM binary

`elf_extracts/elf_04964C84.bin` and `./root/TScomm4default` are byte-identical:

```
size   236848
sha256 911668f8b8cefa7ef10b1d4bea224bc176ebdfdf8767be79391c6a43cca1d9a2
```

So the ELF sitting at the tail of the outer update file is not a mystery
fourth component — it is the same TSCOMM binary the BSP ships.

Its runtime paths:

```
/mnt/mmcp5/SYS_OK
/mnt/mmcp7/tscfs
/mnt/mmcp7/tscfs/UPDATE
/mnt/mmcp7/tscfsRsvd/TScommConfiguration
/mnt/mmcp7/tscfsRsvd/TScommConfigurationOpt
/mnt/mmcp7/tscfsRsvd/TScommConfigurationPrevious
/mnt/mmcp7/updater/bsp_next
```

## The pluggable application slot

`/root/starter.sh` is a generic launcher:

```sh
defaultname="/root/TScomm4default"
filename="/root/starter.conf"

if test -f $filename; then
    lines=($(cat $filename))
    ExeName=${lines[0]}
    ExePath=${lines[1]}
    ExeSource=$ExePath/$ExeName
    ExeDestination=$ExePath/../$ExeName
    # copy, chmod u+x, run $ExeDestination
else
    exec $defaultname
fi
```

`starter.conf` is **not present in this image**. `/root` contains only
`.ssh/`, `TScomm4default`, `starter.sh`, `version` (3 bytes).

This is the mechanism: TSCOMM is launched through an indirection whose target
is chosen by a config file supplied at deploy time. Whatever surveying
application is meant to run is dropped in and pointed at from outside.

## Unresolved

1. `gzip_00342980.bin` (22.62 MiB) does not parse as a stock UBI volume image:
   - 181 blocks on a genuine 128 KiB stride, each starting `UBI#`
   - `vid_hdr_offset` `0x800`, `data_offset` `0x1000` — real values
   - **0 of 181** blocks have a non-zero erase counter
   - **181 of 181** blocks have a volume header CRC of `0xFFFFFFFF`, the
     erased sentinel, so no block carries a valid volume record
   - yet **179 of 181** block bodies contain all 256 byte values with a mean
     filler fraction of 0.0219

   Unwritten headers over high-entropy bodies. Next step is `ubireader`; if
   that also fails, treat it as a vendor U-Boot / NAND update partition scheme
   rather than UBI and stop guessing the layout.

2. The 7.46 MiB encrypted `.sbc` region at `0x0499EA00` is the more valuable
   open problem, because it is where the actual subsystem firmware lives.
   Recovering it means either finding the decryption in the updater binary or in
   the two ELFs, or locating the key. That is a reverse-engineering problem, not
   a file-format one.

## Corrections to earlier conclusions in this repo

- `firmware_report.txt` reports `CPIO newc archive: not found` and
  `UBI image marker: not found`. Those were scanned against the raw outer
  `.bin`, before `unpack_payloads.py` decompressed the embedded streams. Both
  containers do exist.
- **This document previously claimed the package contained no application
  payload at all.** That was wrong. The rootfs genuinely has no survey
  application, but the encrypted `.sbc` component region at the tail of the
  outer file was never examined, because the container walk only looked at
  streams `unpack_payloads.py` had already extracted and that script stops at
  the third stream. Lesson: a container walk is only as complete as the scan
  that produced its inputs.
- The `SquashFS little-endian: 0x41000` hit reported inside the UBI blob was
  called a likely false positive on the grounds that the blob was empty
  filler. That reasoning was wrong and the hit is **unverified**.

## Reproducing

```sh
python inspect_firmware.py     # outer container scan
python inspect_elf.py          # ELF carving
python unpack_payloads.py      # decompress embedded streams
python identify_application.py # container walk -> application_report.txt
```

`identify_application.py` is read-only and writes only its own report. It does
**not** cover the tail component region — that is the gap described above.

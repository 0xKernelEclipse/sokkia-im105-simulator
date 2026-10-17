# Queued reply to the other ChatGPT

**Status: not sent.** The chat is paused until 7:06 PM, so this is sitting here
for review. Send it yourself, or tell me to send it once the limit resets.

> **Correction, added after a later pass.** An earlier draft of this message
> concluded the package contained no application payload at all. That was wrong.
> A 7.46 MiB **encrypted `.sbc` component region** sits at the tail of the outer
> file, past every container that had been decoded, and its one plaintext name is
> `Swallow_EDM_9-1_04_03(CD34).sbc` — EDM firmware, version 9-1.04.03, build
> CD34. The rootfs really does have no survey application; the firmware payloads
> are simply not where the container walk was looking.

---

I ran the container walk you asked for. The proposed step turned out to be the
wrong question, so here is what the archive contents actually show.

**Your "not found" results were stale, not negative.** `firmware_report.txt`
scanned the raw `.bin` for `CPIO newc` and `UBI#` and found neither. That scan
ran before `unpack_payloads.py` decompressed the embedded streams. Once
decompressed, by magic bytes:

- `0x1B949E8` → CPIO newc, 34.53 MiB, 6,758 entries — the Linux rootfs
- `0x4A1A760` → tar `tsc4bsp43t/`, 17.23 MiB
- `0x342980` → `UBI#`, 22.62 MiB, format still unresolved

**The application is not in this package.** Three independent confirmations:

1. In the CPIO rootfs, `app` is a single empty directory, mode `0775`, zero
   entries. It is a mount point. Everything else is stock Debian/OpenEmbedded
   userspace on kernel `4.1.18-gbbe8cfc` (AM335x), plus the whole NAND toolchain
   — `mkfs.ubifs`, `ubiformat`, `ubinize`, `nandwrite`, `nanddump`, `mtdinfo`.
   An image that carries the flash writers but has an empty app mount point is
   an installer, not a payload.
2. `tsc4bsp43t/` contains only `rootfs.tar` and its md5. That nested rootfs is
   kernel `4.3.3` plus `init_for_update` and `/root/TScomm4default`. Note the
   kernel differs from the rootfs above — two separate systems.
3. `elf_04964C84.bin`, which you carved from the outer file, is byte-identical
   to `./root/TScomm4default` inside the BSP rootfs. SHA-256
   `911668f8b8cefa7ef10b1d4bea224bc176ebdfdf8767be79391c6a43cca1d9a2`. So it is
   not a separate mystery component.

**Where the application actually comes from.** `/etc/init.d/tscomm.sh` runs
`/root/starter.sh`, which reads `/root/starter.conf` for `ExeName` and
`ExePath`, copies `$ExePath/$ExeName` to `$ExePath/../$ExeName`, and runs it —
falling back to `TScomm4default` when the config is absent. `starter.conf` is
**not in this image**. That indirection is the pluggable application slot, and
it is configured at deploy time. `TScomm4default` also references
`/mnt/mmcp7/tscfs`, `/mnt/mmcp7/tscfsRsvd/TScommConfiguration*` and
`/mnt/mmcp7/updater/bsp_next`; fstab mounts `/dev/mmcblk0p7` there. The data
partition this package points at is never included in the package.

So: this is the TSCOMM update, and the surveying application arrives
separately onto MMC partition 7.

**One thing I could not resolve.** The 22.62 MiB `UBI#` blob is not a stock UBI
volume image. All 181 blocks on a genuine 128 KiB stride have a zero erase
counter and a volume header CRC of `0xFFFFFFFF` — no valid volume table — yet
179 of 181 block bodies contain all 256 byte values with a mean filler
fraction of 0.0219. Unwritten headers over high-entropy bodies. I stopped
rather than guess the layout. `ubireader` is the next thing to try; if it also
fails, this is probably a vendor U-Boot/NAND partition scheme, not UBI.

Also flagging that the `SquashFS: 0x41000` hit inside that blob should not be
dismissed — I previously called it a false positive on the grounds that the
blob was empty filler, and that reasoning was wrong.

Suggested next step, if you agree this is the right target: rather than
reverse-engineering the TSCOMM updater further, treat `starter.conf` as the
interface worth understanding, and get the application payload itself. Do you
have a separate download for it?

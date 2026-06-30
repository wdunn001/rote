---
slug: lshw-summary
name: lshw -short (comprehensive hardware inventory)
family: system
platform: linux
equivalents: hwinfo (some distros); inxi (user-friendly); dmidecode (BIOS-level)
references: man lshw
---

# Command
```sh
sudo lshw -short                      # short table
sudo lshw -class network               # one class
sudo lshw -class processor -class memory -class disk
sudo lshw -json | jq ...               # machine-readable
```

# When to use
You want a single tool that enumerates ALL hardware (CPU, memory, disks, NICs, GPUs, USB, PCI) on a Linux host.

# When NOT to use
- Quick check for ONE thing — `lspci`, `lsblk`, `lscpu`, `lsusb`, `free -h` are faster.
- Inside WSL — most hardware is bridged via Windows, so `lshw` returns sparse info. Use `wmic` against the Windows host instead.
- Container with restricted privileges — needs `sudo` AND access to `/sys` + `/proc`.

# Gotchas
- Needs root for full output. Without root: omits serial numbers, hardware vendor names, some firmware details.
- `lshw` is NOT installed by default on every distro. On Debian/Ubuntu: `sudo apt-get install -y lshw`.
- The default output is VERY long. Always start with `-short` or `-class <X>`.
- The `-json` output is great for scripting but huge; pipe through `jq` aggressively.
- For BIOS / DMI / SMBIOS info, `dmidecode` is the right tool (lshw incorporates some of it but `dmidecode -t` is the source of truth).

# Flags
- `-short`: brief tabular output (recommended start)
- `-class <c>`: filter to a class (network, processor, memory, disk, display, bridge, system, bus)
- `-json` / `-xml` / `-html`: machine-readable formats
- `-businfo`: include PCI/USB bus addresses
- `-numeric`: include numeric PCI vendor:device IDs
- `-quiet`: suppress progress messages
- `-disable <test>`: skip a probe (sometimes hangs on broken hardware)

# Examples
- Quick overview: `sudo lshw -short`
- All network cards: `sudo lshw -class network`
- Memory modules detail: `sudo lshw -class memory`
- JSON to a file then jq: `sudo lshw -json > /tmp/hw.json && jq '.children[] | select(.id=="core") | .children[] | .id' /tmp/hw.json`
- Just CPU: `lscpu` (faster, doesn't need root)
- Just disks: `lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT,MODEL`
- BIOS / SMBIOS: `sudo dmidecode -t bios -t system -t baseboard`

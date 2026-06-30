---
slug: tar-extract
name: tar extract (xzf / xJf / xjf)
family: fs
platform: cross-platform
equivalents: unzip (for .zip); 7z x (universal)
references: man tar
---

# Command
```sh
tar xzf <file>.tar.gz     # gzip
tar xJf <file>.tar.xz     # xz
tar xjf <file>.tar.bz2    # bzip2
tar xf  <file>.tar.zst    # zstd (modern tar auto-detects)
```

# When to use
Extract a tarball. Modern GNU tar auto-detects compression with `xf` alone — older systems need the flag.

# When NOT to use
Archive contains unknown / untrusted content — extract to a sandbox dir first.

# Gotchas
- `tar xzf` extracts INTO THE CURRENT DIR. Use `-C <dir>` to target somewhere else.
- `-v` prints every file — slow on huge archives. Drop it.
- The TAR-BOMB problem: an archive that extracts to the current dir instead of a subdir, scattering files everywhere. Always `tar tzf <file> | head` first to inspect.
- Modern tar (GNU 1.30+, macOS bsdtar) auto-detects compression. `tar xf` works for .tar.gz, .tar.xz, .tar.bz2, .tar.zst.

# Flags
- `x` extract / `c` create / `t` list
- `f <file>`: archive file (must be last in flag clump)
- `z` gzip / `J` xz / `j` bzip2 / no-flag = auto-detect (modern)
- `v` verbose (slow on big archives)
- `-C <dir>`: change to dir before operating

# Examples
- List first: `tar tzf archive.tar.gz | head`
- Extract to dir: `tar xzf archive.tar.gz -C /tmp/extracted/`
- Auto-detect: `tar xf archive.tar.zst` (modern tar handles it)
- Create: `tar czf archive.tar.gz dir/`

---
slug: apt-vs-apt-get
name: apt vs apt-get (when to pick which)
family: package-mgmt
platform: debian, ubuntu
equivalents: 
references: https://manpages.debian.org/apt
---

# Command
```sh
apt install <pkg>   # interactive shell
apt-get install -y <pkg>  # scripts / CI
```

# When to use
Decide which command-line tool to use for Debian/Ubuntu package operations.

# When NOT to use
Not a runtime command — this is a reference for picking between two tools.

# Gotchas
- `apt` shows progress bars + colored output + an upgradable-packages list at the end. Looks pretty in a terminal; breaks log scrapers.
- `apt`'s output format is NOT a stable CLI contract — it WILL change between versions.
- `apt-get`'s output is the stable scripting contract. Use it in scripts.
- Both call the same backend (libapt); same commands work on both.

# Flags
Identical flag set; `apt` is just a friendlier front-end.

# Examples
- Day-to-day: `apt search postgres`, `apt show postgresql-client`
- Scripts: `apt-get install -y postgresql-client`

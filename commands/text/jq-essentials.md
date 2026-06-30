---
slug: jq-essentials
name: jq essentials (.field, [], select, map)
family: text
platform: cross-platform
equivalents: yq (yaml); fx (interactive)
references: https://stedolan.github.io/jq/manual/
---

# Command
```sh
<json-source> | jq '.<path>'
<json-source> | jq '.[] | select(.status == "active")'
<json-source> | jq -r '.items[] | "\(.id)\t\(.name)"'
```

# When to use
Parse / filter / reshape JSON on the command line. The rote's CLI uses jq throughout.

# When NOT to use
YAML — use `yq` (jq-syntax-compatible).
Deeply complex transformations — use a real script (Python, JS).
XML — use `xmlstarlet`.

# Gotchas
- `-r` / `--raw-output` strips JSON quoting on STRING output. Without it `jq '.name'` returns `"foo"`; with `-r` returns `foo`.
- `-c` / `--compact-output`: one line per result (for piping to xargs / writing to file).
- jq's `select(...)` returns the matching item; `map(select(...))` returns the array of matching items.
- `\(.field)` is string interpolation; `"\(.a)\t\(.b)"` builds tab-separated output.
- `if-then-else` and `// default` for null handling: `.maybe_missing // "default"`.

# Flags
- `-r`: raw output (no JSON quotes on string results)
- `-c`: compact (one line per result)
- `-n`: don't read stdin (start from null)
- `--arg <name> <value>`: pass string variable
- `--argjson <name> <json>`: pass JSON variable
- `-S`: sort keys in output (for diffs)

# Examples
- Field: `cat resp.json | jq '.data.users'`
- Filter array: `jq '.users[] | select(.active == true)'`
- Build object: `jq '{name, email}'`
- TSV for table output: `jq -r '.users[] | [.id, .name, .email] | @tsv'`
- Count: `jq '.users | length'`
- Sum: `jq '[.transactions[].amount] | add'`

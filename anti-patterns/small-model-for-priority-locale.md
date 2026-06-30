---
slug: small-model-for-priority-locale
title: Used a small LLM (qwen2.5:7b) to translate the priority locale — output was garbled
hit_count: 1
token_cost: high — a full re-translation pass on a bigger model + ~45 manual Claude corrections
---

# Symptom

Bulk-translated an i18n glossary (309 keys) into the priority locale (Ukrainian) on the cheap default delegate model `qwen2.5:7b`. The output had transliteration artifacts and outright wrong words in Cyrillic technical text:

- `чорної skvazhyny` — *skvazhyna* = **borehole**, not "black box"
- `годувальник` — = **breadwinner**, not "feed/stream"
- `гекса` — = **hex**, not "heuristic" (евристична)
- `джоystick`, `Необов'яzkove`, `informatsiya` — Latin letters spliced into Cyrillic words
- awkward gerund `літання` instead of `політ/польоту`

# Root cause

The `local-llm` delegate defaulted to the small/fast model. 7B-class models are unreliable for non-English (especially Cyrillic) technical translation: they transliterate, drop into English, and pick wrong cognates. Latin-script high-resource locales (de/es) survive a 7B far better, which masks the problem until you check the priority locale.

# Remedy

- Use the largest **feasible** local model for the priority locale: `mixtral:8x7b` on .88 (47B MoE, ~13B active = fast + good multilingual).
- Then run a **Claude correction overlay**: scan for Latin-letter intrusions inside Cyrillic, wrong-word cognates, and English fallbacks; author a flat-JSON fix overlay and merge it on top (`merge-i18n-locale-keys.mjs`).
- Reserve Claude review for the **priority locale only**; secondary Latin-script locales can ship at qwen2.5 quality.
- The `translate-i18n-via-delegate.mjs` script now defaults to `mixtral:8x7b`; `--model qwen2.5:latest` is the explicit smoke-test override.

See also: [[bulk-translation-in-claude-not-delegate]], [[llama70b-cpu-offload-timeout-on-88]].

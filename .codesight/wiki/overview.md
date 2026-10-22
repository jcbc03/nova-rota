# ia_off_v3 — Overview

> **Navigation aid.** This article shows WHERE things live (routes, models, files). Read actual source files before implementing new features or making changes.

**ia_off_v3** is a python project built with raw-http.

## Scale

23 library files · 23 environment variables

**Libraries:** 23 files — see [libraries.md](./libraries.md)

## High-Impact Files

Changes to these files have the widest blast radius across the codebase:

- `ia_off/config.py` — imported by **17** files
- `ia_off/sdcpp.py` — imported by **16** files
- `ia_off/perf.py` — imported by **14** files
- `ia_off/engines_registry.py` — imported by **12** files
- `ia_off/engine_api.py` — imported by **11** files
- `ia_off/moderador.py` — imported by **8** files

## Required Environment Variables

- `IA_OFF_DADOS_DIR` — `ia_off/config.py`
- `IA_OFF_HOME` — `ia_off/config.py`
- `IA_OFF_MODELOS_DIR` — `ia_off/config.py`
- `IA_OFF_MODERACAO_ARQUIVO` — `ia_off/config.py`
- `IA_OFF_MODERACAO_SENHA` — `ia_off/config.py`
- `IA_OFF_RAG_DIR` — `ia_off/config.py`
- `IA_OFF_SDCPP_VARIANT` — `ia_off/sdcpp.py`
- `IA_OFF_UPSCALE_MODEL` — `ia_off/config.py`
- `IA_OFF_VCRUNTIME_DIR` — `ia_off/config.py`
- `IA_OFF_VIDEO_MODELO` — `ia_off/config.py`
- `IA_OFF_VOZ_DIR` — `ia_off/config.py`
- `IA_OFF_WAN22_MODEL` — `ia_off/config.py`
- _...9 more_

---
_Back to [index.md](./index.md) · Generated 2026-10-22_
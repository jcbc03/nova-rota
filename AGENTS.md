# Project Context

This is a python project using raw-http.


High-impact files (most imported, changes here affect many other files):
- ia_off/config.py (imported by 16 files)
- ia_off/sdcpp.py (imported by 13 files)
- ia_off/perf.py (imported by 11 files)
- ia_off/engine_api.py (imported by 10 files)
- ia_off/engines_registry.py (imported by 8 files)
- ia_off/moderador.py (imported by 7 files)
- ia_off/image_engine.py (imported by 7 files)
- ia_off/job_queue.py (imported by 6 files)

Required environment variables (no defaults):
- IA_OFF_DADOS_DIR (ia_off/config.py)
- IA_OFF_HOME (ia_off/config.py)
- IA_OFF_MODELOS_DIR (ia_off/config.py)
- IA_OFF_MODERACAO_ARQUIVO (ia_off/config.py)
- IA_OFF_MODERACAO_SENHA (ia_off/config.py)
- IA_OFF_RAG_DIR (ia_off/config.py)
- IA_OFF_UPSCALE_MODEL (ia_off/config.py)
- IA_OFF_VCRUNTIME_DIR (ia_off/config.py)
- IA_OFF_VIDEO_MODELO (ia_off/config.py)
- IA_OFF_VOZ_DIR (ia_off/config.py)
- IA_OFF_WAN22_MODEL (ia_off/config.py)
- IA_OFF_WAN22_T5 (ia_off/config.py)
- IA_OFF_WAN22_VAE (ia_off/config.py)
- IA_OFF_ZIMAGE_LLM (ia_off/config.py)
- IA_OFF_ZIMAGE_MODEL (ia_off/config.py)

Read .codesight/wiki/index.md for orientation (WHERE things live). Then read actual source files before implementing. Wiki articles are navigation aids, not implementation guides.
Read .codesight/CODESIGHT.md for the complete AI context map including all routes, schema, components, libraries, config, middleware, and dependency graph.

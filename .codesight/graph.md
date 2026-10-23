# Dependency Graph

## Most Imported Files (change these carefully)

- `ia_off/config.py` — imported by **17** files
- `ia_off/sdcpp.py` — imported by **17** files
- `ia_off/perf.py` — imported by **14** files
- `ia_off/engines_registry.py` — imported by **12** files
- `ia_off/engine_api.py` — imported by **11** files
- `ia_off/media_tabs.py` — imported by **8** files
- `ia_off/moderador.py` — imported by **8** files
- `ia_off/job_queue.py` — imported by **7** files
- `ia_off/image_engine.py` — imported by **7** files
- `ia_off/app.py` — imported by **6** files
- `ia_off/ollama_client.py` — imported by **5** files
- `ia_off/rag.py` — imported by **5** files
- `ia_off/storage.py` — imported by **3** files
- `ia_off/jobs.py` — imported by **3** files
- `ia_off/voice_engine.py` — imported by **3** files
- `ia_off/__init__.py` — imported by **2** files
- `ia_off/upscaler.py` — imported by **2** files
- `ia_off/ov_engine.py` — imported by **2** files
- `ia_off/translate.py` — imported by **2** files
- `ia_off/sizing.py` — imported by **2** files

## Import Map (who imports what)

- `ia_off/config.py` ← `ia_off/app.py`, `ia_off/engines_registry.py`, `ia_off/job_queue.py`, `ia_off/media_tabs.py`, `ia_off/moderador.py` +12 more
- `ia_off/sdcpp.py` ← `ia_off/engines_registry.py`, `ia_off/media_tabs.py`, `ia_off/voice_engine.py`, `tests/stress_gui.py`, `tests/test_engine_api.py` +12 more
- `ia_off/perf.py` ← `ia_off/app.py`, `ia_off/engines_registry.py`, `ia_off/image_engine.py`, `ia_off/media_tabs.py`, `ia_off/ov_engine.py` +9 more
- `ia_off/engines_registry.py` ← `ia_off/app.py`, `tests/stress_gui.py`, `tests/test_engines_registry.py`, `tests/test_fase_decode.py`, `tests/test_flux2_cpu_padrao.py` +7 more
- `ia_off/engine_api.py` ← `ia_off/engines_registry.py`, `ia_off/image_engine.py`, `ia_off/ov_engine.py`, `ia_off/sdcpp.py`, `ia_off/upscaler.py` +6 more
- `ia_off/media_tabs.py` ← `ia_off/app.py`, `tests/test_decode_barra.py`, `tests/test_flux2_cpu_padrao.py`, `tests/test_progresso_tick.py`, `tests/test_translate.py` +3 more
- `ia_off/moderador.py` ← `ia_off/app.py`, `ia_off/engines_registry.py`, `tests/mo_pc_check.py`, `tests/test_job_queue.py`, `tests/test_moderador.py` +3 more
- `ia_off/job_queue.py` ← `ia_off/app.py`, `tests/test_engines_registry.py`, `tests/test_fase_decode.py`, `tests/test_job_queue.py`, `tests/test_sub2_cdi.py` +2 more
- `ia_off/image_engine.py` ← `ia_off/app.py`, `ia_off/engines_registry.py`, `ia_off/ov_engine.py`, `tests/stress_gui.py`, `tests/test_engine_api.py` +2 more
- `ia_off/app.py` ← `ia_off/__main__.py`, `tests/smoke_gui.py`, `tests/stop_ensure_gui.py`, `tests/stress_gui.py`, `tests/test_std_streams.py` +1 more

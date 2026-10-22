# Libraries

> **Navigation aid.** Library inventory extracted via AST. Read the source files listed here before modifying exported functions.

**23 library files** across 2 modules

## Ia_off (20 files)

- `ia_off/sdcpp.py` — cli_safe, default_dir, find_binary, download_binary, ensure_binary, run_with_fallback, …
- `ia_off/media_tabs.py` — open_path, get_translator, translate_in_job, save_png, pil_to_pixmap, image_meta, …
- `ia_off/perf.py` — ov_cache_dir, set_thread_env, effective_threads, set_high_priority, apply, total_ram_gb, …
- `ia_off/job_queue.py` — chat_iniciado, chat_terminado, chat_ativo, esperar_chat_livre, unload_ollama_models, register_engine, …
- `ia_off/moderador.py` — ativa, exportar_padrao, checar_prompt, completar_negativo, instrucoes_chat, senha_definida, …
- `ia_off/app.py` — md_html, run_bg, fit_history, is_embed_model, log_line, install_diagnostics, …
- `ia_off/rag.py` — read_file, chunk_text, default_folder, migrate, reindex, index_file, …
- `ia_off/engines_registry.py` — gerar_imagem, gerar_video, transcrever, falar, ampliar, moderado, …
- `ia_off/voice_engine.py` — whisper_model_dir, piper_voice_path, transcribe, split_sentences, espeak_data_dir, speak
- `ia_off/sizing.py` — target_size, native_size, plan, upscale, warning
- `ia_off/engine_api.py` — make_cancel_check, make_progress, raise_if_cancelled, Cancelled
- `ia_off/ollama_client.py` — build_modelfile, create_from_gguf, OllamaError, OllamaClient
- `ia_off/ov_engine.py` — step_callback_kwargs, ir_dir_for, export_ir, OVEngine
- `ia_off/upscaler.py` — tile_grid, upscale_array, detect_scale, ampliar
- `ia_off/config.py` — output_dir, load, save
- `ia_off/image_engine.py` — inspect_sd_folder, load_sd_components, ImageEngine
- `ia_off/jobs.py` — running, shutdown_all, Job
- `ia_off/runtime_dlls.py` — candidatos, achar_vcomp, env_para_exe
- `ia_off/translate.py` — is_english, clean_output, Translator
- `ia_off/storage.py` — Storage

## Tools (3 files)

- `tools/converter_ampliador.py` — build_model, sha256, main
- `tools/baixar_ampliador.py` — main
- `tools/checar_imports.py` — main

---
_Back to [overview.md](./overview.md)_
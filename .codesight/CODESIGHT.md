# ia_off_v3 — AI Context Map

> **Stack:** raw-http | none | unknown | python

> 0 routes | 0 models | 0 components | 23 lib files | 23 env vars | 0 middleware | 39 events | 0% test coverage
> **Token savings:** this file is ~3,100 tokens. Without it, AI exploration would cost ~25,700 tokens. **Saves ~22,600 tokens per conversation.**
> **Last scanned:** 2026-10-22 15:27 — re-run after significant changes

---

# Libraries

- `ia_off/app.py`
  - function md_html: (text)
  - function run_bg: (owner, fn, on_chunk, on_done, on_error)
  - function fit_history: (sys_prompt, hist, num_ctx, chars_por_token, reserva)
  - function is_embed_model: (name, cfg)
  - function log_line: (msg)
  - function install_diagnostics: ()
  - _...3 more_
- `ia_off/config.py`
  - function output_dir: (kind)
  - function load: ()
  - function save: (cfg)
- `ia_off/engine_api.py`
  - function make_cancel_check: (cancel_flag, cancelled)
  - function make_progress: (progress_cb, progress)
  - function raise_if_cancelled: (check)
  - class Cancelled
- `ia_off/engines_registry.py`
  - function gerar_imagem: (params, on_progress, cancel_flag, engine_factory)
  - function gerar_video: (params, on_progress, cancel_flag)
  - function transcrever: (params, on_progress, cancel_flag)
  - function falar: (params, on_progress, cancel_flag)
  - function ampliar: (params, on_progress, cancel_flag)
  - function moderado: (fn, contexto, campo, negativo, neg_padrao)
  - _...1 more_
- `ia_off/image_engine.py`
  - function inspect_sd_folder: (path)
  - function load_sd_components: (path)
  - class ImageEngine
- `ia_off/job_queue.py`
  - function chat_iniciado: ()
  - function chat_terminado: ()
  - function chat_ativo: ()
  - function esperar_chat_livre: (timeout, cancel_flag, poll)
  - function unload_ollama_models: (host, timeout)
  - function register_engine: (tipo, fn)
  - _...5 more_
- `ia_off/jobs.py`
  - function running: ()
  - function shutdown_all: (timeout_ms)
  - class Job
- `ia_off/media_tabs.py`
  - function open_path: (p)
  - function get_translator: (cfg)
  - function translate_in_job: (j, cfg, prompt, negative)
  - function save_png: (im, fp, meta)
  - function pil_to_pixmap: (img)
  - function image_meta: (p, mode, seed)
  - _...7 more_
- `ia_off/moderador.py`
  - function ativa: (cfg)
  - function exportar_padrao: (path)
  - function checar_prompt: (texto, contexto, cfg)
  - function completar_negativo: (negativo, cfg)
  - function instrucoes_chat: (cfg)
  - function senha_definida: (cfg)
  - _...4 more_
- `ia_off/ollama_client.py`
  - function build_modelfile: (gguf_path, num_ctx, threads, temperature, system)
  - function create_from_gguf: (exe, name, gguf_path, **kw)
  - class OllamaError
  - class OllamaClient
- `ia_off/ov_engine.py`
  - function step_callback_kwargs: (pipe, on_step)
  - function ir_dir_for: (src_path, lcm_path, lcm, kind)
  - function export_ir: (src_path, kind, lcm, lcm_path, log)
  - class OVEngine
- `ia_off/perf.py`
  - function ov_cache_dir: ()
  - function set_thread_env: (threads)
  - function effective_threads: (cfg)
  - function set_high_priority: (on)
  - function apply: (cfg, import_torch)
  - function total_ram_gb: ()
  - _...7 more_
- `ia_off/rag.py`
  - function read_file: (path)
  - function chunk_text: (text, size, overlap)
  - function default_folder: ()
  - function migrate: (store, progress)
  - function reindex: (store, embed_fn, batch, progress, on_progress, cancel_flag)
  - function index_file: (path, store, embed_fn, size, overlap, progress)
  - _...3 more_
- `ia_off/runtime_dlls.py`
  - function candidatos: (exe_path, cfg)
  - function achar_vcomp: (exe_path, cfg)
  - function env_para_exe: (exe_path, base_env, cfg)
- `ia_off/sdcpp.py`
  - function cli_safe: (text, what)
  - function default_dir: ()
  - function find_binary: (folder, variant)
  - function download_binary: (folder, progress, total, cancelled, variant)
  - function ensure_binary: (folder, variant, progress, t, cancelled)
  - function run_with_fallback: (folder, variant, build_args, on_line, cancelled, log, progress, t, ensure, progress_cb, cancel_flag, phase_cb)
  - _...13 more_
- `ia_off/sizing.py`
  - function target_size: (aspect, short, mult)
  - function native_size: (engine, w, h)
  - function plan: (engine, w, h)
  - function upscale: (img, w, h, sharpen)
  - function warning: (w, h)
- `ia_off/storage.py` — class Storage
- `ia_off/translate.py`
  - function is_english: (text)
  - function clean_output: (text)
  - class Translator
- `ia_off/upscaler.py`
  - function tile_grid: (w, h, tile)
  - function upscale_array: (arr, run, model_scale, tile, pad, on_progress, cancel_flag)
  - function detect_scale: (run)
  - function ampliar: (params, on_progress, cancel_flag, runner)
- `ia_off/voice_engine.py`
  - function whisper_model_dir: (cfg)
  - function piper_voice_path: (cfg)
  - function transcribe: (audio_path, progress_cb, cancel_flag, cfg, language, model_loader, audio_loader)
  - function split_sentences: (text, max_len)
  - function espeak_data_dir: (onnx, src)
  - function speak: (text, out_wav, progress_cb, cancel_flag, cfg, voice_loader)
- `tools/baixar_ampliador.py` — function main: ()
- `tools/checar_imports.py` — function main: ()
- `tools/converter_ampliador.py`
  - function build_model: ()
  - function sha256: (p)
  - function main: ()

---

# Config

## Environment Variables

- `APPDATA` (has default) — ia_off/config.py
- `IA_OFF_DADOS_DIR` **required** — ia_off/config.py
- `IA_OFF_HOME` **required** — ia_off/config.py
- `IA_OFF_MODELOS_DIR` **required** — ia_off/config.py
- `IA_OFF_MODERACAO_ARQUIVO` **required** — ia_off/config.py
- `IA_OFF_MODERACAO_SENHA` **required** — ia_off/config.py
- `IA_OFF_RAG_DIR` **required** — ia_off/config.py
- `IA_OFF_SDCPP_VARIANT` **required** — ia_off/sdcpp.py
- `IA_OFF_UPSCALE_MODEL` **required** — ia_off/config.py
- `IA_OFF_VCRUNTIME_DIR` **required** — ia_off/config.py
- `IA_OFF_VIDEO_MODELO` **required** — ia_off/config.py
- `IA_OFF_VOZ_DIR` **required** — ia_off/config.py
- `IA_OFF_WAN22_MODEL` **required** — ia_off/config.py
- `IA_OFF_WAN22_T5` **required** — ia_off/config.py
- `IA_OFF_WAN22_VAE` **required** — ia_off/config.py
- `IA_OFF_ZIMAGE_LLM` **required** — ia_off/config.py
- `IA_OFF_ZIMAGE_MODEL` **required** — ia_off/config.py
- `IA_OFF_ZIMAGE_VAE` **required** — ia_off/config.py
- `LOCALAPPDATA` (has default) — ia_off/config.py
- `MKL_NUM_THREADS` **required** — tests/test_perf.py
- `OMP_NUM_THREADS` **required** — tests/test_perf.py
- `QT_QPA_PLATFORM` **required** — tests/smoke_gui.py
- `SYSTEMROOT` **required** — ia_off/runtime_dlls.py

---

# Dependency Graph

## Most Imported Files (change these carefully)

- `ia_off/config.py` — imported by **17** files
- `ia_off/sdcpp.py` — imported by **14** files
- `ia_off/perf.py` — imported by **12** files
- `ia_off/engine_api.py` — imported by **11** files
- `ia_off/engines_registry.py` — imported by **10** files
- `ia_off/moderador.py` — imported by **8** files
- `ia_off/job_queue.py` — imported by **7** files
- `ia_off/image_engine.py` — imported by **7** files
- `ia_off/app.py` — imported by **6** files
- `ia_off/ollama_client.py` — imported by **5** files
- `ia_off/rag.py` — imported by **5** files
- `ia_off/media_tabs.py` — imported by **5** files
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
- `ia_off/sdcpp.py` ← `ia_off/engines_registry.py`, `ia_off/media_tabs.py`, `ia_off/voice_engine.py`, `tests/stress_gui.py`, `tests/test_engine_api.py` +9 more
- `ia_off/perf.py` ← `ia_off/app.py`, `ia_off/engines_registry.py`, `ia_off/image_engine.py`, `ia_off/media_tabs.py`, `ia_off/ov_engine.py` +7 more
- `ia_off/engine_api.py` ← `ia_off/engines_registry.py`, `ia_off/image_engine.py`, `ia_off/ov_engine.py`, `ia_off/sdcpp.py`, `ia_off/upscaler.py` +6 more
- `ia_off/engines_registry.py` ← `ia_off/app.py`, `tests/stress_gui.py`, `tests/test_engines_registry.py`, `tests/test_fase_decode.py`, `tests/test_flux2_variant.py` +5 more
- `ia_off/moderador.py` ← `ia_off/app.py`, `ia_off/engines_registry.py`, `tests/mo_pc_check.py`, `tests/test_job_queue.py`, `tests/test_moderador.py` +3 more
- `ia_off/job_queue.py` ← `ia_off/app.py`, `tests/test_engines_registry.py`, `tests/test_fase_decode.py`, `tests/test_job_queue.py`, `tests/test_sub2_cdi.py` +2 more
- `ia_off/image_engine.py` ← `ia_off/app.py`, `ia_off/engines_registry.py`, `ia_off/ov_engine.py`, `tests/stress_gui.py`, `tests/test_engine_api.py` +2 more
- `ia_off/app.py` ← `ia_off/__main__.py`, `tests/smoke_gui.py`, `tests/stop_ensure_gui.py`, `tests/stress_gui.py`, `tests/test_std_streams.py` +1 more
- `ia_off/ollama_client.py` ← `ia_off/app.py`, `ia_off/media_tabs.py`, `tests/test_core.py`, `tests/test_ollama_stop.py`, `tests/test_rag_v3.py`

---

# Events & Queues

- `+ Nova conversa` [event] — `ia_off/app.py`
- `Renomear` [event] — `ia_off/app.py`
- `Excluir` [event] — `ia_off/app.py`
- `Atualizar` [event] — `ia_off/app.py`
- `Importar GGUF…` [event] — `ia_off/app.py`
- `Enviar` [event] — `ia_off/app.py`
- `Parar` [event] — `ia_off/app.py`
- `Copiar última resposta` [event] — `ia_off/app.py`
- `Procurar…` [event] — `ia_off/app.py`
- `Adicionar arquivos…` [event] — `ia_off/app.py`
- `Remover selecionado` [event] — `ia_off/app.py`
- `Limpar base` [event] — `ia_off/app.py`
- `Baixar modelo de embeddings` [event] — `ia_off/app.py`
- `Perguntar` [event] — `ia_off/app.py`
- `…` [event] — `ia_off/app.py`
- `Benchmark (SD 1.5, 4 passos, 512×512)` [event] — `ia_off/app.py`
- `Alterar filtro…` [event] — `ia_off/app.py`
- `Trocar senha…` [event] — `ia_off/app.py`
- `Salvar` [event] — `ia_off/app.py`
- `Cancelado.` [event] — `ia_off/jobs.py`
- `warn` [event] — `ia_off/media_tabs.py`
- `translated` [event] — `ia_off/media_tabs.py`
- `Abrir imagem de entrada…` [event] — `ia_off/media_tabs.py`
- `Limpar máscara` [event] — `ia_off/media_tabs.py`
- `Gerar` [event] — `ia_off/media_tabs.py`
- `Cancelar` [event] — `ia_off/media_tabs.py`
- `Usar como entrada` [event] — `ia_off/media_tabs.py`
- `Abrir pasta` [event] — `ia_off/media_tabs.py`
- `Ampliar com IA` [event] — `ia_off/media_tabs.py`
- `log` [event] — `ia_off/media_tabs.py`
- `Gerar vídeo` [event] — `ia_off/media_tabs.py`
- `Baixar/verificar stable-diffusion.cpp` [event] — `ia_off/media_tabs.py`
- `▶ Tocar` [event] — `ia_off/media_tabs.py`
- `⏸ Pausar` [event] — `ia_off/media_tabs.py`
- `Escolher áudio…` [event] — `ia_off/media_tabs.py`
- `Copiar texto` [event] — `ia_off/media_tabs.py`
- `▶ Ouvir de novo` [event] — `ia_off/media_tabs.py`
- `Transcrever` [event] — `ia_off/media_tabs.py`
- `Falar` [event] — `ia_off/media_tabs.py`

---

# Test Coverage

> **0%** of routes and models are covered by tests
> 32 test files found

---

_Generated by [codesight](https://github.com/Houseofmvps/codesight) — see your codebase clearly_
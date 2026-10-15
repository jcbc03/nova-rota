# Fila de tarefas (job_queue.py), interface v1

Uma tarefa pesada por vez (CPU). Responsável: DEV beck.

## Métodos
- `enqueue(tipo, params) -> id`: tipo = "imagem" | "video" | "ampliar"
- `cancel(id)`: cancela na fila ou rodando
- `list_jobs()`: estados: na_fila, rodando, concluida, falhou, cancelada

## Sinais Qt (a tela só escuta estes)
- `started(id)`
- `progress(id, passo, total, pct, eta_s)`
- `finished(id, caminho_resultado)`
- `failed(id, erro)`
- `cancelled(id)`

## Contrato com os motores (ia_off)
- Aceitam `on_progress(passo, total)`
- Checam `cancel_flag.is_set()` entre passos e encerram limpo

## Implementação (DEV beck, ia_off/job_queue.py)
- `JobQueue(parent=None, engines=None, progress_interval=0.1)` — criar na thread da GUI (ex.: no MainWindow).
- `id` é `str` ("job-1", ...). `enqueue` levanta `ValueError` se o tipo não tiver motor.
- `cancel(id) -> bool`; `list_jobs()` / `get(id)` devolvem dicts: id, tipo, estado, passo, total, pct, eta_s, resultado, erro, criado, inicio, fim, params.
- `progress`: pct 0–100 (float), eta_s em segundos (-1 = desconhecido); limitado a 1 emissão/`progress_interval` s (o último passo sempre sai).
- `shutdown(wait=True, timeout=None)`: cancela tudo e para o worker — chamar no `closeEvent`/`aboutToQuit`.

## Registro de motores (ia_off pluga sem editar job_queue.py)
```python
from ia_off.job_queue import register_engine, JobCancelled
def motor_imagem(params, on_progress, cancel_flag):
    for passo in range(1, n + 1):
        if cancel_flag.is_set():
            return None            # ou raise JobCancelled()
        ...                        # trabalho pesado
        on_progress(passo, n)
    return str(caminho_png)        # vira finished(id, caminho)
register_engine("imagem", motor_imagem)   # também: fila.register_engine(...) só p/ uma instância
```
- Exceção (sem cancelamento) -> `failed(id, "Tipo: mensagem")`; retorno vazio/None sem cancelamento -> `failed`.
- O motor roda numa thread de trabalho: NÃO pode tocar em widgets.

## Tela (DEV Front)
- Conectar sinais a métodos de QObject/QWidget (slots rodam na thread da GUI).

## Motores (ia_off: image_engine.py, sdcpp.py, ov_engine.py)
- Todo ponto de entrada de geração aceita, opcionais (padrão `None`, compatível com chamadas antigas):
  `progress_cb(step:int, total:int)` e `cancel_flag` (qualquer objeto com `is_set()`, ex. `threading.Event`).
- Cancelado -> levanta `ia_off.engine_api.Cancelled` (subclasse de `RuntimeError`, mensagem "Cancelado."; `image_engine.Cancelled` é o mesmo).
  Na fila: tratar como cancelamento (o `cancel_flag` já estará setado).
- `ImageEngine.generate(..., progress_cb=None, cancel_flag=None)`: diffusers via `callback_on_step_end`; OpenVINO via
  callback por passo (`callback_on_step_end` ou `callback` nas versões antigas do optimum). `total = steps * batch`.
  Cancelamento no OV não cai para a CPU.
- `sdcpp.run(args, on_line, cancelled=None, progress_cb=None, cancel_flag=None)` e
  `sdcpp.run_with_fallback(..., progress_cb=None, cancel_flag=None)`: progresso lido das linhas "3/20" do sd-cli;
  ao cancelar mata a árvore do processo (Windows: `taskkill /T /F`; Linux: grupo de processos) em até ~0,2 s, mesmo sem saída.
- `OVEngine.pipeline(..., cancel_flag=None)` checa o flag entre exportar/carregar/compilar.
- Caminhos de modelo só vêm do `cfg` (config.py). Motores rodam na thread de trabalho e não tocam em Qt.
- Adaptador p/ a fila: `lambda params, on_progress, cancel_flag: motor(..., progress_cb=on_progress, cancel_flag=cancel_flag)`.

### Registro na fila (ia_off/engines_registry.py)
- No `app.py`, logo após criar a fila: `from .engines_registry import register_all; register_all(self.fila)`
  (sem argumento registra no registro global do `job_queue`). Tipos: `"imagem"` e `"video"`.
- `on_progress(passo, total)` vem da fila (ela calcula pct/eta). Retorno = caminho do arquivo -> `finished(id, caminho)`.
- Prompts vão como estão (a tradução PT->EN fica com a tela, antes de enfileirar).
- Comum aos dois: `prompt` (obrigatório), `negative` (""), `seed` (-1 = aleatório), `saida` (pasta; padrão Imagens/Vídeos\IA_Off),
  `cfg_override` (dict que sobrepõe o config.json só nesta tarefa).
- `"imagem"`: `modo` (`txt2img`|`img2img`|`inpaint`|`pix2pix`|`flux2`, padrão `txt2img`), `width`/`height` (512),
  `steps` (4), `guidance` (1.0), `batch` (1), `strength` (0.6), `image_guidance` (1.5, pix2pix), `lcm` (True),
  `init_image` (caminho; obrigatório em img2img/inpaint/pix2pix; referência opcional no flux2), `mask` (caminho; obrigatório em inpaint).
  Retorna o 1º PNG (`AAAAMMDD_HHMMSS_<modo>_<seed>.png`); com batch > 1 os outros ficam na mesma pasta (seed+1, ...).
  `total` = steps × batch.
- `"video"` (Wan 2.1 via sd.cpp): `width` (480), `height` (272), `frames` (17; ajustado p/ 4k+1), `steps` (20),
  `cfg_scale` (6.0), `fps` (16), `flow_shift` (3.0). Retorna o `.mp4` (ou o `.avi` se a conversão falhar) + um `.txt` com os parâmetros.
- `"ampliar"` (DEV beck, `ia_off/upscaler.py`, `ampliar(params, on_progress, cancel_flag)`; Real-ESRGAN ONNX na CPU):
  `entrada` (caminho da imagem; obrigatório; aceita também `input`), `escala` (2|4, padrão 4; aceita `scale`),
  `saida` (opcional: arquivo `.png/.jpg/.webp` OU pasta; padrão Imagens\IA_Off; aceita `output`), `tile` (padrão `cfg["upscale_tile"]`=256),
  `cfg_override`. Progresso = bloco i de N (`total` = nº de blocos); `cancel_flag` checado entre blocos (-> `Cancelled`).
  Retorna o PNG `AAAAMMDD_HHMMSS_<nome>_x<escala>.png` (transparência preservada; metadado `upscaler`).
  Config: `upscale_model` (.onnx; env `IA_OFF_UPSCALE_MODEL`; padrão `C:\IA\modelos\imagem\realesr-general-x4v3.onnx`),
  `upscale_backend` (`auto`|`onnxruntime`|`openvino`|`lanczos`), `upscale_tile`. Baixar o modelo (~5 MB, SHA-256 conferido):
  `python tools\baixar_ampliador.py`. Sem modelo/runtime: NÃO falha, amplia com Lanczos e sinaliza (nome `..._x4_lanczos.png`,
  metadado `upscaler = "lanczos (fallback: motivo)"`, `upscaler.ULTIMO_FALLBACK[0]` = motivo). Total = 1 passo nesse caso.
- Arquivos de modelo faltando -> `failed` com `FileNotFoundError`. O motor de imagem (pipelines residentes) é um só por processo,
  separado do da aba Imagem (que continua no fluxo antigo até a tela migrar).

### Voz (ia_off/voice_engine.py) — tipos "transcrever" e "falar"
- `transcribe(audio_path, progress_cb=None, cancel_flag=None, cfg=None, language=None) -> str` — faster-whisper, CPU int8;
  progresso em segundos de áudio (`passo`/`total` = s processados / duração).
- `speak(text, out_wav, progress_cb=None, cancel_flag=None, cfg=None) -> str` (caminho do WAV mono 16 bits) — Piper;
  progresso por frase. Usa o pacote `piper-tts`; com `piper_exe` no config usa o piper.exe (cancelar mata o processo).
  Cancelado não deixa WAV pela metade.
- Config: `voz_dir` (padrão `C:\IA\modelos\voz`, env `IA_OFF_VOZ_DIR`), `whisper_model` (`small`|`base`|pasta),
  `whisper_lang` (`pt`), `piper_voice` (`pt_BR-faber-medium` ou caminho .onnx), `piper_exe` ("").
  Pastas: `<voz_dir>\whisper\faster-whisper-<modelo>\` e `<voz_dir>\piper\<voz>.onnx(+.json)`. Baixar com `baixar_voz.bat`.
- Fila `"transcrever"`: `audio` (obrigatório, caminho), `idioma` (padrão do config), `modelo` (small/base), `saida` (pasta;
  padrão = pasta do áudio), `cfg_override`. Retorna o caminho do `.txt` com o texto (ler o arquivo no `finished`).
- Fila `"falar"`: `texto` (obrigatório), `voz` (padrão do config), `arquivo` (caminho .wav) ou `saida` (pasta; padrão Música\IA_Off),
  `cfg_override`. Retorna o caminho do `.wav`.

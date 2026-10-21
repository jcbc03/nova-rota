# Ampliador — API (ia_off/upscaler.py) — IA Off v3.0

Real-ESRGAN `realesr-general-x4v3` (SRVGGNetCompact, ~1,2 M parâmetros) em ONNX, só CPU. Responsável: DEV beck.

## Motor da fila (tipo `"ampliar"`)
```python
ampliar(params, on_progress, cancel_flag, runner=None) -> str   # caminho do arquivo gerado
```
Registrado por `engines_registry.register_all` (`reg("ampliar", ...)`). `runner` só para testes: callable
`run(x float32 [1,3,h,w] 0..1) -> [1,3,h*s,w*s]` (atributos opcionais `scale`, `name`).

| param | padrão | descrição |
|---|---|---|
| `entrada` (ou `input`) | — obrigatório | imagem de entrada; inexistente -> `FileNotFoundError` (vira `failed`) |
| `escala` (ou `scale`) | `4` | `2` ou `4`; outro -> `ValueError` |
| `saida` (ou `output`) | `config.output_dir("pictures")` | arquivo `.png/.jpg/.jpeg/.webp` ou pasta |
| `tile` | `cfg["upscale_tile"]` (256) | lado do bloco de entrada em px (mín. 8) |
| `pad` | `24` | contexto extra por lado (px reais, descartado na colagem: sem emendas) |
| `model_scale` | auto | escala do modelo; senão `runner.scale` ou detectada com bloco 8x8 |
| `cfg_override` | `{}` | sobrepõe o config só nesta tarefa |

Nome gerado (pasta): `AAAAMMDD_HHMMSS_<nome>_x<escala>.png` (`_x<escala>_lanczos.png` no fallback).
Modelo 4x com `escala=2`: roda em 4x e reduz com Lanczos. Transparência preservada (alfa ampliado com Lanczos).
PNG recebe metadados iTXt: `upscaler`, `source`, `scale`, `seconds`, `software` (`IA Off 3.0`).

## Sinais na fila
- `progress(id, i, N, pct, eta)`: um passo por bloco (`N = len(tile_grid(w, h, tile))`); no fallback 1 passo `(1, 1)`.
- `cancel_flag` checado antes de cada bloco e antes de salvar -> `engine_api.Cancelled` -> `cancelled(id)`;
  nenhum arquivo parcial é gravado e nenhum `progress` sai após o cancelamento.
- `phase`: o ampliador não emite fases (salvar é rápido).
- Erro do modelo (ex.: saída com escala errada) -> `failed(id, "RuntimeError: ...")`.

## Config (config.py)
| chave | padrão | descrição |
|---|---|---|
| `upscale_model` | env `IA_OFF_UPSCALE_MODEL` ou `<MODELOS_DIR>\imagem\realesr-general-x4v3.onnx` | arquivo .onnx |
| `upscale_backend` | `auto` | `auto` (onnxruntime -> openvino) \| `onnxruntime` \| `openvino` \| `lanczos` |
| `upscale_tile` | `256` | menor = menos RAM, um pouco mais lento |
| `threads` | nº de CPUs | threads do runtime |

O runner carregado fica em cache (chave backend + caminho + mtime); trocar o arquivo recarrega.

## Fallback Lanczos (nunca falha por falta de modelo/runtime)
Motivos: `upscale_backend=lanczos`; arquivo do modelo ausente; nenhum runtime carregou (erros de cada um no motivo).
Sinalização: sufixo `_lanczos` no nome, metadado `upscaler = "lanczos (fallback: <motivo>)"`,
`upscaler.ULTIMO_FALLBACK[0] = <motivo>` (None quando usou o modelo) e WARNING no log `ia_off.upscaler`.
A tela pode avisar o usuário lendo `ULTIMO_FALLBACK[0]` no `finished`.

## RAM / tile (i5-8365U, sem GPU)
- Por bloco (tile 256 + pad 24 = 304² px): entrada ~1 MB, mapas internos 64 canais ~24 MB cada, saída 4x ~18 MB float32.
  Pico do runtime fica na casa de 100–200 MB; somado ao resultado final (W·H·3 bytes, ex. 4K ≈ 25 MB).
- Pouca RAM: `upscale_tile` 128. Tile maior que a imagem = bloco único.

## Interação com a descarga do Ollama
`"ampliar"` está em `queue_unload_types`: com `queue_unload_ollama` ligado, a fila descarrega os modelos do Ollama
antes de começar (nunca com chat ativo; espera até `queue_unload_wait_s` e, no timeout, pula). Ver docs/FILA_API.md.

## Modelo — pendente
- Fonte oficial: pesos `.pth` em github.com/xinntao/Real-ESRGAN, release v0.2.5.0 (`realesr-general-x4v3.pth`,
  4 885 111 bytes; BSD-3-Clause, © 2021 Xintao Wang). O projeto **não publica ONNX oficial**.
- ONNX no repo: `models/realesr-general-x4v3.onnx` (4 866 432 bytes, SHA-256 `5f68a264…a0fb4d`), exportado do `.pth`
  por `tools/converter_ampliador.py` (precisa de torch); instalado por `tools/baixar_ampliador.py` (só copia e confere hash).
- Alternativa de terceiro: Qualcomm AI Hub (`qualcomm/Real-ESRGAN-General-x4v3`, BSD-3), zip ONNX float 4 540 895 bytes
  (formato de entrada/saída a validar).
- **Pendente: aprovação do Julio** para a fonte e distribuição do modelo; até lá o fallback Lanczos cobre a ausência.

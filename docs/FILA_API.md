# Fila de tarefas (job_queue.py), interface v1

Uma tarefa pesada por vez (CPU). Responsável: DEV beck.

## Métodos
- `enqueue(tipo, params) -> id`: tipo = "imagem" | "video"
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

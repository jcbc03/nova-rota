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

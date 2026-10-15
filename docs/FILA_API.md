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

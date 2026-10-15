"""Contrato comum dos motores de imagem/vídeo (sem Qt).

Todo ponto de entrada de geração aceita, opcionalmente:
- progress_cb(step:int, total:int)
- cancel_flag: qualquer objeto com is_set() (ex.: threading.Event)
Ao perceber o cancelamento o motor levanta `Cancelled`.
"""


class Cancelled(RuntimeError):
    """Geração cancelada pelo usuário (nome 'Cancelled' é reconhecido por jobs.py)."""

    def __init__(self, msg="Cancelado."):
        super().__init__(msg)


def make_cancel_check(cancel_flag=None, cancelled=None):
    """Une o flag novo (is_set) e o callable legado (cancelled()) em uma função sem argumentos."""
    def check():
        if cancel_flag is not None and cancel_flag.is_set():
            return True
        return bool(cancelled()) if cancelled is not None else False
    return check


def make_progress(progress_cb=None, progress=None):
    """Repassa (step, total) para o callback novo e o legado (os dois são opcionais)."""
    def emit(step, total):
        step, total = int(step), int(total)
        if progress is not None:
            progress(step, total)
        if progress_cb is not None:
            progress_cb(step, total)
    return emit


def raise_if_cancelled(check):
    if check():
        raise Cancelled()

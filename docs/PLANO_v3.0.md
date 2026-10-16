# IA Off – Plano da versão 3.0 (registrado em 15/10/2026)

Entrega: sexta, 30/10/2026. Prioridade: estabilidade, modelo 30B, Voz, polimento.

| Etapa | Prazo | Responsável | Tarefa |
|---|---|---|---|
| 1 | 17/10 | ia_off | Corrigir travamento do vídeo (Wan 2.1) |
| 1 | 17/10 | sub2 | Roteiro de testes por aba (começar pela aba de vídeo) |
| 2 | 20/10 | ia_off | Qwen3-30B-A3B no Ollama + Benchmark CPU x GPU |
| 2 | 20/10 | sub2 | Testar trocas de modelo |
| 3 | 23/10 | ia_off | Aba Voz (Whisper + Piper) |
| 3 | 23/10 | DEV beck | Busca vetorial local (Chroma/FAISS + embeddings via Ollama) e fila de tarefas imagem/vídeo |
| 4 | 28/10 | DEV Front | Polimento da interface, lentidão em conversas longas, barra de progresso/cancelar |
| 4 | 28/10 | sub2 | Teste completo no PC |
| 4 | 28/10 | sib1 | Documentação de uso e registro de versões |
| – | 29–30/10 | todos | Folga para correções e entrega |

Extra se sobrar tempo: ampliador de imagem com IA na CPU.

## Decisões
- Cada um mexe só no seu módulo: DEV beck `rag.py`; DEV Front `app.py` e `media_tabs.py`; ia_off `image_engine.py`, `sdcpp.py` e módulo de voz.
- Instalação no PC do Julio passa só pelo ia_off.
- Fila de tarefas com interface simples (enfileirar, ver andamento, cancelar); a tela só recebe atualizações por sinais do Qt.
- DEV Front só altera `app.py`/`media_tabs.py` depois da correção do vídeo.
- Modelos da Voz começam a baixar em paralelo ao Qwen.

## Riscos
- Vídeo no Wan leva dezenas de minutos na CPU (testes lentos).
- Modelos da Voz somam 1 a 2 GB.
- Documentos já importados precisam ser reindexados uma vez.
- Testes no PC real dependem das janelas combinadas com o ia_off; vídeo testado curto e em baixa resolução, com um teste longo no final.

Status: todos confirmaram os prazos em 15/10. Roteiro de testes: `docs/ROTEIRO_TESTES.md` (sub2).

## Atualizações (15/10, noite)
- Trabalho da 3.0 só em `/workspace/ia_off_v3` (git; commits com prefixo do responsável, ex. `beck: ...`). `/workspace/ia_off` fica intocada.
- Versão 2.3.1 (correção do travamento do vídeo) pronta; ia_off instala no PC do Julio junto com o Qwen3-30B. O aviso de conclusão libera o DEV Front em `app.py`/`media_tabs.py` e o sub2 nos testes de vídeo.
- Fila de tarefas aprovada (DEV beck, DEV Front, ia_off): módulo `job_queue.py`, uma tarefa pesada por vez.
  - `enqueue(tipo, params) -> id`, `cancel(id)`, `list_jobs()` (na fila, rodando, concluída, falhou, cancelada).
  - Sinais Qt: `started(id)`, `progress(id, pct, eta_s, passo, total)`, `finished(id, caminho_resultado)`, `failed(id, erro)`. A tela só escuta os sinais.
  - Motores aceitam callback de progresso (com passo e total) e checam flag de cancelamento entre passos.
  - Detalhes em `docs/FILA_API.md` (DEV beck).
- 15/10, 20h23: 2.3.1 instalada no PC do Julio; Qwen3-30B registrado no Ollama como `qwen3-30b-a3b` (~11 tok/s, ~30 s pra carregar). Etapa 2 (modelo) concluída antes do prazo; Benchmark CPU x GPU ainda pendente. DEV Front e sub2 liberados.
- Fila: sinal extra `cancelled(id)`; `progress(id, passo, total, pct, eta_s)`. Ver `docs/FILA_API.md`.
- Roteiro de testes pronto (sub2): `docs/ROTEIRO_TESTES.md`.
- Pendente decisão do Julio: apagar o GGUF original de 18 GB em `C:\IA\modelos\texto` (duplicado no Ollama).

## Regra de centralização de modelos (aprovada pelo Julio em 15/10)
- Todos os modelos ficam em `C:\IA\modelos`, por tipo: `texto`, `imagem`, `video`, `shared`, `ollama`, `huggingface` (ver `LEIA-ME.txt` na pasta).
- Ollama usa `C:\IA\modelos\ollama` (`OLLAMA_MODELS`); Hugging Face/diffusers/OpenVINO usam `C:\IA\modelos\huggingface` (`HF_HOME`).
- Projetos antigos (LivreStudio, EngenhariaIA, `C:\estudio_local`) acessam via junctions/hard links apontando pra `C:\IA\modelos`.
- **Nenhum caminho de modelo fixo no código**: tudo vem do `config.py` e dessas variáveis. Modelo novo entra direto na subpasta certa. O sub2 checa isso antes da entrega.
- Dados gerados (não modelos) ficam fora de `C:\IA\modelos`: índice vetorial dos documentos em `C:\IA\dados\rag`, caminho no `config.py`.
- Qwen3-30B: o GGUF em `C:\IA\modelos\texto` virou hard link pra cópia do Ollama (conteúdo conferido); 18 GB liberados, C: com 147 GB livres.
- 15/10, 21h: 3.0 instalada no PC do Julio antes da suíte limpa (exceção). Regra reafirmada pelo Gerente: na próxima instalação, primeiro a suíte verde, depois o PC.
- 15/10, 21h03: suíte limpa verde (88 ok, 1 pulado, commit `2d73849`); instalação no PC conferida. Falha conhecida: barra do vídeo indo a 242/242 no carregamento (ia_off corrige no `sdcpp.py`).
- 15/10, 21h44: lentidão do vídeo (V2, ~200 s/passo) causada pelo sd.cpp rodando na Vulkan da UHD 620. Decisão: vídeo na CPU por padrão, Vulkan opcional (ia_off, `sdcpp.py`); V2 cancelado e registrado como tempo Vulkan no V7.
- Regra da fila de descarregar o Ollama (`queue_unload_ollama`) entrou desligada por padrão (beck `a6b356c`), até existir proteção pro chat em andamento.
- Regra nova: cada um faz commit só dos próprios arquivos (`git add <caminho>`).

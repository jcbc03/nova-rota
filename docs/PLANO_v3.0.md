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

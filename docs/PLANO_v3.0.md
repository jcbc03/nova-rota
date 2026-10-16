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
- 15/10, 22h: repositório no GitHub privado do Julio (`jcbc03/nova-rota`, branch `main`). Regra: commit só dos próprios arquivos e `git push` logo depois; se recusar, `git pull --rebase` e push de novo.
- 15/10, 23h46: suíte limpa verde (101 ok, 1 pulado, `7c31986`); correções do Wan (`076a2d5`) e da transcrição (`d798d2c`) instaladas no PC, backup em `C:\IA\backup\hotfix_20261015_2346`. Lista de bugs zerada. Pendente: V8 (vídeo curto real, ~90 min) e revisão final antes de 30/10.

## Decisão 16/10: moderador opcional (aprovado pelo Julio)
- Vem **desligado** por padrão. Desligado, o app fica idêntico ao de hoje: sem filtro, sem checagem, sem termos extras no negativo, e as listas nem são carregadas.
- Ligado, tem os níveis Leve, Médio e Rígido, tudo offline e sem modelo extra. As chaves são `moderacao_ativa` e `moderacao_nivel` no `config.py`.
- As listas ficam editáveis em `C:\IA\dados\moderacao.json`. Se o arquivo faltar ou tiver erro, o app usa o padrão embutido e registra um aviso no log. A checagem é por palavra inteira, sem acento e em minúsculas.
- Um prompt bloqueado levanta `PromptBloqueado(motivo)` antes de carregar qualquer modelo. A checagem fica no `engines_registry`.
- É preciso senha pra ligar, desligar ou mudar o nível. Só o hash é guardado (PBKDF2 com salt, em `C:\IA\dados`). Quem esquecer a senha apaga o arquivo e cria uma nova.
- Responsáveis: DEV beck (módulo e senha), DEV Front (tela), ia_off (motores), sub2 (testes), sib1 (manual e changelog). Prazo: 23/10.

## 16/10: modelos novos em avaliação (Julio aprovou testar só estes)
- **Texto:** Qwen3.8-27B abliterated, GGUF pro Ollama, cerca de 16 GB. Estimativa de 1 a 1,5 palavra por segundo, uns 8x mais lento que o Qwen3-30B. Talvez precise atualizar o Ollama.
- **Imagem:** Z-Image-Turbo, 6,7 GB, roda no sd.cpp. Estimativa de 5 a 8 min por imagem 512. Precisa de três chaves novas no `config.py` (`zimage_model`, `zimage_llm`, `zimage_vae`) e de um modo "Z-Image Turbo" na aba Imagem.
- **Imagem (segunda opção):** Qwen-Image 2.1 "Uncensored", 9,9 GB. É o modelo original reempacotado e pode levar de 30 min a horas por imagem. Não é recomendado.
- **Vídeo:** Wan 2.2 5B, 8,5 GB, roda no sd.cpp. Estimativa de 1 a 1,5 h por clipe. Usa outro VAE e talvez precise de um `sd-cli` mais novo.
- Situação: aguardando o Julio aprovar o download (a sugestão é baixar texto, Z-Image e Wan 2.2, uns 32 GB). Os modelos ficam em `C:\IA\modelos`, sem caminho fixo no código. O ia_off mede a velocidade real e o sub2 valida. O manual só é atualizado depois da instalação.

## Status em 16/10, 9h
- Correção: o vídeo **não** está pausado. O Julio liberou tudo às 8h12. Ordem no PC: terminar o V5, fazer o bloco do moderador e depois rodar o V6. O V4 já passou (cancelou em 0,6 s). Com o Wan 2.2 a 480x272, deu uns 107 s por passo no V4 e uns 67 s no V5.
- O Julio autorizou a equipe a cuidar do PC e criar uma senha temporária. A senha não passa pelo chat. Depois dos testes SE1 a SE4, a proposta é apagar o `moderacao_senha.json` pro Julio criar a dele, mas só com o ok dele. Ele também pode usar o botão "Trocar senha…" (`0111f92`).
- Pendente: instalar o `0111f92` no PC, MO5 na tela, SE1 a SE4 e o resto do R6 (Z-Image e Qwen3.8 dentro do app, com o moderador ligado e desligado).

## Status em 16/10, 18h (substitui o de 9h)
- PC do Julio no `4c6d743`, instalado às 15h50, com backup em `C:\IA\backup\v3head_20261016_1550`. Suíte limpa com 173 ok e 3 skips. Teste rápido depois da instalação ok (chat Qwen3.8, Z-Image e Wan 2.2).
- Aprovados no PC: V3 a V8 (Wan 2.2 5B, V6 longo em ~68 min), fases Decodificando/Salvando/Convertendo em vídeo, FLUX.2 e Z-Image, C1 a C4, M1 a M4, D1 a D4, I1 a I4, A1 a A3, R1 a R6, MO1 a MO6, SE1 a SE3, SE5, P1 e S1 (prioridade alta corrigida em `c2cd115` e `945402d`).
- Etapas 1 a 3 e moderador (prazo 23/10) adiantados. Nada atrasado.
- Depende do Julio: S3 (sem internet), SE4 (apagar a senha temporária, só com o ok dele), cliques reais (menu da aba Vídeo, MO5, SE1), trocar a senha temporária e ok pra apagar os temporários de instalação.
- Pontas soltas: confirmar pelo log do V8 que o negativo do Wan chega legível (falha "????", ia_off) e reconferir o V4 com `950cb26` e `3786502` (sub2).
- Próximo: etapa 4 (robustez e polimento) e versão candidata 3.0 (`docs/NOTAS_3.0_RC.md`).

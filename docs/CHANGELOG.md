# Registro de versões – IA Off

## 3.0 (instalada no PC do Julio em 15/10/2026; versão atual no PC: `0111223`, instalada em 16/10 às 14h53, backup em `C:\IA\backup\v3head_20261016_1453`; em testes; entrega prevista 30/10/2026)
### Novo
- Busca em documentos com índice vetorial local FAISS (`faiss-cpu`, com fallback numpy); índice em `rag_dir` do `config.py` (padrão `C:\IA\dados\rag`). Documentos antigos são reindexados uma vez na abertura, com andamento na barra de status. (beck `8bf11e9`, front `fde8c1b`)
- Fila de tarefas de imagem e vídeo (`job_queue.py`): uma tarefa por vez, sinais `started`, `progress`, `finished`, `failed`, `cancelled`. (beck `51aeff4`)
- Motores de imagem e vídeo com progresso por passo e cancelamento; o sd.cpp encerra todos os processos ao cancelar; motores registrados na fila e ligados no app. (ia_off `79df871`, `39c5dc2`; front `915ef28`)
- Ampliador de imagem com IA na CPU: Real-ESRGAN `realesr-general-x4v3` (4,9 MB) via ONNX Runtime, em blocos, com progresso e cancelamento; sem o modelo, usa Lanczos e marca o arquivo com `_lanczos`. Modelo convertido dos pesos oficiais do Real-ESRGAN (release v0.2.5.0) e incluído no repositório com licença BSD-3, sem download de terceiros. (beck `482a0df`, `5efbedc`)
- Motor de voz offline: Whisper (transcrever, gera `.txt`) e Piper pt_BR (falar, gera `.wav`), tipos "transcrever" e "falar" na fila; modelos ~550 MB. (ia_off `e248a1b`)
- Abas de Imagem e Vídeo pela fila: SD 1.5 uma vez só na RAM; barra com estado, passo, % e tempo restante, e botão Cancelar. (front `020cd6c`)
- Aba Voz: transcrever um áudio (texto na tela com botão de copiar) e falar um texto (toca na hora, com ouvir de novo), com barra de progresso e Cancelar. (front `9b17af5`)
- Botão Ampliar (2x/4x) embaixo da galeria da aba Imagem, pela fila, com aviso quando cai no Lanczos. (front `0fac9a7`)
- Pacote de atualização `atualizar_v3.bat` (~665 MB), com backup e versões travadas. (ia_off `7b613cf`)
- Opção da fila pra liberar da RAM os modelos do Ollama antes de tarefas pesadas (`queue_unload_ollama`, desligada por padrão). (beck `a6b356c`)
- Vídeo usa a CPU por padrão (Vulkan opcional via `video_vulkan`) e a barra não conta mais o carregamento como passo. (ia_off `bb21e2d`)
- Polimento visual: barra de progresso, foco, hover, grupos, rolagem e barra de status. (front `6b581cc`)
- Moderação opcional, desligada por padrão, com os níveis Leve, Médio e Rígido, listas editáveis em `moderacao.json` e senha guardada só como hash pra alterar o filtro: o módulo é do DEV beck (`eba4fd9`, ajuste do Médio em `d7c13f1`), a tela é do DEV Front (`820ae78`) a ligação nos motores é do ia_off (`a80196b`) e a do chat é do DEV Front (`6a4e4a2`). Transcrever e Ampliar ficam sem checagem. O botão "Trocar senha…" pede a senha atual e a nova (front `0111f92`). A checagem MO no PC roda com `tests/mo_pc_check.py`, sem mexer na configuração (sub2 `ca17c6d`). Validado no PC em 16/10 (`92b5253`): MO1 a MO6, SE1 a SE3 e SE5 ok. O SE4 (apagar o arquivo da senha) espera o ok do Julio. A senha temporária está em `C:\IA\dados\SENHA_TEMPORARIA.txt`, e a moderação ficou desligada. Instalado no PC em 16/10, à 1h09 (`3179726`, backup em `C:\IA\backup\mod_20261016_0109`).

- Modo de imagem "Z-Image Turbo (sd.cpp)", com 8 passos e guidance 1, e caminhos nas chaves `zimage_model`, `zimage_llm` e `zimage_vae`. Instalado no PC em 16/10 (`ac06c3a`). Medido em 512×512 com 8 passos: cerca de 13 min (774 a 800 s), igual com a moderação ligada ou desligada. (beck `0136c70`, front `d165531`, ia_off `f190de5`)

- Modelo de chat `qwen3.8-27b-aggressive` (Qwen3.8-27B abliterated, IQ4_XS, 15,7 GB) no Ollama. Medido: de 1,4 a 1,6 tokens/s, com 63 a 84 s até a primeira palavra no app. (ia_off, 16/10)

### Melhorado
- Com `queue_unload_ollama` ligado, a fila não descarrega o Ollama enquanto um chat está respondendo. Ela espera até `queue_unload_wait_s` (120 s) e, se passar disso, roda o job sem descarregar. O padrão continua desligado. (beck `0a3000d`, front `7d717b1` no chat e nos documentos)
- Chaves `wan22_model`, `wan22_t5` e `wan22_vae` pro Wan 2.2 5B, que começam vazias e aceitam `IA_OFF_WAN22_*`. A chave `video_modelo` escolhe entre `wan21` (padrão) e `wan22`. Seletor Wan 2.1/2.2 na aba Vídeo (front `497b0f6`). O motor cai no 2.1 se faltar algum arquivo do 2.2, e o 2.2 gera a 24 fps (ia_off `9ce183b`). Fases depois do último passo pelo sinal `JobQueue.phase` (ia_off `23f9c97`, doc beck `fed6825`, tela front `9ca9fea`). Testado no PC: V5 (9 quadros, 8 passos) em ~25 min e V6 (17 quadros, 20 passos) em ~68 min. O V8 (20 passos) levou ~68 min, sendo ~29 min de decodificação depois do último passo. A fase "Decodificando…" não apareceu no log do V8 porque ele rodou direto pelo motor, sem passar pela fila. Agora a aba Vídeo também escreve `[fase] …` no log (front `ad56e06`). Conferido pela fila: no Wan, as fases chegam (decodificação de ~4 min 44 s). No FLUX.2 e no Z-Image elas passaram a aparecer com o `0111223` (beck), que passa o `phase_cb` com a mesma lógica do vídeo. A suíte deu 173 ok e 3 skips. Instalado no PC em 16/10 às 14h53, com backup em `C:\IA\backup\v3head_20261016_1453`. V3 ok: durante um vídeo Wan 2.2 de 713 s a interface respondeu sempre, com maior pausa de 0,41 s. R6 ok pelo seletor (`video_modelo: wan22` no `cfg_override`): 480×272, 5 quadros e 2 passos em 713 s, sendo 523 s de decodificação, com as três fases e `modelo: wan22` no .txt. Com moderação ligada: 723 s, negativo preenchido pela moderação, e depois a moderação foi desligada de novo. Falta o Julio conferir o seletor na tela da aba Vídeo (beck `f2c2c93`, `bcc2217`)
- Chat rápido em conversas longas: histórico montado uma vez e tela atualizada no máximo a cada 80 ms; rolagem automática só quando você está no fim da conversa. (front `daa045d`)
### Corrigido
- Prioridade alta (turbo) agora é aplicada no Windows 64-bit: `GetCurrentProcess` com `restype c_void_p`, e o erro do Windows vai pro log se falhar (`c2cd115`, `945402d`). Suíte 173 ok e 3 skips. S1 a refazer depois da instalação.
- Depois de Cancelar, a aba Vídeo mostrava um passo a mais que não existia (ex.: "passo 4/20"). Agora a tela e a fila ignoram o progresso que ainda chega. (front `950cb26`, beck `3786502`)
- O `sd-cli` não abria fora do app (erro 0xC0000135, faltava a `vcomp140.dll`). Agora o código acha a DLL sozinho e monta o PATH do `sd-cli` (`runtime_dlls.py`, chave opcional `vcruntime_dir`). Testado no PC sem as cópias manuais: achou a DLL no PySide6 e o `sd-cli` abriu normal e com Vulkan. As cópias manuais continuam como reserva. (beck `7e67730`, ia_off `b0eb083`, instalado em 16/10 às 7h19)
- Nenhum caminho de modelo fica mais fixo no código, e nenhum aponta pro OneDrive. Os padrões vêm de `MODELOS_DIR` (`C:\IA\modelos`, que pode ser trocada por `IA_OFF_MODELOS_DIR`), e o `ollama_exe` usa `%LOCALAPPDATA%`. (beck `d4c9b83`)
- O seletor de modelo do chat listava modelos de embeddings (como `embeddinggemma-2:740m`), que davam "Erro 400: does not support chat". Agora eles ficam fora da lista, e um modelo salvo que não serve pra conversa volta pra um modelo de chat. (front `25b048e`, aguardando a suíte e a instalação)
- `atualizar_v3.bat` não copiava a pasta `models/` (modelo do ampliador). (ia_off `fc16923`)
- Documentos importados na 2.x sumiam: a 3.0 agora copia o índice antigo de `%APPDATA%\IA_Off_v1\rag` pra `C:\IA\dados\rag` na primeira abertura, sem apagar o antigo, e migra. (front `6ee483e`)

- Voz (Piper) derrubava o app quando instalado em caminho com acento, como "Área de Trabalho". (ia_off `1755162`)
- Botão Ampliar quebrado: tipo "ampliar" não registrado na fila. (ia_off `b8b39bf`)
- Modelo de embeddings padrão trocado pra `embeddinggemma-2:740m`, já presente no Ollama do PC. (beck `98931fb`)
- Teste de estresse da interface estável no Windows. (sub2 `4cfdaf7`)
- Cancelar a transcrição levava 88 s; agora para em 0,1 s. (ia_off `d798d2c`)
- Prompt negativo padrão do vídeo Wan chegava como "????" no Windows; agora vai em inglês, e os prompts do vídeo têm os acentos trocados pela letra base. (ia_off `076a2d5`)

### Em andamento
- Revisão final antes da entrega de 30/10.

## 2.3.1 (15/10/2026)
- Corrigido: o app fechava sozinho ao carregar a geração de vídeo (Wan 2.1).
- Novo modelo de chat: Qwen3-30B-A3B no Ollama (`qwen3-30b-a3b`, ~11 tokens/s no PC do Julio).

## 2.3
- Chat via Ollama, perguntas sobre documentos, imagem (SD 1.5 + LCM, FLUX.2 Klein), seletores até 8K, tradução automática do prompt, modo turbo e modelos centralizados em `C:\IA\modelos`.

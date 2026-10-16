# Registro de versões – IA Off

## 3.0 (instalada no PC do Julio em 15/10/2026, em testes; entrega prevista 30/10/2026)
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
### Melhorado
- Chat rápido em conversas longas: histórico montado uma vez e tela atualizada no máximo a cada 80 ms; rolagem automática só quando você está no fim da conversa. (front `daa045d`)
### Corrigido
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

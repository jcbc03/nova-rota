# Registro de versões – IA Off

## 3.0 (em desenvolvimento, entrega prevista 30/10/2026)
### Novo
- Busca em documentos com índice vetorial local FAISS (`faiss-cpu`, com fallback numpy); índice em `rag_dir` do `config.py` (padrão `C:\IA\dados\rag`). Documentos antigos são reindexados uma vez na abertura, com andamento na barra de status. (beck `8bf11e9`, front `fde8c1b`)
- Fila de tarefas de imagem e vídeo (`job_queue.py`): uma tarefa por vez, sinais `started`, `progress`, `finished`, `failed`, `cancelled`. (beck `51aeff4`)
- Motores de imagem e vídeo com progresso por passo e cancelamento; o sd.cpp encerra todos os processos ao cancelar; motores registrados na fila e ligados no app. (ia_off `79df871`, `39c5dc2`; front `915ef28`)
- Ampliador de imagem com IA na CPU: Real-ESRGAN `realesr-general-x4v3` (4,9 MB) via ONNX Runtime, em blocos, com progresso e cancelamento; sem o modelo, usa Lanczos e marca o arquivo com `_lanczos`. Modelo republicado por terceiro no Hugging Face, hash conferido. (beck `482a0df`)
- Motor de voz offline: Whisper (transcrever, gera `.txt`) e Piper pt_BR (falar, gera `.wav`), tipos "transcrever" e "falar" na fila; modelos ~550 MB. (ia_off `e248a1b`)
- Abas de Imagem e Vídeo pela fila: SD 1.5 uma vez só na RAM; barra com estado, passo, % e tempo restante, e botão Cancelar. (front `020cd6c`)
### Melhorado
- Chat rápido em conversas longas: histórico montado uma vez e tela atualizada no máximo a cada 80 ms; rolagem automática só quando você está no fim da conversa. (front `daa045d`)
### Em andamento
- Tela: aba Voz, depois botão Ampliar (2x/4x), depois polimento (DEV Front).
- Suíte de testes em ambiente limpo (sub2).
- Pacote único de instalação no PC do Julio: `faiss-cpu`, `onnxruntime`, modelos de voz e do ampliador (ia_off, após aprovação do sub2).
- Benchmark CPU x GPU Intel (ia_off).

## 2.3.1 (15/10/2026)
- Corrigido: o app fechava sozinho ao carregar a geração de vídeo (Wan 2.1).
- Novo modelo de chat: Qwen3-30B-A3B no Ollama (`qwen3-30b-a3b`, ~11 tokens/s no PC do Julio).

## 2.3
- Chat via Ollama, perguntas sobre documentos, imagem (SD 1.5 + LCM, FLUX.2 Klein), seletores até 8K, tradução automática do prompt, modo turbo e modelos centralizados em `C:\IA\modelos`.

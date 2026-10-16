# IA Off v2.3.1 — Assistente de IA local (offline)

Janela nativa (PySide6/Qt), sem navegador. Usa o **Ollama** em `localhost:11434` (CPU).

## Instalação
1. Extraia a pasta (ex.: `C:\ia_off`).
2. Dê dois cliques em `instalar.bat` (cria `.venv` com Python 3.11 e instala dependências).
3. Abra com `iniciar.bat` (sem console).

## Uso
- **Chat**: escolha o modelo (ex.: `qwen2.5:3b`), Ctrl+Enter envia, "Parar" interrompe. Conversas ficam salvas na barra lateral.
- **Importar GGUF…**: escolha uma sugestão (Qwen3-4B ou Qwen2.5-Coder-7B), o app gera um Modelfile e roda `ollama create`. O GGUF é referenciado no lugar original.
  Obs.: o Ollama armazena os pesos internamente (em `%USERPROFILE%\.ollama\models`), ocupando espaço extra (~2,5 GB / ~4,7 GB).
- **Documentos**: adicione PDF/TXT/DOCX/MD, depois pergunte. Usa o modelo de embeddings `embeddinggemma-2:740m` do Ollama (padrão do `config.py`, já instalado no PC do Julio). Se faltar: botão "Baixar modelo de embeddings" ou `ollama pull embeddinggemma-2:740m` (internet uma única vez).
- **Configurações**: URL/caminho do Ollama, threads (recomendado 4), contexto, temperatura, prompt de sistema.

Se o Ollama não estiver rodando, o app tenta iniciar `ollama serve` automaticamente.
Dados e log de erros: `%APPDATA%\IA_Off_v1`.

## Novidades da v2: Imagem e Vídeo (CPU)
**Atualizar uma instalação v1:** feche o app e rode `atualizar.bat` (instala torch CPU, diffusers etc. no `.venv` existente, ~1 GB de download). Instalação nova: `instalar.bat` já inclui tudo.

### Aba Imagem
- Modos: **Texto → Imagem**, **Imagem → Imagem**, **Inpaint** (abra uma imagem, marque "Pintar máscara" e pinte a área a refazer) e **Editar por instrução** (InstructPix2Pix, ex.: "make it winter").
- Usa os modelos no lugar: `C:\estudio_local\models\imagem\sd15` (se faltarem tokenizer/scheduler/model_index o app usa um tokenizer CLIP embutido e o agendador padrão do SD 1.5; os pesos fp16 são convertidos para float32 na CPU), LCM LoRA (padrão 5 passos, guidance 1,2), `sd15-inpainting` e `timbrooks/instruct-pix2pix` do cache do Hugging Face (somente offline).
- **FLUX.2 Klein 4B** (melhor qualidade, via stable-diffusion.cpp): 4 passos, CFG 1,0. Mais lento que SD 1.5+LCM.
- Imagens salvas em `Imagens\IA_Off`. Tempo típico no i5-8365U: SD1.5+LCM 512×512 ≈ 30–90 s; a 1ª geração carrega o modelo.

### Aba Vídeo (Wan 2.1 T2V 1.3B)
- Usa o **stable-diffusion.cpp** (`sd-cli.exe`, release `master-964-1d0a58a`, CPU x64). Na primeira vez o app baixa ~18 MB (ou rode `baixar_sdcpp.bat`). Depois funciona offline.
- Padrão: 480×272, 17 quadros, 20 passos, 16 fps. **Muito lento na CPU** (dezenas de minutos). Saída MP4 em `Vídeos\IA_Off`, com prévia no app.
- Os caminhos de todos os modelos ficam em **Configurações → Caminhos dos modelos**.

## Novidades da v2.1: tradução automática do prompt (PT → EN, offline)
- Nas abas **Imagem** e **Vídeo** há a opção **"Traduzir prompt para inglês"**. Padrão: ligada para SD 1.5, Inpaint e Pix2Pix; desligada para FLUX.2 e Wan (pode ligar quando quiser).
- A tradução usa o modelo de chat do Ollama definido em **Configurações → Modelo de tradução** (padrão `qwen2.5:3b`, temperatura 0), traduz prompt e negativo sem acrescentar, remover ou censurar nada e mantém listas de tags separadas por vírgula.
- Textos que já parecem estar em inglês não são enviados ao modelo. As traduções ficam em cache (`%APPDATA%\IA_Off_v1\traducoes.json`).
- O texto traduzido aparece no campo "Em inglês" (e no log do vídeo) antes da geração. Nas imagens PNG, prompt traduzido e original ficam nos metadados; o nome do arquivo recebe `_en`. Cada vídeo ganha um `.txt` com os prompts.
- Se o Ollama estiver desligado, o app avisa e usa o prompt original.

## Novidades da v2.2: proporção e resolução
- **Proporção** (1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3, 5:4, 4:5, 21:9, 9:21, 2:1 ou *Personalizado* com L×A manual) e **Resolução** pelo lado curto (256p … 1024p HD, 1440p 2K, 2160p 4K, 4320p 8K). Ex.: 16:9 em 8K = 7680×4320. O rótulo mostra o tamanho final.
- Na CPU cada motor gera no seu **tamanho nativo** (SD 1.5 até 768 no lado longo, FLUX.2 até 1024, múltiplos de 64) e, se o pedido for maior, a imagem é **ampliada** com Lanczos + nitidez leve (opção "Nitidez leve no upscale"). Os metadados guardam o tamanho gerado e o final.
- 4K/8K: o upscale é rápido, mas usa bastante RAM e gera PNGs grandes (aviso na tela). O upscale não cria detalhes novos, apenas amplia.
- Vídeo (Wan 1.3B): mesmas proporções, resoluções 256p/384p/480p, máximo 832×480 (ou 480×832), múltiplos de 16, sem upscale.
- As últimas escolhas ficam salvas.

## Novidades da v2.3: desempenho máximo (CPU + GPU Intel)
**Instalar o suporte à GPU Intel (opcional, recomendado):** feche o app e rode `instalar_gpu.bat` (instala OpenVINO + optimum-intel no `.venv`; ~600 MB). No fim ele mostra os dispositivos; deve aparecer `GPU`. Se não aparecer, atualize o driver Intel UHD 620 (Intel Driver & Support Assistant).

**Configurações → Desempenho**
- **Dispositivo**: Auto (padrão) / CPU / GPU Intel (OpenVINO) / GPU Vulkan / CPU (OpenVINO).
  - SD 1.5, Imagem→Imagem e Inpaint: GPU Intel via OpenVINO. A 1ª vez de cada modelo **exporta** para OpenVINO (vários minutos, com o LCM já fundido) e salva em `%LOCALAPPDATA%\IA_Off_v1\ov_cache`; depois carrega rápido. Mudar o tamanho recompila (alguns segundos a 1 min); o cache de kernels acelera as próximas vezes.
  - Pix2Pix continua na CPU (PyTorch).
  - Wan e FLUX.2: sd.cpp **Vulkan** (`sd-master-1d0a58a-bin-win-vulkan-x64.zip`, baixado uma vez para `%APPDATA%\IA_Off_v1\sdcpp\vulkan`).
  - Qualquer erro na GPU volta automaticamente para a CPU (aparece no log).
- **Modo máximo** (padrão ligado): todas as 8 threads, prioridade alta do processo, pipelines residentes na memória entre gerações, sem attention slicing/CPU offload, `channels_last`. `torch.compile` não é usado no Windows (exige compilador).
- **Benchmark**: gera 512×512 com 4 passos em cada backend disponível, mostra os tempos e oferece usar o mais rápido.
- A GPU integrada usa a memória compartilhada do Windows automaticamente (até metade da RAM, ~16 GB); não há limite imposto pelo app.
- **Ollama (chat/tradução)**: continua na CPU — o Ollama não acelera GPU Intel integrada oficialmente.
- Com prioridade alta e todas as threads, o PC pode ficar menos responsivo durante a geração; desligue o Modo máximo se precisar usar o PC ao mesmo tempo.

## v2.3.1: correção de travamentos
- Corrigido fechamento inesperado (Qt6Core 0xc0000005 / 0xc0000409): atualizações de tela vindas de tarefas em segundo plano agora sempre rodam na thread da interface; tarefas são canceladas e aguardadas ao fechar; variáveis de ambiente não são mais alteradas durante a geração; mensagens de progresso muito rápidas (sd.cpp) são agrupadas.
- Diagnóstico em `%APPDATA%\IA_Off_v1`: `crash.log` (falhas nativas, faulthandler), `erro.log` (exceções Python, inclusive de threads) e `qt.log` (mensagens do Qt). Envie esses arquivos se algo travar.

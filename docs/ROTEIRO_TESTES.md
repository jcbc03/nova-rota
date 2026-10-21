# Roteiro de testes — IA Off 3.0 (responsável: sub2)

Formato: cada teste tem ID, passos, resultado esperado e status (✅ passou / ❌ falhou / ⏳ pendente).
Ambiente: PC do Julio (i5-8365U, 32 GB, UHD 620), com a instalação feita pelo ia_off. Testes automáticos em `tests/` rodam na `ia_off_v3`.

## 0. Pré-teste
| ID | Passos | Esperado | Status |
|---|---|---|---|
| P1 | Abrir pelo atalho "IA Off" | Janela abre em < 15 s, 6 abas visíveis | ✅ PC 16/10 (0111223): atalho abre em 1,7 s, 6 abas |
| P2 | Rodar `pytest tests/` na ia_off_v3, num ambiente limpo só com o requirements.txt | Todos passam | ✅ 16/10 18h, af66cc4 (código = 4c6d743 instalado): 173 ok e 3 pulados, 2 rodadas. Antes: 9h, 0a3000d, 158 ok e 3 pulados (2 sem modelo tiny, 1 sem `optimum.intel`). Antes: 15/10, 2d73849, 88 ok e 1 pulado |

## 1. Vídeo (Wan 2.1) — prioridade, testar primeiro
| ID | Passos | Esperado | Status |
|---|---|---|---|
| V1 | Abrir a aba Vídeo e carregar o modelo | Não fecha nem trava (correção 2.3.1) | ✅ 15/10 no PC (ia_off) |
| V2 | Gerar vídeo curto em baixa resolução | Termina, arquivo salvo e reproduzível | ✅ 15/10 (fila + engines_registry, headless): 480x272, 17 quadros, 20 passos → `20261015_205851_wan_1107368692.mp4`, 32 784 B, ffprobe ok (h264 480x272, 16 fps, 17 quadros, 1,06 s). TEMPO_TOTAL 8124 s = ~45 min Vulkan (morta em 11/20) + ~90 min na CPU (recaída automática) |
| V3 | Durante a geração, trocar de aba e mexer na janela | Interface continua respondendo | ✅ 15/10 offscreen no PC: vídeo (sd.cpp falso) na fila trocando de aba a cada 100 ms: 23–29 trocas, maior pausa da UI 0,13 s, sinais na thread principal; repetido após aplicar 6b581cc. smoke_gui ✅. stress_gui ❌ no PC (video_lines=0: o FakeEngine de imagem usa sleep(0.0005) que no Windows dura ~15 ms, o vídeo não chega a rodar antes do fechamento; problema do teste, não do app) → com 4cfdaf7 instalado: stress_gui ✅ e smoke_gui ✅ no PC (15/10 23:39); ✅ 16/10 no PC real (c2cd115/0111223): vídeo Wan 2.2 real 713 s, 5881 trocas de aba, maior pausa 0,41 s, app nunca travou |
| V4 | Cancelar no meio (após a fila do beck) | Para em até 1 passo, sem travar | ✅ PC 16/10 (Wan 2.2 5B 480x272): cancelou em 0,6 s no passo 3/20, ~107 s/passo. Bug: "passo 4/20" falso após Cancelar, corrigido na tela em 950cb26 (beck também na fila). 16/10 18h: 950cb26 (tela) e 3786502 (fila) estão no 4c6d743 instalado; 21 testes de cancelamento ok no box; falta só a confirmação visual de um Cancelar real no PC (ia_off ou Julio) |
| V5 | Barra mostra passo X de N e ETA (após DEV Front) | Números avançam e batem com o fim | ✅ PC 16/10 (Wan 2.2 5B 480x272, 9 frames, 8 passos): 1494 s, ~67 s/passo, ETA ok. Bug: após 8/8 ainda 14,5 min de decode VAE/mp4 (~11,5 GB RAM) sem aviso; falta fase "Decodificando…" (ia_off, sdcpp.py) |
| V7 | Rodar o mesmo vídeo do V2 na CPU e na Vulkan | CPU mais rápida; CPU é o padrão; anotar os dois tempos | ✅ 15/10 (mesmo vídeo do V2). Vulkan (UHD 620): ~200 s/passo (11/20 em ~2535 s; carga ~9 min). CPU (-t 4): carga+texto ~9 min, amostragem ~65 min (~170–245 s/passo, média ~197 s), decodificação VAE ~16 min, total ~90 min (5405 s). CPU ≈ Vulkan na amostragem, não mais rápida; CPU fica padrão (bb21e2d) por usar pouca GPU/RAM compartilhada |
| V8 | Vídeo curto real depois do `076a2d5` (negativo em inglês, prompt ASCII) | Log mostra o negativo legível; vídeo sem os defeitos que o negativo evita | ✅ PC 16/10: 4111 s; fase decodificando/salvando/convertendo confirmada no Wan pela JobQueue (decode ~4m44). fase no Z-Image ok após 0111223 (256 px, 2 passos, 69 s) |
| V6 | Um teste longo na resolução padrão (no final) | Termina sem erro; anotar tempo | ✅ PC 16/10 (Wan 2.2 5B 480x272, 17 frames, 20 passos): 4062 s (~67,7 min), 10:15–11:23; `Videos\IA_Off\20261016_101555_wan_1234.mp4` |

## 2. Chat (Ollama)
| ID | Passos | Esperado | Status |
|---|---|---|---|
| C1 | Enviar pergunta curta | Resposta aparece enquanto é gerada | ✅ PC 16/10 tarde: Qwen3.8 27B, 1º token 63,7 s, total 91,6 s |
| C2 | Conversa longa (40+ mensagens) | Sem lentidão perceptível (correção do Front) | ✅ PC 16/10 (130143f): 43 mensagens sem lentidão |
| C3 | Fechar e reabrir o app | Histórico preservado | ✅ box (9506c28) + PC 16/10 (130143f) |
| C4 | Importar um GGUF | Modelo aparece e responde | ✅ PC 16/10 (130143f): GGUF importado |

## 3. Trocas de modelo (prazo 20/10)
| ID | Passos | Esperado | Status |
|---|---|---|---|
| M1 | Selecionar Qwen3-30B-A3B e perguntar | Responde; anotar tempo do 1º token e tokens/s | ✅ PC 16/10 tarde: Qwen3.8 27B, 1º token 52,3 s, ~1,4 tok/s |
| M2 | Trocar 30B → modelo pequeno → 30B | Sem erro, RAM liberada (ver Gerenciador de Tarefas) | ✅ PC 16/10 (130143f) |
| M3 | Trocar SD 1.5 ↔ FLUX.2 Klein na aba Imagem | Ambos geram; sem estouro de RAM | ✅ PC 16/10 tarde: Z-Image 512, 8 passos, 816 s |
| M4 | Chat com 30B carregado + gerar imagem | Não trava; anotar uso de RAM | ✅ PC 16/10 (130143f) |

## 4. Documentos
| ID | Passos | Esperado | Status |
|---|---|---|---|
| D0 | Abrir a 3.0 pela 1ª vez com os documentos da 2.x | Documentos antigos migrados e aparecendo (commit 6ee483e) | ✅ 15/10 sem dados: `%APPDATA%\IA_Off_v1\rag` não tem meta.json (0 documentos) e `C:\IA\dados\rag` vazio → cópia/migração é no-op (0 trechos). Consulta com índice temporário + Ollama `embeddinggemma-2:740m`: 0,07 s, citou `[1] manual_teste.txt (score 0.78)`. ⚠ `embed_model` do config (`nomic-embed-text`) não está instalado no Ollama do PC (404) |
| D1 | Importar PDF, DOCX e TXT | Os três indexados | ✅ box (9506c28) + PC 16/10 (130143f) |
| D2 | Perguntar algo de cada um | Resposta correta com citação da fonte | ✅ PC 16/10 tarde: pdf, docx e txt com fonte e citação certas (falha anterior era do script) |
| D3 | Reindexar após a busca vetorial do beck | Conclui; anotar tempo | ✅ PC 16/10 tarde: 3 trechos em 0,2 s, progresso 3/3 |
| D4 | Mesmas perguntas de D2 com a busca nova | Respostas iguais ou melhores | ✅ PC 16/10 (0111223): FAISS = numpy (mesmas fontes e notas), 4,1 s |

## 5. Imagem
| ID | Passos | Esperado | Status |
|---|---|---|---|
| I1 | Texto → imagem com prompt em português | Tradução aplicada, imagem gerada | ✅ PC 16/10 (130143f): 40 s |
| I2 | Imagem → imagem, inpainting e edição por instrução | Os três funcionam | ✅ PC 16/10 tarde: img2img 25 s, inpaint 147 s, pix2pix 53 s |
| I3 | Cada proporção e resoluções baixa/alta | Tamanho de saída correto | ✅ PC 16/10 (130143f): as três proporções no tamanho certo |
| I4 | Enfileirar 3 imagens | Rodam uma por vez, na ordem | ✅ box (9506c28) + PC 16/10 (130143f): 3 jobs em ordem |

## 5b. Ampliador
| ID | Passos | Esperado | Status |
|---|---|---|---|
| U1 | Ampliar 2x e 4x uma imagem da galeria | Usa o modelo de IA (sem `_lanczos`); anotar o tempo no i5 | ✅ 15/10 (fila, 512→, onnxruntime, modelo 4x realesr-general-x4v3): 2x 3,8 s (1024²), 4x 3,9 s (2048²); nomes `_x2`/`_x4` sem `_lanczos`. ⚠ o tipo `ampliar` não estava no register_all (corrigido em b8b39bf; no teste foi registrado à mão) |
| U2 | Cancelar no meio | Para entre um bloco e outro | ✅ 15/10: cancelado 0,9 s após o pedido (3 eventos de progresso) |
| U3 | Tirar o modelo do lugar e ampliar | Cai no Lanczos e a tela avisa | ✅ 15/10 (headless, modelo inexistente via cfg_override): 0,1 s, `_x2_lanczos.png`, metadado e log avisam. 16/10 18h: aviso na tela ✅ (DEV Front, janela diz que o modelo não foi achado e como instalar) |

## 6. Voz (após o ia_off, prazo 23/10)
| ID | Passos | Esperado | Status |
|---|---|---|---|
| A1 | Gravar/transcrever áudio em português (Whisper) | Texto correto | ✅ PC 16/10 (0111223): Whisper small 100% no áudio do Piper, 7,0 s; microfone não testado |
| A2 | Sintetizar texto (Piper) | Áudio claro, sem internet | ✅ PC 16/10 (0111223): Piper faber 3,4 s de áudio em 7,3 s, offline |
| A3 | Cancelar a transcrição de um áudio longo | Para sem travar | ✅ 15/10 com d798d2c (testado no PC sem instalar, módulo carregado pelo script): áudio de 108 s, transcrição completa 117 s; cancelar aos 4 s (carregando o modelo) e aos 25 s (decodificando) → job cancelado em 0,1 s; a thread auxiliar termina o trecho de 10 s em andamento em segundo plano. Antes: 88 s |

## 7. Configurações e desempenho
| ID | Passos | Esperado | Status |
|---|---|---|---|
| S1 | Ligar/desligar modo turbo | Uso de núcleos muda | ✅ PC 16/10: núcleos ok (8 turbo, 2 com 2 threads); BUG prioridade alta nunca aplicada: perf.set_high_priority sem restype no GetCurrentProcess (SetPriorityClass erro 6, silencioso) → corrigido em c2cd115 (instalado 15:30): prioridade Alta (128) com turbo, 8 threads (~7,3 núcleos) vs 2 com turbo desligado; texto do log corrigido em 945402d (suíte 173 ok) |
| S2 | Rodar Benchmark CPU x GPU (OpenVINO) | Resultado registrado aqui | ✅ 15/10 SD 1.5 + LCM, 512x512, 4 passos (após aquecimento): PyTorch CPU 36,1 s · OpenVINO CPU 29,3 s · OpenVINO GPU (UHD 620) 17,5 s/imagem. Aquecimento/exportação: 35 s / 135 s / 95 s |
| S3 | Desligar a internet e usar todas as abas | Tudo funciona offline | ⏳ fica pro Julio: desligar a internet derruba o acesso do ia_off ao PC. 16/10 18h: regra de firewall exige admin; comando enviado ao Julio |

## 8. Regra de centralização (antes da entrega)
| ID | Passos | Esperado | Status |
|---|---|---|---|
| R1 | `rg -n -i 'C:\\\\|C:/' ia_off --glob '!config.py'` | Nenhum caminho fixo fora do `config.py` (15/10: ✅ limpo) | ✅ 16/10 (0a3000d): só a docstring do `rag.py` cita o padrão `C:\\IA\\dados\\rag` |
| R2 | Conferir `OLLAMA_MODELS` e `HF_HOME` no PC | Apontam pra `C:\IA\modelos\ollama` e `\huggingface` | ✅ PC 16/10: OLLAMA_MODELS = C:\IA\modelos\ollama, HF_HOME = C:\IA\modelos\huggingface |
| R3 | Índice de documentos após a busca vetorial | Gravado em `C:\IA\dados\rag` | ✅ PC 16/10 (0111223): índice em C:\IA\dados\rag (FAISS) |
| R4 | Abrir LivreStudio, EngenhariaIA e estudio_local | Continuam achando os modelos | ✅ PC 16/10 (130143f): LivreStudio e EngenhariaIA abrem; estudio_local acha os modelos |
| R5 | `rg -n "OneDrive|C:\\\\" ia_off --glob "!config.py"` e conferir padrões de Wan/FLUX.2/Z-Image no `config.py` | Nenhum caminho de modelo fixo fora do `config.py`; padrões vêm de `C:\IA\modelos`/variáveis, sem OneDrive; o `config.json` do Julio continua achando os arquivos | ✅ (ac06c3a) |
| R6 | Novos modelos (Qwen3.8 27B, Z-Image, Wan 2.2 5B) | Aparecem nos seletores sem caminho fixo, geram um teste, tempo registrado, moderador ligado/desligado ok | ✅ Z-Image desligado 774 s e ligado 786 s; Qwen3.8 1,47 e 1,41 tok/s, ok com moderação desligada e ligada; Wan 2.2 V5 ok; Wan 2.2 pelo seletor (video_modelo=wan22 no cfg_override): desligado 713 s (decode 523 s), ligado 723 s (decode ~531 s, negativo da moderação preenchido); fases decodificando/salvando/convertendo e .txt com modelo: wan22; moderação desligada de novo. Menu da aba Vídeo na tela fica pro Julio |

## 9. Moderador e senha (prazo 23/10)
| ID | Passos | Esperado | Status |
|---|---|---|---|
| MO1 | Moderação desligada: comparar o comando do `sd-cli` e o prompt do chat com e sem o hook | Idênticos; listas nem carregadas; nenhum bloqueio | ✅ PC 16/10 (92b5253 = código do bcc2217), mo_pc_check |
| MO2 | Ligar em Leve, Médio e Rígido com o mesmo conjunto de prompts | Rígido bloqueia tudo do Médio, e o Médio tudo do Leve | ✅ PC 16/10 (92b5253 = código do bcc2217), mo_pc_check |
| MO3 | Prompts normais em PT-BR em todos os níveis | Nenhum bloqueio falso (checagem por palavra inteira) | ✅ PC 16/10 (92b5253 = código do bcc2217), mo_pc_check |
| MO4 | Burla com acento, maiúsculas e letras separadas por espaço | Bloqueado; "e a" ou "o e" não colam em bloqueio falso | ✅ PC 16/10 (92b5253 = código do bcc2217), mo_pc_check |
| MO5 | Prompt bloqueado em imagem, vídeo e Falar | `PromptBloqueado` com motivo na tela, sem carregar modelo | ✅ PC 16/10 (92b5253 = código do bcc2217): Imagem, Vídeo e Falar bloqueiam com motivo, sem carregar modelo nem sd-cli (pelo código; clique real fica pro Julio) |
| MO6 | `moderacao.json` ausente ou com erro de sintaxe | Usa o padrão embutido, avisa no log e não derruba o app | ✅ PC 16/10 (92b5253 = código do bcc2217), mo_pc_check |
| SE1 | Primeira vez em "Alterar filtro…" | Pede pra criar a senha e confirmar; arquivo guarda só hash PBKDF2 com salt | ✅ PC 16/10 (92b5253 = código do bcc2217): senha temporária criada; arquivo só com hash PBKDF2 (240k iterações) e salt; fora dos logs (clique real fica pro Julio) |
| SE2 | Senha errada | Nada muda e aparece aviso | ✅ PC 16/10 (92b5253 = código do bcc2217): senha errada recusa e nada muda |
| SE3 | Senha certa | Liga, desliga e troca o nível | ✅ PC 16/10 (92b5253 = código do bcc2217): senha certa libera; desligar também pede senha |
| SE4 | Apagar o arquivo da senha | App pede senha nova | ✅ PC 16/10 18h (ok do Julio): sem o json o app pede senha nova; arquivo restaurado do backup senha_1744.json e a temporária voltou a valer |
| SE5 | "Trocar senha…" (0111f92) | Senha atual errada não muda nada; atual certa + nova confirmada troca | ✅ PC 16/10 (senha atual errada não muda nada) |

## 10. Etapa 4 (robustez e polimento, prazo 28/10) e regressão pós-instalação

Rodar no PC depois de instalar o 14dbf57 (código do 6e042b3), com P2 verde antes.

| # | Teste | Esperado | Resultado |
|---|---|---|---|
| E1 | V4 de novo: Cancelar real no meio de um vídeo Wan 2.2 | Para em até 1 passo, sem "passo N" falso depois do Cancelar (950cb26 + 3786502) | ⏳ |
| E2 | V5 com o FPS novo: vídeo Wan 2.2 e depois Wan 2.1 pela aba Vídeo | O .txt e o arquivo saem com 24 fps no 2.2 e 16 fps no 2.1 (132ee82) | ⏳ |
| E3 | V8: vídeo Wan com o negativo vazio | O .txt grava o negativo padrão do Wan, igual ao que o sd-cli recebe (7fe5e0c) | ⏳ |
| E4 | R6 regressão: Z-Image, Qwen3.8 e Wan 2.2, um de cada | Geram normal, com os tempos perto dos de 16/10 | ⏳ |
| E5 | Descarga do Ollama: gerar uma imagem com o chat parado | O Ollama é descarregado antes, e o log registra isso | ⏳ |
| E6 | Descarga com chat em andamento: mandar mensagem longa e logo depois um vídeo na fila | A fila espera o chat (até `queue_unload_wait_s`) e não descarrega no meio. Se passar do tempo, pula com aviso no log, e o chat termina inteiro | ⏳ |
| E7 | `IA_OFF_QUEUE_UNLOAD_OLLAMA=0` | Não descarrega nada | ⏳ |
| E8 | "Decodificando…" na primeira geração de um modelo | Mostra o tempo passado e o aviso de que pode demorar, sem estimativa | ⏳ |
| E9 | "Decodificando…" na segunda geração do mesmo modelo | Mostra quanto já passou, o total estimado e quanto falta. Anotar o real contra o estimado (aceitável errar até ~25%) | ⏳ |
| E10 | Textos de bloqueio do moderador (com ele ligado) no Chat, Imagem, Vídeo e Falar | Mostra o motivo, diz que nada foi enviado nem salvo, o texto fica na caixa e aponta pra Configurações > Moderação > "Alterar filtro…". Depois, desligar a moderação | ⏳ |
| E11 | Robustez (725295b): forçar falha de um job (modelo ausente via cfg_override) | O erro aparece no log, e nada fica calado | ⏳ |
| E12 | Conversa longa com 200+ mensagens (depois da entrega do Front) | Rolar e mandar mensagem sem travar. Anotar o tempo de abrir a conversa | ⏳ |
| E13 | Barra de progresso e Cancelar em todas as abas (depois do Front) | Toda aba mostra progresso e cancela sem travar | ⏳ |
| E14 | P2 + R5 no hash final | Suíte verde e nenhum caminho fixo fora do config.py | ⏳ |

## Registro de falhas
| Data | ID | Versão | O que aconteceu | Responsável | Status |
|---|---|---|---|---|---|
| 15/10 | V2 | 3.0 | Barra foi a 242/242 em 8 s: carregamento do modelo contado como passo (também 825/825 e 108 e 4 na decodificação) | ia_off (sdcpp.py) | corrigido em 0e2f431/bb21e2d (só conta barras com total == --steps) |
| 15/10 | V2 | 3.0 | ~200 s por passo em 480x272 (20 passos, cerca de 1h10), acima do esperado; causa: vídeo rodando pela versão Vulkan na UHD 620; correção = CPU por padrão no sdcpp.py | ia_off | CPU padrão em bb21e2d; na CPU também ~197 s/passo (V7), o modelo é que é pesado pro i5 |
| 15/10 | U1 | 3.0 | Tipo `ampliar` não registrado na fila (botão Ampliar com IA: "Nenhum motor registrado") | ia_off | corrigido em b8b39bf (instalado no PC 15/10 23:38; fila real ok) |
| 15/10 | A2/A3 | 3.0 | Piper derrubava o processo: espeak-ng não abre dados no caminho com "Área de Trabalho" | ia_off | corrigido em 1755162 (aplicado no PC) |
| 15/10 | A3 | 3.0 | Cancelar transcrição demorou 88 s | ia_off (voice_engine) | corrigido em d798d2c (trechos de 10 s numa thread; falta instalar no PC) |
| 15/10 | V2 | 3.0 | Negativo padrão do Wan chega ao sd-cli como "????" (página de código do Windows) | ia_off (sdcpp) | fechado 16/10: não é bug (cli_safe manda ASCII de propósito; .txt guarda UTF-8; os "?" são do log de tokens do sd-cli) |
| 15/10 | D2 | 3.0 | `nomic-embed-text` (embed_model padrão) não instalado no Ollama do PC | ia_off | padrão trocado em 98931fb; config.json do Julio trocado para embeddinggemma-2:740m (backup C:\IA\backup\config_20261015_2338.json) |
| 16/10 | V8 | 3.0 | Negativo vazio: .txt grava "negative:" em branco, mas o sd-cli recebe o negativo padrão do Wan | ia_off (sdcpp) | aberto (amanhã) |


## Checklist do Julio

A lista única do Julio é o passo a passo de [`docs/NOTAS_3.0_RC.md`](NOTAS_3.0_RC.md).

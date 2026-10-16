# Roteiro de testes — IA Off 3.0 (responsável: sub2)

Formato: cada teste tem ID, passos, resultado esperado e status (✅ passou / ❌ falhou / ⏳ pendente).
Ambiente: PC do Julio (i5-8365U, 32 GB, UHD 620), com a instalação feita pelo ia_off. Testes automáticos em `tests/` rodam na `ia_off_v3`.

## 0. Pré-teste
| ID | Passos | Esperado | Status |
|---|---|---|---|
| P1 | Abrir pelo atalho "IA Off" | Janela abre em < 15 s, 6 abas visíveis | ⏳ |
| P2 | Rodar `pytest tests/` na ia_off_v3, num ambiente limpo só com o requirements.txt | Todos passam | ✅ 15/10, commit 2d73849: 88 ok e 1 pulado |

## 1. Vídeo (Wan 2.1) — prioridade, testar primeiro
| ID | Passos | Esperado | Status |
|---|---|---|---|
| V1 | Abrir a aba Vídeo e carregar o modelo | Não fecha nem trava (correção 2.3.1) | ✅ 15/10 no PC (ia_off) |
| V2 | Gerar vídeo curto em baixa resolução | Termina, arquivo salvo e reproduzível | ✅ 15/10 (fila + engines_registry, headless): 480x272, 17 quadros, 20 passos → `20261015_205851_wan_1107368692.mp4`, 32 784 B, ffprobe ok (h264 480x272, 16 fps, 17 quadros, 1,06 s). TEMPO_TOTAL 8124 s = ~45 min Vulkan (morta em 11/20) + ~90 min na CPU (recaída automática) |
| V3 | Durante a geração, trocar de aba e mexer na janela | Interface continua respondendo | ✅ 15/10 offscreen no PC: vídeo (sd.cpp falso) na fila trocando de aba a cada 100 ms: 23–29 trocas, maior pausa da UI 0,13 s, sinais na thread principal; repetido após aplicar 6b581cc. smoke_gui ✅. stress_gui ❌ no PC (video_lines=0: o FakeEngine de imagem usa sleep(0.0005) que no Windows dura ~15 ms, o vídeo não chega a rodar antes do fechamento; problema do teste, não do app) → com 4cfdaf7 instalado: stress_gui ✅ e smoke_gui ✅ no PC (15/10 23:39) |
| V4 | Cancelar no meio (após a fila do beck) | Para em até 1 passo, sem travar | ⏳ |
| V5 | Barra mostra passo X de N e ETA (após DEV Front) | Números avançam e batem com o fim | ⏳ |
| V7 | Rodar o mesmo vídeo do V2 na CPU e na Vulkan | CPU mais rápida; CPU é o padrão; anotar os dois tempos | ✅ 15/10 (mesmo vídeo do V2). Vulkan (UHD 620): ~200 s/passo (11/20 em ~2535 s; carga ~9 min). CPU (-t 4): carga+texto ~9 min, amostragem ~65 min (~170–245 s/passo, média ~197 s), decodificação VAE ~16 min, total ~90 min (5405 s). CPU ≈ Vulkan na amostragem, não mais rápida; CPU fica padrão (bb21e2d) por usar pouca GPU/RAM compartilhada |
| V8 | Vídeo curto real depois do `076a2d5` (negativo em inglês, prompt ASCII) | Log mostra o negativo legível; vídeo sem os defeitos que o negativo evita | ⏳ |
| V6 | Um teste longo na resolução padrão (no final) | Termina sem erro; anotar tempo | ⏳ |

## 2. Chat (Ollama)
| ID | Passos | Esperado | Status |
|---|---|---|---|
| C1 | Enviar pergunta curta | Resposta aparece enquanto é gerada | ⏳ |
| C2 | Conversa longa (40+ mensagens) | Sem lentidão perceptível (correção do Front) | ⏳ |
| C3 | Fechar e reabrir o app | Histórico preservado | ⏳ |
| C4 | Importar um GGUF | Modelo aparece e responde | ⏳ |

## 3. Trocas de modelo (prazo 20/10)
| ID | Passos | Esperado | Status |
|---|---|---|---|
| M1 | Selecionar Qwen3-30B-A3B e perguntar | Responde; anotar tempo do 1º token e tokens/s | ⏳ |
| M2 | Trocar 30B → modelo pequeno → 30B | Sem erro, RAM liberada (ver Gerenciador de Tarefas) | ⏳ |
| M3 | Trocar SD 1.5 ↔ FLUX.2 Klein na aba Imagem | Ambos geram; sem estouro de RAM | ⏳ |
| M4 | Chat com 30B carregado + gerar imagem | Não trava; anotar uso de RAM | ⏳ |

## 4. Documentos
| ID | Passos | Esperado | Status |
|---|---|---|---|
| D0 | Abrir a 3.0 pela 1ª vez com os documentos da 2.x | Documentos antigos migrados e aparecendo (commit 6ee483e) | ✅ 15/10 sem dados: `%APPDATA%\IA_Off_v1\rag` não tem meta.json (0 documentos) e `C:\IA\dados\rag` vazio → cópia/migração é no-op (0 trechos). Consulta com índice temporário + Ollama `embeddinggemma-2:740m`: 0,07 s, citou `[1] manual_teste.txt (score 0.78)`. ⚠ `embed_model` do config (`nomic-embed-text`) não está instalado no Ollama do PC (404) |
| D1 | Importar PDF, DOCX e TXT | Os três indexados | ⏳ |
| D2 | Perguntar algo de cada um | Resposta correta com citação da fonte | ⏳ |
| D3 | Reindexar após a busca vetorial do beck | Conclui; anotar tempo | ⏳ |
| D4 | Mesmas perguntas de D2 com a busca nova | Respostas iguais ou melhores | ⏳ |

## 5. Imagem
| ID | Passos | Esperado | Status |
|---|---|---|---|
| I1 | Texto → imagem com prompt em português | Tradução aplicada, imagem gerada | ⏳ |
| I2 | Imagem → imagem, inpainting e edição por instrução | Os três funcionam | ⏳ |
| I3 | Cada proporção e resoluções baixa/alta | Tamanho de saída correto | ⏳ |
| I4 | Enfileirar 3 imagens | Rodam uma por vez, na ordem | ⏳ |

## 5b. Ampliador
| ID | Passos | Esperado | Status |
|---|---|---|---|
| U1 | Ampliar 2x e 4x uma imagem da galeria | Usa o modelo de IA (sem `_lanczos`); anotar o tempo no i5 | ✅ 15/10 (fila, 512→, onnxruntime, modelo 4x realesr-general-x4v3): 2x 3,8 s (1024²), 4x 3,9 s (2048²); nomes `_x2`/`_x4` sem `_lanczos`. ⚠ o tipo `ampliar` não estava no register_all (corrigido em b8b39bf; no teste foi registrado à mão) |
| U2 | Cancelar no meio | Para entre um bloco e outro | ✅ 15/10: cancelado 0,9 s após o pedido (3 eventos de progresso) |
| U3 | Tirar o modelo do lugar e ampliar | Cai no Lanczos e a tela avisa | ✅ 15/10 (headless, modelo inexistente via cfg_override): 0,1 s, `_x2_lanczos.png`, metadado e log avisam. Aviso na tela não verificado |

## 6. Voz (após o ia_off, prazo 23/10)
| ID | Passos | Esperado | Status |
|---|---|---|---|
| A1 | Gravar/transcrever áudio em português (Whisper) | Texto correto | ⏳ |
| A2 | Sintetizar texto (Piper) | Áudio claro, sem internet | ⏳ |
| A3 | Cancelar a transcrição de um áudio longo | Para sem travar | ✅ 15/10 com d798d2c (testado no PC sem instalar, módulo carregado pelo script): áudio de 108 s, transcrição completa 117 s; cancelar aos 4 s (carregando o modelo) e aos 25 s (decodificando) → job cancelado em 0,1 s; a thread auxiliar termina o trecho de 10 s em andamento em segundo plano. Antes: 88 s |

## 7. Configurações e desempenho
| ID | Passos | Esperado | Status |
|---|---|---|---|
| S1 | Ligar/desligar modo turbo | Uso de núcleos muda | ⏳ |
| S2 | Rodar Benchmark CPU x GPU (OpenVINO) | Resultado registrado aqui | ✅ 15/10 SD 1.5 + LCM, 512x512, 4 passos (após aquecimento): PyTorch CPU 36,1 s · OpenVINO CPU 29,3 s · OpenVINO GPU (UHD 620) 17,5 s/imagem. Aquecimento/exportação: 35 s / 135 s / 95 s |
| S3 | Desligar a internet e usar todas as abas | Tudo funciona offline | ⏳ |

## 8. Regra de centralização (antes da entrega)
| ID | Passos | Esperado | Status |
|---|---|---|---|
| R1 | `rg -n -i 'C:\\\\|C:/' ia_off --glob '!config.py'` | Nenhum caminho fixo fora do `config.py` (15/10: ✅ limpo) | ⏳ |
| R2 | Conferir `OLLAMA_MODELS` e `HF_HOME` no PC | Apontam pra `C:\IA\modelos\ollama` e `\huggingface` | ⏳ |
| R3 | Índice de documentos após a busca vetorial | Gravado em `C:\IA\dados\rag` | ⏳ |
| R4 | Abrir LivreStudio, EngenhariaIA e estudio_local | Continuam achando os modelos | ⏳ |
| R5 | `rg -n "OneDrive|C:\\\\" ia_off --glob "!config.py"` e conferir padrões de Wan/FLUX.2/Z-Image no `config.py` | Nenhum caminho de modelo fixo fora do `config.py`; padrões vêm de `C:\IA\modelos`/variáveis, sem OneDrive; o `config.json` do Julio continua achando os arquivos | ⏳ |
| R6 | Novos modelos (Qwen3.8 27B, Z-Image, Wan 2.2 5B) | Aparecem nos seletores sem caminho fixo, geram um teste, tempo registrado, moderador ligado/desligado ok | ⏳ |

## 9. Moderador e senha (prazo 23/10)
| ID | Passos | Esperado | Status |
|---|---|---|---|
| MO1 | Moderação desligada: comparar o comando do `sd-cli` e o prompt do chat com e sem o hook | Idênticos; listas nem carregadas; nenhum bloqueio | ⏳ |
| MO2 | Ligar em Leve, Médio e Rígido com o mesmo conjunto de prompts | Rígido bloqueia tudo do Médio, e o Médio tudo do Leve | ⏳ |
| MO3 | Prompts normais em PT-BR em todos os níveis | Nenhum bloqueio falso (checagem por palavra inteira) | ⏳ |
| MO4 | Burla com acento, maiúsculas e letras separadas por espaço | Bloqueado; "e a" ou "o e" não colam em bloqueio falso | ⏳ |
| MO5 | Prompt bloqueado em imagem, vídeo e Falar | `PromptBloqueado` com motivo na tela, sem carregar modelo | ⏳ |
| MO6 | `moderacao.json` ausente ou com erro de sintaxe | Usa o padrão embutido, avisa no log e não derruba o app | ⏳ |
| SE1 | Primeira vez em "Alterar filtro…" | Pede pra criar a senha e confirmar; arquivo guarda só hash PBKDF2 com salt | ⏳ |
| SE2 | Senha errada | Nada muda e aparece aviso | ⏳ |
| SE3 | Senha certa | Liga, desliga e troca o nível | ⏳ |
| SE4 | Apagar o arquivo da senha | App pede senha nova | ⏳ |

## Registro de falhas
| Data | ID | Versão | O que aconteceu | Responsável | Status |
|---|---|---|---|---|---|
| 15/10 | V2 | 3.0 | Barra foi a 242/242 em 8 s: carregamento do modelo contado como passo (também 825/825 e 108 e 4 na decodificação) | ia_off (sdcpp.py) | corrigido em 0e2f431/bb21e2d (só conta barras com total == --steps) |
| 15/10 | V2 | 3.0 | ~200 s por passo em 480x272 (20 passos, cerca de 1h10), acima do esperado; causa: vídeo rodando pela versão Vulkan na UHD 620; correção = CPU por padrão no sdcpp.py | ia_off | CPU padrão em bb21e2d; na CPU também ~197 s/passo (V7), o modelo é que é pesado pro i5 |
| 15/10 | U1 | 3.0 | Tipo `ampliar` não registrado na fila (botão Ampliar com IA: "Nenhum motor registrado") | ia_off | corrigido em b8b39bf (instalado no PC 15/10 23:38; fila real ok) |
| 15/10 | A2/A3 | 3.0 | Piper derrubava o processo: espeak-ng não abre dados no caminho com "Área de Trabalho" | ia_off | corrigido em 1755162 (aplicado no PC) |
| 15/10 | A3 | 3.0 | Cancelar transcrição demorou 88 s | ia_off (voice_engine) | corrigido em d798d2c (trechos de 10 s numa thread; falta instalar no PC) |
| 15/10 | V2 | 3.0 | Negativo padrão do Wan chega ao sd-cli como "????" (página de código do Windows) | ia_off (sdcpp) | aberto |
| 15/10 | D2 | 3.0 | `nomic-embed-text` (embed_model padrão) não instalado no Ollama do PC | ia_off | padrão trocado em 98931fb; config.json do Julio trocado para embeddinggemma-2:740m (backup C:\IA\backup\config_20261015_2338.json) |

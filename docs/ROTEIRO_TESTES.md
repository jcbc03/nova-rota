# Roteiro de testes — IA Off 3.0 (responsável: sub2)

Formato: cada teste tem ID, passos, resultado esperado e status (✅ passou / ❌ falhou / ⏳ pendente).
Ambiente: PC do Julio (i5-8365U, 32 GB, UHD 620), com a instalação feita pelo ia_off. Testes automáticos em `tests/` rodam na `ia_off_v3`.

## 0. Pré-teste
| ID | Passos | Esperado | Status |
|---|---|---|---|
| P1 | Abrir pelo atalho "IA Off" | Janela abre em < 15 s, 6 abas visíveis | ⏳ |
| P2 | Rodar `pytest tests/` na ia_off_v3 | Todos passam | ⏳ |

## 1. Vídeo (Wan 2.1) — prioridade, testar primeiro
| ID | Passos | Esperado | Status |
|---|---|---|---|
| V1 | Abrir a aba Vídeo e carregar o modelo | Não fecha nem trava (correção 2.3.1) | ⏳ |
| V2 | Gerar vídeo curto em baixa resolução | Termina, arquivo salvo e reproduzível | ⏳ |
| V3 | Durante a geração, trocar de aba e mexer na janela | Interface continua respondendo | ⏳ |
| V4 | Cancelar no meio (após a fila do beck) | Para em até 1 passo, sem travar | ⏳ |
| V5 | Barra mostra passo X de N e ETA (após DEV Front) | Números avançam e batem com o fim | ⏳ |
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

## 6. Voz (após o ia_off, prazo 23/10)
| ID | Passos | Esperado | Status |
|---|---|---|---|
| A1 | Gravar/transcrever áudio em português (Whisper) | Texto correto | ⏳ |
| A2 | Sintetizar texto (Piper) | Áudio claro, sem internet | ⏳ |

## 7. Configurações e desempenho
| ID | Passos | Esperado | Status |
|---|---|---|---|
| S1 | Ligar/desligar modo turbo | Uso de núcleos muda | ⏳ |
| S2 | Rodar Benchmark CPU x GPU (OpenVINO) | Resultado registrado aqui | ⏳ |
| S3 | Desligar a internet e usar todas as abas | Tudo funciona offline | ⏳ |

## 8. Regra de centralização (antes da entrega)
| ID | Passos | Esperado | Status |
|---|---|---|---|
| R1 | `rg -n -i 'C:\\\\|C:/' ia_off --glob '!config.py'` | Nenhum caminho fixo fora do `config.py` (15/10: ✅ limpo) | ⏳ |
| R2 | Conferir `OLLAMA_MODELS` e `HF_HOME` no PC | Apontam pra `C:\IA\modelos\ollama` e `\huggingface` | ⏳ |
| R3 | Índice de documentos após a busca vetorial | Gravado em `C:\IA\dados\rag` | ⏳ |
| R4 | Abrir LivreStudio, EngenhariaIA e estudio_local | Continuam achando os modelos | ⏳ |

## Registro de falhas
| Data | ID | Versão | O que aconteceu | Responsável | Status |
|---|---|---|---|---|---|

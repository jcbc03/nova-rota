# IA Off 3.0: versão candidata (16/10/2026)

Versão no PC: `d040ea5`, instalada em 22/10 às 11h48 (P2 verde 2x, 236 ok e 3 skipped). Backup em `C:\IA\backup\v3_20261022_114804`. Antes: `fb8b04d`, instalada às 11h02 (P2 231 ok e 3 skipped), backup em `C:\IA\backup\v3_20261022_110249`; `48dd94e`, instalada às 9h06 (P2 226 ok e 3 skipped), backup em `C:\IA\backup\v3_20261022_090636`; `e7bb291`, instalada às 6h38 (P2 219 ok e 3 skipped), backup em `C:\IA\backup\v3_20261022_063817`; `4641034`, instalada às 6h19 (P2 212 ok e 3 skipped), backup em `C:\IA\backup\v3_20261022_061853`; `97d1539`, instalada em 22/10 às 6h14, backup em `C:\IA\backup\v3_20261022_061414` (medida descartada, substituído pelo `4641034`); `d7e8c8b`, instalada às 5h41 (P2 verde, 206 ok e 3 skipped; SHA256 de 4 arquivos conferido, incluindo `ollama_client.py` e `media_tabs.py`), backup em `C:\IA\backup\v3_20261022_054120`; `5818bfc`, instalada em 22/10 às 4h48, backup em `C:\IA\backup\v3_20261022_044800`. A primeira candidata foi o `4c6d743` (16/10). Backup da versão candidata em `C:\IA\backup\rc_v3.0_4c6d743_20261016` (com `LEIA_rc.txt`). O código no PC é igual ao do `af66cc4` nos 56 arquivos, e o app usa as bibliotecas do `.venv`. Entrega prevista: 30/10/2026. Detalhes e commits em `docs/CHANGELOG.md`.

## O que tem de novo
- **Moderador opcional**, desligado por padrão. Desligado, não restringe nada. Ligado, tem três níveis (leve, médio e rígido), e mudar o filtro exige senha. A senha fica guardada só como hash.
- **Chat com o Qwen3.8 27B** (`qwen3.8-27b-aggressive`): ~1,4 tok/s, primeiro texto em ~1 min.
- **Imagem com Z-Image Turbo**: ~13 min a 512 px.
- **Vídeo com Wan 2.2 5B**, escolhido no seletor Wan 2.1/2.2 da aba Vídeo, a 24 fps.
- **Fases depois do último passo** (Decodificando, Salvando e Convertendo) na barra e no log, em vídeo, FLUX.2 e Z-Image.

## O que foi corrigido
- O seletor do chat não lista mais modelos de embedding (o erro 400).
- Nenhum caminho fixo: os modelos ficam em `C:\IA\modelos`.
- `vcomp140.dll` encontrada pelo gerador de imagem e vídeo.
- Não aparece mais um passo falso depois de Cancelar.
- A prioridade alta do modo turbo agora funciona no Windows 64-bit.

## Novo desde 16/10 (instalado em 21 e 22/10)
- FPS da aba Vídeo segue o modelo: 24 no Wan 2.2 e 16 no 2.1. Antes a tela mandava sempre 16 (`132ee82`).
- Erros que passavam calados na fila, no moderador e no RAG agora vão pro log, sem mudar o comportamento (`725295b`, suíte 178 ok e 3 skips).
- Negativo vazio do Wan gravado certo no .txt (`7fe5e0c`).
- Ollama descarregado antes de tarefas pesadas, sem nunca cortar um chat em andamento (`33a0518`).
- "Decodificando…" com tempo decorrido e estimativa, e mensagens de bloqueio mais claras (`6e042b3`).
- Conversa longa mais leve: com 250 mensagens a tela não pesa mais, e o histórico cabe no contexto do modelo (`5278092`).
- Botão Parar na pergunta aos Documentos (`3b72007`).
- Mensagem de bloqueio sem nome técnico e dizendo que nada foi gerado nem salvo (`17a1827`, `4692dc5`).
- Cancelar revisado em todas as abas (`6b9feba`), incluindo a Voz (`b16b394`, `30a9629`).
- **E13 passou no `70ea8b5`** (22/10): Voz cancela em 251 ms (barra 4/40, job "cancelada"), Imagem em 1,1 s, Vídeo em 256 ms e o Parar do Chat em 477 ms. O detalhe cosmético do "frase(s)" na transcrição foi fechado em `964be01` (agora "s de áudio") e instalado no `5818bfc`; conferido no PC no `5818bfc`: a barra mostra "4 de 40 s de áudio", e todas as abas cancelam.
- **E1 aprovado** (22/10): Cancelar no Wan 2.2 em 0,82 s, sem passo falso.
- **E4 aprovado, ressalva só do 1º token** (`5818bfc`, tudo carregado, nada acima de 15% vs. 16/10): Qwen3.8 1,42 tok/s (igual), 1º token 97 s (16/10: 52 a 64 s); Z-Image 875 s (+7 a 13%), difusão 86,5 s/passo, carga 131 s; Wan 2.2 480×272 em 831 s com 4 passos (mínimo do campo; 16/10 usou 2), ~+7% ajustado, decode +2%.
- **E2 FECHADO**: Wan 2.1 do E3 a 16 fps (.txt e arquivo, ffprobe) e Wan 2.2 a 24 fps.
- **E14 PASSOU no `5818bfc`** (hash final): P2 limpa 2x (203 ok, 3 skipped), R5 limpo (só docstring em `rag.py`), app abre sem erro no PC.
- **Falhas abertas**: (1) Wan decode (Front, `5b88ac2` + teste `e1507cf`): **PASSOU** no PC no `d7e8c8b` em 256×256, 5 quadros, 4 passos: "Passo 2/4" → "Decodificando…" até 2 min 01 s, sem voltar a "Passo N". Ressalva: a fila não mandou passo durante o decode nesta rodada, então o caso exato (480×272) não foi exercitado. Aceito pelo Gerente: o caso exato está coberto pelo teste `e1507cf`, e a rodada em 480×272 não é necessária agora. (2) Parar do Chat (beck): **✅ ACEITO** pelo Gerente no `4641034`. Correções `20de42f` (post e leitura numa thread, checa o Parar a cada 0,05 s) e `a63acce` (fecha o socket TCP na hora, e o Ollama para de gerar). Medido no PC no `4641034` com qwen3.8-27b-aggressive: antes do 1º pedaço 1036/1024/1025 ms (era ~5 s no `d7e8c8b`); no meio da resposta 79/89/89 ms; nenhum pedaço depois do clique, sem diálogo. O Ollama para de verdade: o `ollama ps` mostra só o modelo carregado ~10 s depois, e o 2º Enviar sai normal (1º pedaço em 38-41 s, total 43-45 s). Ressalvas: leva ~1 s antes do 1º pedaço (meta 0,5 s); um ajuste possível do beck (ex.: timeout do join) pode vir depois pelo fluxo normal e não bloqueia a entrega. A CPU foi medida no processo errado (ollama em vez de llama-server; llama-server em 0% ao final). Com isso, a parte de testes da equipe está fechada; falta só o que é do Julio. Roteiro em `753b297`.
- **Parar do Chat ✅ sem ressalva no `e7bb291`** (22/10): a causa do ~1 s era o `localhost` no Windows tentar `::1` (IPv6) antes do IPv4, onde o Ollama escuta; o Winsock perdia ~1 s em todo envio. Fix do beck `e39bba5` (+ `.codesight` `e7bb291`): `ollama_client.py` troca `localhost` por `127.0.0.1`. Medido pelo ia_off com qwen3.8-27b-aggressive: Parar antes do 1º pedaço 33/34/43 ms (até o worker terminar); `llama-server` 0,00-0,02 s de CPU em 3 s ~10 s depois (Ollama parou); nenhum pedaço depois do clique, sem diálogo; 2º Enviar com 1º pedaço em 34,2/45,4/34,1 s; envio normal com modelo quente, 1º pedaço em 20,7/24,1/34,2 s. SHA256 do `ollama_client.py` e hashes do %APPDATA% conferem; nada baixado nem apagado. Saída em `C:\IA\tmp\stope7_out.txt`. Roteiro atualizado pelo sub2 em `2748ccb`.
- **Última rodada da equipe no PC: `48dd94e` ✅** (22/10, 9h06). Inclui a guarda do Front (`c5ae85c`, teste `1cb444f` + `0f2c04a`) e a robustez do beck (`8787d3a`: rag.py e job_queue.py, só casos de erro). Checagem do ia_off com qwen3.8-27b-aggressive, Parar até o worker terminar: antes do 1º pedaço 43 ms; no meio 73 ms; durante o carregamento do modelo 32 ms (`ollama ps` vazio e sem `llama-server` ~10 s depois, carga abandonada). Nenhum pedaço depois do clique, sem diálogo. Envio normal: 1º pedaço em 40,4 s. SHA256 de `app.py`, `ollama_client.py` e %APPDATA% conferem; nada baixado nem apagado. Saída em `C:\IA\tmp\stop48_out.txt`. Daqui em diante ninguém mexe no PC até o Julio. Regressão final em 29/10 (roteiro seção 11, F1 a F12, ~2 h de PC).
- **Falha achada pelo Julio na aba Imagem (22/10, 10h34), corrigida no `fb8b04d`:** diálogo `AttributeError: 'NoneType' object has no attribute 'isatty'` em toda geração de imagem (txt2img e inpaint) pelo atalho. Causa (traceback do ia_off em `C:\IA\tmp\isatty_tb.txt`): o app roda pelo `pythonw`, sem console, então `sys.stdout/stderr` e `sys.__stdout__/__stderr__` ficam `None`; o `transformers` 5.5.4 (`utils/loading_report.py:123`, `_style`) chama `sys.stdout.isatty()` ao carregar o text_encoder do SD 1.5. Os testes rodavam com console e não pegaram. Fix do Front `5b8c93e` (`a126945` + `5024dda`): `ensure_std_streams()` na 1ª linha do `main()` aponta os quatro streams para `os.devnull`; testes de `tqdm` e de `_style` (`35c5de4`) rodaram de verdade na P2. Beck `66cb14c`: a fila grava o traceback completo das falhas no `erro.log` (antes ele se perdia). Conferido pelo ia_off com o pythonw do app: sem máscara 18,8 s, com máscara 21,3 s, sem erro; hashes de `config.json` e `conversas.db` como esperado. Confirmado pelo Julio pelo atalho às 11h32: a aba Imagem gera sem erro.
- **Pedido do Julio (22/10, 11h32): barra de progresso parada entre passos.** No Melhorar, na Imagem e no Vídeo, o "falta" e a porcentagem só mudam quando termina um passo (ou bloco), e ficam parados no meio. No Melhorar com Lanczos é um passo só, então fica parado até o fim. Decisão do Gerente: entra antes da entrega, com o Front. Fix `cc241d6` (main `02f0e8c`): o "falta" desce a cada segundo entre os passos, a porcentagem anda aos poucos sem passar do próximo passo, e aparece "quase lá" se a estimativa acabar antes. Front `e6f82af`: com um passo só (Lanczos no Melhorar) ou antes do 1º passo, mostra "Processando… Xs" / "Carregando modelo… Xs". Instalado no `d040ea5` (11h48); falta a conferência do Julio.
- **Pedido do Julio (22/10, 11h44): linha Tamanho da aba Vídeo espremida** (Proporção, Resolução e L×A sobrepostas, sem clique). Causa: a aba Vídeo não tinha rolagem e o Qt comprimia o seletor em janela baixa. Fix do Front `5c3ea45`: painel da esquerda rola e o seletor mantém o tamanho, com teste que falha sem o fix. Instalado no `d040ea5` com a barra; ia_off conferiu no PC (testes da barra, seletor não espremido, Melhorar pelo modo simples ok; `conversas.db` inalterado). Falta a conferência do Julio.
- **Tamanho do app (medido pelo ia_off, 22/10, só leitura):** uns 57 GB com só o que o app usa (app + Python/venv 2,3 GB, Ollama instalado 2,8 GB, modelos ~51,5 GB: Ollama 17,6, Z-Image 6,2, Wan 13, resto ~14,7; dados 0,13 GB); ~147 GB com tudo no PC (90 GB são cópias .gguf, cache OpenVINO, qwen3-30b e modelos não usados; nada apagado). O `config.json` está com o qwen3-30b-a3b no chat, não o 27B aprovado; com ele o mínimo sobe para ~74 GB. Decisão pendente do Julio.
- Pendentes do Julio: E9 e os cliques reais do E10.
- Ampliador com IA pronto no código, mas no PC continua no Lanczos até o Julio aprovar o modelo de ~4,9 MB.

## Limites conhecidos
- O vídeo é lento neste PC. O menor teste (5 quadros, 2 passos) leva ~12 min, quase 9 deles decodificando, e um de 17 quadros com 20 passos leva ~68 min.
- Z-Image a 768 px passa de 30 min.
- Transcrever e Ampliar não passam pela moderação.

## Passo a passo dos testes do Julio
Esta é a lista oficial, que junta este passo a passo com o checklist do `docs/ROTEIRO_TESTES.md`.
Faça um de cada vez, com o app aberto.

1. **Trocar a senha temporária.** Abra Configurações > Moderação e clique em "Trocar senha…". Use a senha de `C:\IA\dados\SENHA_TEMPORARIA.txt` como atual e crie a sua. Quando der certo, avise a equipe pra apagar o txt.
2. **Senha errada (SE1).** Clique em "Alterar filtro…" e digite uma senha errada. Nada pode mudar.
3. **Ligar o filtro (MO5).** Em "Alterar filtro…", com a senha certa, ligue a moderação no nível médio.
4. **Bloqueio (MO5).** Mande um prompt proibido nas abas Imagem, Vídeo e Falar. Em todas tem que aparecer a mensagem de bloqueio com o motivo, sem gerar nada.
5. **Desligar.** Volte em "Alterar filtro…" e desligue a moderação. Mande o mesmo prompt de novo: agora não pode haver bloqueio.
6. **Vídeo na tela.** O menu Modelo já foi conferido por automação: lista Wan 2.1 1.3B e Wan 2.2 5B (TI2V). Gere um vídeo curto (5 quadros, 2 passos) e veja a barra mostrar "Decodificando…" depois do último passo. Leva uns 12 min. Num segundo vídeo, clique em Cancelar no meio e confira se para logo, sem passo falso depois (V4).
7. **Sem internet (S3).** Rode como administrador o comando de firewall que o ia_off mandou, ou desligue o Wi-Fi ou tire o cabo. Use todas as abas: Chat, Imagem, Vídeo, Documentos e Voz. Tudo tem que funcionar. Depois religue a internet. Enquanto ela estiver desligada, a equipe perde o acesso ao PC.
Já feitos em 16/10, com o ok do Julio: SE4 aprovado (sem o `moderacao_senha.json` o app pede senha nova; o arquivo foi restaurado do backup e a senha temporária voltou) e os temporários da instalação apagados (os backups ficaram).

Se algo falhar, mande no grupo um print e o horário.

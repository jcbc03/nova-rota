# IA Off 3.0: entrega (30/10/2026)

**Versão entregue:** `3f1e0b6`, instalada no PC do Julio em 29/10 às 9h14 (horário de Brasília). O backup está em `C:\IA\backup\v3_20261029_091330`, e os 26 arquivos instalados batem com o pacote. Os commits posteriores no main só mudam a documentação.

## Testes
- A P2 limpa passou duas vezes no `3f1e0b6`, com 268 ok e 3 skipped, e a R5 também está limpa.
- O E15 passou: no modo Auto, o FLUX.2 rodou na CPU e levou 474,6 s em 512×512 e 825,5 s em 512×1024.
- O E16 passou: o Wan 2.2 com imagem inicial levou 602,6 s.
- Na regressão final F1–F12, F1 a F10 estão ✅. O F11 e o F12 estão 🟡 só por itens do Julio: o R4 e o bloqueio de tela.
- Os detalhes estão no `docs/ROTEIRO_TESTES.md` e no `docs/NOTAS_3.0_RC.md`.

## O que é novo na 3.0
Está resumido no `docs/CHANGELOG.md` e no `docs/NOTAS_3.0_RC.md`. Os destaques:
- o Parar responde na hora;
- a barra de progresso mostra o tempo que falta;
- a fila de mídia aceita imagem, vídeo, ampliar, transcrever e falar;
- o FLUX.2 roda na CPU;
- o vídeo Wan 2.2 aceita imagem inicial;
- a linha Tamanho do vídeo foi refeita.

## Limite conhecido
No F7, a estimativa de tempo da decodificação do Wan saiu cerca de 92% acima do real. É só o número que aparece na tela: o vídeo e o tempo real saem certos. A correção (Front) está pronta pra entrar se o Julio aprovar; senão, entra na 3.0.1.

## Pendências do Julio
1. Fazer o checklist de tela em `docs/NOTAS_3.0_RC.md`: E9, os cliques do E10, MO5 e SE1, a barra de progresso, a linha Tamanho, a troca da senha temporária, o E16 na mão, o R4 com o bloqueio de tela e, por último, o S3.
2. Decidir:
   - se a correção do F7 entra agora ou fica pra 3.0.1;
   - o modelo do chat (o `config.json` está com o `qwen3-30b-a3b`, e não com o 27B aprovado);
   - se o FLUX.2 continua;
   - se aprova o `realesr-general-x4v3.onnx`;
   - a limpeza do `stash@{0}`, dos zips e dos ~90 GB.

Nada é apagado sem o ok do Julio.

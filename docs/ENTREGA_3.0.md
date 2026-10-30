# IA Off 3.0: entrega (30/10/2026)

**Versão entregue:** `2f9ec50`, instalada no PC do Julio em 29/10 por volta das 22h36 (horário de Brasília). O backup está em `C:\IA\backup\v3_20261029_223603`, os 53 hashes conferem e o `config.json` não mudou. É o `3f1e0b6` mais a correção do F7 (Front `9200d19`, aprovada pelo Julio às 20h21). A instalação anterior, `3f1e0b6`, tem backup em `v3_20261029_091330`. Os commits posteriores no main só mudam a documentação.

## Testes
- A P2 limpa passou duas vezes no `2f9ec50`, com 271 ok e 3 skipped, e a R5 também está limpa. No `3f1e0b6`, tinha dado 268 ok.
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

## Corrigido na véspera: estimativa do F7
A estimativa de tempo da decodificação do Wan saía cerca de 92% acima do real. Agora o app guarda o tempo real de cada tamanho (largura × altura × quadros). O ia_off refez o F7 duas vezes no PC:
- 1ª rodada: estimou 6 min 59 s e levou 3 min 31 s. Era esperado, porque esse tamanho ainda não tinha tempo salvo.
- 2ª rodada: estimou 3 min 30 s e levou 3 min 49 s, cerca de 8% abaixo do real, dentro do limite de 25%.

Ressalva: na primeira vez que um tamanho novo roda, a estimativa ainda usa a conta proporcional.

## Pendências do Julio
1. Fazer o checklist de tela em `docs/NOTAS_3.0_RC.md`: E9, os cliques do E10, MO5 e SE1, a barra de progresso, a linha Tamanho, a troca da senha temporária, o E16 na mão, o R4 com o bloqueio de tela e, por último, o S3.
2. Decidir:
   - o modelo do chat (o `config.json` está com o `qwen3-30b-a3b`, e não com o 27B aprovado);
   - se o FLUX.2 continua;
   - se aprova o `realesr-general-x4v3.onnx`;
   - a limpeza do `stash@{0}`, dos zips e dos ~90 GB.

Nada é apagado sem o ok do Julio.

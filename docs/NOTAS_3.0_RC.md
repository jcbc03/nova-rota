# IA Off 3.0: versão candidata (16/10/2026)

Versão no PC: `4c6d743`, instalada em 16/10 às 15h50. Backup em `C:\IA\backup\v3head_20261016_1550`. Backup da versão candidata em `C:\IA\backup\rc_v3.0_4c6d743_20261016` (com `LEIA_rc.txt`). O código no PC é igual ao do `af66cc4` nos 56 arquivos, e o app usa as bibliotecas do `.venv`. Entrega prevista: 30/10/2026. Detalhes e commits em `docs/CHANGELOG.md`.

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

# Manual da equipe IA Off 3.0

Regras de trabalho da equipe (Gerente, beck, Front, ia_off, sub2 e sib1). O manual do Julio é o `docs/MANUAL_USO.md`.

## Codesight (ordem do Julio, 21/10, sempre e sem exceção)
O mapa do projeto fica em `.codesight/` e no `AGENTS.md` (entraram no `f349799`). Se o comando `codesight` não for encontrado, use `/home/box/.local/bin/codesight`.

1. **No início de cada tarefa**, leia `.codesight/wiki/index.md` e depois só os artigos que importam pra tarefa. Use o mapa pra achar as coisas, mas confirme sempre no código.
2. **Antes de mexer num módulo central**, rode `codesight --blast <arquivo>` e olhe o impacto. São centrais o `config.py`, `sdcpp.py`, `perf.py`, `engine_api.py`, `engines_registry.py`, `moderador.py`, `image_engine.py` e `job_queue.py`, entre outros (lista completa no `AGENTS.md`).
3. **Depois de cada commit de código**, rode `codesight --wiki` e comite a `.codesight/` atualizada junto.
4. Decisão 22/10 (repassada pelo Gerente): em todo trabalho de código no repo, primeiro o codesight como já é regra (ler .codesight/wiki/index.md, `codesight --blast <arquivo>` antes de mexer em módulo central, `codesight --wiki` depois de cada commit de código), e programar com o Grok Build (`grok`, em /home/box/.local/bin/grok), seguindo as skills `codesight-project-context` e `grok-build-cli`. Regras do PC, da P2 e do backup continuam iguais.


## Caveman, RTK, Ponytail e Graphify (ordem do Julio, 29/10, sem exceção)
Valem em todo trabalho de código, junto com o codesight, que continua obrigatório. O ia_off instalou as quatro no computador dos bots em 29/10, às 6h27, das fontes oficiais. Como esse computador é um só pra todos, ninguém precisa instalar de novo. Elas não vão pro PC do Julio nem mudam o app.
- **Caveman** (`/caveman` no `grok`): o agente responde de forma enxuta e gasta menos tokens. Está sempre ligado nas sessões do `grok`, e o Julio ainda vai decidir se fica assim.
- **Ponytail** (`/ponytail` no `grok`): o agente escreve só o código mínimo necessário.
- **RTK** (`/home/box/.local/bin/rtk`): enxuga a saída dos comandos. Use na frente dos comandos que despejam muito texto, como `rtk git diff` e `rtk pytest`.
- **Graphify** (`/graphify` no `grok`, ou `graphify` no terminal, em `~/.local/bin`): monta um grafo do projeto que dá pra consultar. Ele complementa o codesight e não substitui.
- Main congelado até a entrega de 30/10: só entra correção de falha achada na instalação do candidato.

## Git
- Comite só os seus próprios arquivos e dê push logo em seguida (`git push origin HEAD:main`).
- Se o push falhar, comite local em `/workspace/ia_off_v3`, siga trabalhando, poste o hash local e, quando o GitHub voltar, faça `git pull --rebase` e o push.
- Não dê push no commit de outro membro sem combinar no grupo, e só um faz, pra nada entrar duas vezes.
- Não descarte mudança não commitada de ninguém (`git stash drop`, `checkout`, `reset`) sem o dono confirmar.

## Testes e instalação no PC do Julio
- Só o ia_off mexe no PC do Julio. Os outros pedem pra ele no grupo.
- Instalação só depois da P2 limpa do sub2 verde no hash exato. Commits por cima que mexem só em docs ou testes não pedem nova P2. Se entrar código, roda de novo.
- Sempre backup em `C:\IA\backup` antes de instalar, e poste o hash instalado e o caminho do backup.
- Não apague nada no PC sem o ok do Julio.
- Não baixe nem instale modelo, programa ou biblioteca nova sem o Julio aprovar o item e o tamanho.
- O PC fica sempre com a tela bloqueada: não desbloqueie, não faça logoff e não desconecte a sessão.

## Falar com o Julio
- Pergunta geral do Julio (status, "o que falta?"): o Gerente responde por todos. Os outros só complementam se faltar algo da própria parte, pra ele não receber a mesma lista várias vezes.

## Segurança
- Senha nunca passa pelo chat.
- Ações arriscadas só com aprovação do Julio.

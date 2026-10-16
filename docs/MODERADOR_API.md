# Moderador — API (ia_off/moderador.py) — IA Off v3.0

Moderação **opcional** de prompts. Com `moderacao_ativa = False` (padrão) o app se comporta
exatamente como antes: nenhuma lista é carregada, nenhum arquivo é lido, prompts e negativos
voltam inalterados (identidade), `instrucoes_chat()` devolve `""`.

## Chaves em config.py
| chave | padrão | descrição |
|---|---|---|
| `moderacao_ativa` | `False` | liga/desliga |
| `moderacao_nivel` | `"medio"` | `leve` \| `medio` \| `rigido` (valor inválido = `medio`) |
| `moderacao_arquivo` | `<dados>\moderacao.json` | listas editáveis (env `IA_OFF_MODERACAO_ARQUIVO`) |
| `moderacao_senha_arquivo` | `<dados>\moderacao_senha.json` | hash da senha (env `IA_OFF_MODERACAO_SENHA`) |

`<dados>` = `config.DADOS_DIR` = env `IA_OFF_DADOS_DIR` ou `C:\IA\dados`.

Níveis são cumulativos: `leve ⊂ medio ⊂ rigido` (bloqueados, negativos e instruções do chat acumulam).
- leve: conteúdo claramente ilegal (sexual envolvendo menores).
- medio: + sexual explícito (frases como "sexo explícito"; "sexo feminino" passa), pornografia, gore, estupro, tortura.
- rigido: + "sexo"/"sex" isolados, nudez, violência, armas, drogas.

## Funções (todas aceitam `cfg=None` → `config.load()`)
```python
ativa(cfg=None) -> bool
checar_prompt(texto, contexto="imagem", cfg=None) -> None   # levanta PromptBloqueado
completar_negativo(negativo, cfg=None) -> str               # acrescenta termos do nível
instrucoes_chat(cfg=None) -> str                            # texto p/ system prompt ("" se desligada)
exportar_padrao(path) -> Path                               # grava moderacao.json padrão
senha_definida(cfg=None) -> bool
definir_senha(senha, cfg=None)        # só se não houver senha; vazia -> ValueError
verificar_senha(senha, cfg=None) -> bool
trocar_senha(atual, nova, cfg=None) -> bool   # False se 'atual' errada; nova vazia -> ValueError
class PromptBloqueado(Exception): .motivo (pt-BR), .termo, .nivel, .contexto
```
`contexto`: `imagem` | `video` | `voz` | `chat` (informativo, vai na exceção).

## Casamento de termos
Normaliza (remove acentos NFKD, minúsculas, leet `0→o 1→i 3→e 4→a 5→s @→a $→s`),
quebra em palavras e compara **palavra/frase inteira** (não substring: "sexta", "Essex",
"armário" passam). Sequências de 3+ letras isoladas são juntadas (`s e x o` → `sexo`);
"e a", "o e" nunca são coladas.

## moderacao.json
```json
{
  "versao": 1,
  "substituir": false,
  "niveis": {
    "leve":   {"bloqueados": ["..."], "negativos": ["..."]},
    "medio":  {"bloqueados": ["..."], "negativos": ["..."]},
    "rigido": {"bloqueados": ["..."], "negativos": ["..."]}
  }
}
```
- `substituir: false` (padrão): listas do arquivo **estendem** as embutidas; `true`: substituem
  (apenas para os níveis/campos presentes).
- Arquivo ausente → listas embutidas. JSON inválido ou formato errado → listas embutidas + warning
  no log (nunca quebra). Gere um modelo com `moderador.exportar_padrao(cfg["moderacao_arquivo"])`.

## GUI (DEV Front): senha antes de alterar ativa/nível
```python
from ia_off import moderador as mod
if not mod.senha_definida(cfg):
    nova = pedir_nova_senha()              # confirmar 2x; recusar vazia
    mod.definir_senha(nova, cfg)
elif not mod.verificar_senha(pedir_senha(), cfg):
    avisar("Senha incorreta"); return
cfg["moderacao_ativa"] = ...; cfg["moderacao_nivel"] = ...; config.save(cfg)
```
Apagar o arquivo de senha reseta: o app volta a pedir uma nova senha.
O arquivo guarda só `algo`, `iterations` (240000), `salt` e `hash` (hex, PBKDF2-HMAC-SHA256).

## Engines (ia_off): antes de carregar qualquer modelo
```python
from ia_off import moderador as mod
try:
    mod.checar_prompt(prompt, "imagem", cfg)     # "video" | "voz" | "chat"
except mod.PromptBloqueado as e:
    mostrar_erro(e.motivo); return
negativo = mod.completar_negativo(negativo, cfg)
# chat: system = cfg["system_prompt"] + ("\n" + mod.instrucoes_chat(cfg) if mod.ativa(cfg) else "")
```
Chame a checagem **antes** de carregar o modelo para não gastar RAM/tempo com pedidos recusados.

## Log (logger `ia_off.moderador`)
- WARNING: `moderacao.json` inválido/formato errado (usa listas embutidas); arquivo de senha existente mas
  ilegível/corrompido (`senha_definida` e `verificar_senha` devolvem `False`, comportamento inalterado).
- Arquivo de senha ausente não gera aviso (estado normal: sem senha). Senha errada não gera log.

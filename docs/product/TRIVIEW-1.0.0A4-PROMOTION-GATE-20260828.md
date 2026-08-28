# TriView 1.0.0a4 — gate de promoção do ecossistema (2026-08-28)

## Estado canônico observado

| Referência | Estado |
| --- | --- |
| TriView `main` | `60b7e86dc738e1dc285e942951c67e41ac82b018` (`v1.0.0a3`) |
| TriView `release/1.0.0a4` | `09a361d761adf1e2e614d23718b84776c365cacc` (PR #78) |
| Divergência `main...release/1.0.0a4` | `0/117`: nenhum commit exclusivo de `main`; a release está 117 commits à frente |
| PR TriView #74 | `release/1.0.0a4` → `main`; **DRAFT**, estado de merge `CLEAN`, sem merge |
| MCF `main` | `0b900ee03a05153e2e4a795fce7b457f5b4bb812`, após PRs #180, #184 e #185 |

Este registro é uma reconciliação documental e de Capsule. Não altera runtime,
provider, controles de janela, protocolo GUI, versões, tags, release ou estado
canônico MCF.

## Limite de integração

O Mission Cockpit TriView permanece estritamente **GET-only** e orientado por
evidência. Ele não conecta, autoriza, executa, revoga ou escreve. A referência
MCF acima atualiza o contexto de promoção; ela não amplia o escopo do cockpit e
não autoriza recuperação MCF, mutação de missão, gate humano ou autorização.

## Gates ainda bloqueantes

- Aceite físico R7 em Linux Mint/X11: **NOT_RUN**.
- Matriz LEA-197: cinco ciclos Terminal e cinco ciclos Xed, sem captura entre
  janelas: **NOT_RUN**.
- Smoke físico da integração MCF/Cockpit: **NOT_RUN**.
- Update controlado de pré-publicação, dry-run de rollback e rollback controlado:
  **NOT_RUN**.
- Issue #26: bloqueada até a evidência física exata ser aprovada.
- `HUMAN_GATE` final: bloqueado até todos os gates anteriores passarem e haver
  aprovação humana nova.

Assim, a PR #74 deve permanecer draft; não há autorização para merge em `main`,
tag, publicação ou release.

## Sequência recomendada

1. Manter esta reconciliação de documentação/Capsule separada e revisável.
2. Renovar o candidato e executar o R7 físico completo contra o SHA exato
   aprovado, incluindo os gates LEA-197, MCF, update e rollback.
3. Resolver a Issue #26 e obter um `HUMAN_GATE` novo antes de qualquer decisão
   de promoção.

Esta ordem evita tratar o estado de integração documental MCF como evidência de
aceite físico ou autorização de publicação.

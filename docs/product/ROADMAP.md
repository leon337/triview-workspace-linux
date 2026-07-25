# Roadmap do produto

Este roadmap registra direção e sequência. Uma funcionalidade só é concluída após implementação, CI, integração no trem e teste de aceite no Linux Mint.

## Marcos concluídos

### `0.1.0` — Fundação modular
Status: **concluído**

### `0.1.1` — Migração e atualização segura
Status: **concluído**

### `0.1.2` — Primeira interface gráfica
Status: **concluído**

### LEA-194 — Consolidação documental
Status: **concluído**

### `0.2.0` — Browser Engine
Status: **concluído e validado no Linux Mint**

### `0.3.0` — Workspaces persistentes
Status: **concluído e validado no Linux Mint**

## Trem de desenvolvimento LEA-197–205

A branch `main` permanece estável. O trem é integrado em `train/road-to-1.0`. Cada LEA usa branch, PR, CI e candidato isolado antes da promoção.

### `0.4.0` — Application Engine — LEA-197
Status: **integrado ao trem; aguardando teste no Linux Mint**

### `0.5.0` — Terminal Engine — LEA-198
Status: **integrado ao trem; aguardando teste no Linux Mint**

### `0.6.0` — PDF Engine — LEA-199
Status: **integrado ao trem; aguardando teste no Linux Mint**

### `0.7.0` — Capture Engine — LEA-200
Status: **implementado no candidato; aguardando CI e teste no Linux Mint**

- captura por janela do painel;
- backends maim e ImageMagick;
- botão Print habilitado;
- PNGs organizados e histórico JSONL;
- candidato isolado.

### `0.8.0` — Recording Engine — LEA-201
Status: **planejado**

### `0.9.0` — Plugin Engine — LEA-202
Status: **planejado**

### `0.10.0` — Layout Engine avançado — LEA-203
Status: **planejado**

### `0.11.0` — Session Engine completo — LEA-204
Status: **planejado**

### `1.0.0` — Workspace Hub — LEA-205
Status: **planejado**

## Evoluções posteriores

- backend nativo ou híbrido para Wayland;
- múltiplos monitores;
- sincronização opcional;
- marketplace e assinatura de plugins;
- automações e agentes de IA.

## Itens transversais

- testes automatizados e CI;
- logs e mensagens de erro;
- documentação e ADRs;
- backup e compatibilidade de dados;
- candidatos isolados;
- rastreabilidade Linear ↔ GitHub.

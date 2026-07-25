# Roadmap do produto

Uma funcionalidade só é concluída após implementação, CI, integração no trem e teste de aceite no Linux Mint.

## Marcos validados

- `0.1.0` Fundação modular — **concluído**;
- `0.1.1` Migração segura — **concluído**;
- `0.1.2` Interface gráfica — **concluído**;
- LEA-194 Documentação — **concluído**;
- `0.2.0` Browser Engine — **validado no Linux Mint**;
- `0.3.0` Workspaces persistentes — **validado no Linux Mint**.

## Trem LEA-197–205

A branch `main` permanece estável. A integração ocorre em `train/road-to-1.0`.

### `0.4.0` — Application Engine — LEA-197
Status: **integrado ao trem; aguardando teste**

### `0.5.0` — Terminal Engine — LEA-198
Status: **integrado ao trem; aguardando teste**

### `0.6.0` — PDF Engine — LEA-199
Status: **integrado ao trem; aguardando teste**

### `0.7.0` — Capture Engine — LEA-200
Status: **integrado ao trem; aguardando teste**

### `0.8.0` — Recording Engine — LEA-201
Status: **integrado ao trem; aguardando teste**

### `0.9.0` — Plugin Engine — LEA-202
Status: **implementado no candidato; aguardando CI e teste**

- manifestos declarativos e API versionada;
- ativação explícita;
- diretórios permitidos e symlinks ignorados;
- execução pelo Application Engine sem shell;
- diagnóstico e isolamento de falhas.

### `0.10.0` — Layout Engine avançado — LEA-203
Status: **planejado**

### `0.11.0` — Session Engine completo — LEA-204
Status: **planejado**

### `1.0.0` — Workspace Hub — LEA-205
Status: **planejado**

## Posterior

- Wayland nativo;
- múltiplos monitores;
- sincronização opcional;
- marketplace e assinatura de plugins;
- agentes de IA.

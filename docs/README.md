# Documentação do TriView Workspace

Este diretório separa recursos validados, candidatos do trem e funcionalidades planejadas.

## Estado

- versão estável: `0.3.0` em `main`;
- candidato atual: `0.5.0` — Terminal Engine, LEA-198;
- Browser e workspaces persistentes: validados;
- Application Engine e Panel Runtime: integrados ao trem;
- Terminal Engine: implementado, aguardando CI e aceite;
- LEA-199–205: etapas seguintes.

## Produto

- [Visão](product/VISION.md)
- [Princípios](product/PRINCIPLES.md)
- [Roadmap](product/ROADMAP.md)
- [Histórico](product/RELEASE_HISTORY.md)

## Arquitetura

- [Visão arquitetural](architecture/README.md)
- [Engines](architecture/ENGINES.md)
- [Migração](migration.md)
- [Atualização e candidatos](updater.md)

## ADRs

- [ADR-0001 — Plataforma](decisions/ADR-0001-workspace-platform.md)
- [ADR-0002 — Documentação](decisions/ADR-0002-documentation-source-of-truth.md)
- [ADR-0003 — Browser X11](decisions/ADR-0003-browser-x11-reparenting.md)
- [ADR-0004 — Catálogo versionado](decisions/ADR-0004-versioned-workspace-catalog.md)
- [ADR-0005 — Panel Runtime](decisions/ADR-0005-application-engine-panel-runtime.md)
- [ADR-0006 — Terminal e emuladores](decisions/ADR-0006-terminal-engine-emulator-adapters.md)

## Registros

- [LEA-195](work/LEA-195.md)
- [LEA-196](work/LEA-196.md)
- [LEA-197](work/LEA-197.md)
- [LEA-198](work/LEA-198.md)

## Fábrica

- [Manual](factory/SOFTWARE_FACTORY_WORKFLOW.md)
- [Trem LEA-197–205](factory/DEVELOPMENT_TRAIN_LEA-197-205.md)

## Regras

1. `main` recebe somente marcos aprovados.
2. Cada candidato usa branch, PR, CI e instalação isolada.
3. Decisões arquiteturais geram ADR.
4. Dados pessoais não ficam no código versionado.
5. Dependências reprovadas bloqueiam promoções posteriores afetadas.

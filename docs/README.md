# Documentação do TriView Workspace

Este diretório é a referência oficial do produto. Ele separa o que está validado, o que está em candidato e o que permanece planejado.

## Visão rápida

- **Versão estável:** `0.3.0` na branch `main`.
- **Candidato atual:** `0.4.0` — Application Engine, LEA-197.
- **Browser Engine:** validado em Linux Mint/X11.
- **Workspaces persistentes:** validados no Linux Mint.
- **Panel Runtime:** implementado para processos e janelas X11.
- **Application Engine:** implementado, aguardando CI e aceite real.
- **LEA-198–205:** tarefas e branches preparadas no trem.

## Produto

- [Visão do produto](product/VISION.md)
- [Princípios do produto](product/PRINCIPLES.md)
- [Roadmap](product/ROADMAP.md)
- [Histórico de versões](product/RELEASE_HISTORY.md)

## Arquitetura

- [Arquitetura da plataforma](architecture/README.md)
- [Responsabilidades dos Engines](architecture/ENGINES.md)
- [Migração da versão legada](migration.md)
- [Estratégia de atualização](updater.md)

## Decisões arquiteturais

- [ADR-0001 — Plataforma de workspaces](decisions/ADR-0001-workspace-platform.md)
- [ADR-0002 — Documentação como fonte oficial](decisions/ADR-0002-documentation-source-of-truth.md)
- [ADR-0003 — Browser Engine por incorporação X11](decisions/ADR-0003-browser-x11-reparenting.md)
- [ADR-0004 — Catálogo versionado de workspaces](decisions/ADR-0004-versioned-workspace-catalog.md)
- [ADR-0005 — Application Engine sobre Panel Runtime](decisions/ADR-0005-application-engine-panel-runtime.md)

## Registros de trabalho

- [LEA-195 — Browser Engine](work/LEA-195.md)
- [LEA-196 — Workspaces persistentes](work/LEA-196.md)
- [LEA-197 — Application Engine](work/LEA-197.md)

## Fábrica de Softwares

- [Manual operacional](factory/SOFTWARE_FACTORY_WORKFLOW.md)
- [Trem LEA-197–205](factory/DEVELOPMENT_TRAIN_LEA-197-205.md)

## Regras de manutenção

1. `main` contém apenas marcos aprovados no Linux Mint.
2. Candidatos ficam em branches e instalações isoladas.
3. Toda LEA possui Linear, branch, PR, CI, documentação e aceite.
4. Decisões relevantes geram ADR.
5. Dados pessoais ficam fora dos diretórios versionados.
6. Falha em uma dependência bloqueia a promoção das LEAs posteriores afetadas.

# Documentação do TriView Workspace

Este diretório é a referência oficial do produto. Ele separa o que está implementado, o que aguarda validação e o que permanece planejado.

## Visão rápida

- **Produto:** plataforma Linux para organizar workspaces compostos por painéis independentes.
- **Versão funcional atual:** `0.3.0`.
- **Estado atual:** fundação modular, migração segura, atualizador versionado, Browser Engine validado em X11 e catálogo persistente de workspaces.
- **Persistência:** catálogo versionado em `XDG_DATA_HOME`, com gravação atômica e restauração do último workspace.
- **Disponibilidade do navegador:** exige `DISPLAY`, Brave/Chromium compatível e `xdotool`.
- **Ainda não implementado:** Application Engine, print individual, gravação por painel, plugins e backend nativo de Wayland.

## Documentação de produto

- [Visão do produto](product/VISION.md)
- [Princípios do produto](product/PRINCIPLES.md)
- [Roadmap](product/ROADMAP.md)
- [Histórico de versões](product/RELEASE_HISTORY.md)

## Documentação técnica

- [Arquitetura da plataforma](architecture/README.md)
- [Responsabilidades dos Engines](architecture/ENGINES.md)
- [Migração da versão legada](migration.md)
- [Estratégia de atualização](updater.md)

## Decisões arquiteturais

- [ADR-0001 — Plataforma de workspaces](decisions/ADR-0001-workspace-platform.md)
- [ADR-0002 — Documentação como fonte oficial](decisions/ADR-0002-documentation-source-of-truth.md)
- [ADR-0003 — Browser Engine por incorporação X11](decisions/ADR-0003-browser-x11-reparenting.md)
- [ADR-0004 — Catálogo versionado de workspaces](decisions/ADR-0004-versioned-workspace-catalog.md)

## Registros de trabalho

- [LEA-195 — Primeiro Browser Engine funcional](work/LEA-195.md)
- [LEA-196 — Workspaces persistentes](work/LEA-196.md)

## Processo da Fábrica de Softwares

- [Manual operacional da Fábrica de Softwares](factory/SOFTWARE_FACTORY_WORKFLOW.md)

## Regras de manutenção

1. Uma funcionalidade só pode ser descrita como concluída quando estiver implementada, testada e integrada à branch principal.
2. Funcionalidades futuras devem ser marcadas como planejadas.
3. Toda decisão arquitetural relevante deve gerar ou atualizar uma ADR.
4. Toda versão funcional deve atualizar o `CHANGELOG.md` e o histórico de versões.
5. Toda tarefa concluída deve manter vínculo entre Linear, branch, pull request e commit de merge.
6. Dados pessoais do usuário não devem ser gravados dentro do diretório versionado do código.
7. O README da raiz deve permanecer como porta de entrada para esta documentação.

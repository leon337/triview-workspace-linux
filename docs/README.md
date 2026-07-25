# Documentação do TriView Workspace

Este diretório é a referência oficial do produto. Ele separa claramente o que já está implementado, o que está em desenvolvimento e o que ainda é planejamento.

## Visão rápida

- **Produto:** plataforma Linux para organizar workspaces compostos por painéis independentes.
- **Versão funcional atual:** `0.1.2`.
- **Estado atual:** fundação modular, migração segura, atualizador versionado e interface gráfica inicial com três painéis responsivos.
- **Ainda não implementado:** incorporação real de navegadores e aplicações, persistência completa de workspaces, print individual e gravação por painel.

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

- [ADR-0001 — Tratar o produto como plataforma de workspaces](decisions/ADR-0001-workspace-platform.md)
- [ADR-0002 — Documentação como fonte oficial de verdade](decisions/ADR-0002-documentation-source-of-truth.md)

## Processo da Fábrica de Softwares

- [Manual operacional da Fábrica de Softwares](factory/SOFTWARE_FACTORY_WORKFLOW.md)

## Regras de manutenção

1. Uma funcionalidade só pode ser descrita como concluída quando estiver implementada, testada e integrada à branch principal.
2. Funcionalidades futuras devem ser marcadas como planejadas, nunca como disponíveis.
3. Toda decisão arquitetural relevante deve gerar ou atualizar uma ADR.
4. Toda versão funcional deve atualizar o `CHANGELOG.md` e o histórico de versões.
5. Toda tarefa concluída deve manter vínculo entre Linear, branch, pull request e commit de merge.
6. O README da raiz deve permanecer curto e apontar para esta documentação central.

## Estado documental

A consolidação desta estrutura foi executada pela tarefa **LEA-194**. A partir dela, este diretório passa a ser a referência principal para continuidade técnica, produto e processo.

# Documentação do TriView Workspace

Este diretório separa recursos validados, candidatos do trem e funcionalidades planejadas.

## Estado

- versão estável: `0.3.0` em `main`;
- candidato atual: `0.8.0` — Recording Engine, LEA-201;
- Browser e workspaces persistentes: validados;
- Application, Terminal, PDF e Capture Engines: integrados ao trem;
- Recording Engine: implementado, aguardando CI e aceite;
- LEA-202–205: etapas seguintes.

## Produto

- [Visão](product/VISION.md)
- [Princípios](product/PRINCIPLES.md)
- [Roadmap](product/ROADMAP.md)
- [Histórico](product/RELEASE_HISTORY.md)

## Arquitetura

- [Visão arquitetural](architecture/README.md)
- [Engines](architecture/ENGINES.md)
- [Atualização e candidatos](updater.md)

## ADRs do trem

- [ADR-0005 — Panel Runtime](decisions/ADR-0005-application-engine-panel-runtime.md)
- [ADR-0006 — Terminal e emuladores](decisions/ADR-0006-terminal-engine-emulator-adapters.md)
- [ADR-0007 — Visualizadores PDF](decisions/ADR-0007-pdf-viewer-runtime.md)
- [ADR-0008 — Captura por janela](decisions/ADR-0008-panel-window-capture.md)
- [ADR-0009 — Gravação com FFmpeg](decisions/ADR-0009-panel-region-recording-ffmpeg.md)

## Registros do trem

- [LEA-197](work/LEA-197.md)
- [LEA-198](work/LEA-198.md)
- [LEA-199](work/LEA-199.md)
- [LEA-200](work/LEA-200.md)
- [LEA-201](work/LEA-201.md)

## Fábrica

- [Manual](factory/SOFTWARE_FACTORY_WORKFLOW.md)
- [Trem LEA-197–205](factory/DEVELOPMENT_TRAIN_LEA-197-205.md)

## Regras

1. `main` recebe somente marcos aprovados.
2. Cada candidato usa branch, PR, CI e instalação isolada.
3. Decisões arquiteturais geram ADR.
4. Dados pessoais ficam fora do código versionado.
5. Dependências reprovadas bloqueiam promoções posteriores afetadas.

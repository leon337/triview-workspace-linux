# Changelog

## 0.7.0 — Capture Engine

- implementa captura individual por painel;
- usa `maim` ou ImageMagick `import` em X11;
- habilita o botão Print para todos os tipos de painel;
- grava primeiro em arquivo parcial e promove somente após sucesso;
- organiza PNGs por workspace, painel e data;
- adiciona histórico JSONL auditável;
- executa captura sem bloquear a interface;
- adiciona testes e ADR-0008.

## 0.6.0 — PDF Engine

- PDF Adapter e Engine;
- visualizadores do sistema;
- validação, incorporação e fallback externo;
- ADR-0007.

## 0.5.0 — Terminal Engine

- Terminal Adapter e Engine;
- shell configurável e emuladores adaptados;
- shell gráfico genérico;
- ADR-0006.

## 0.4.0 — Application Engine e Panel Runtime

- Panel Runtime comum;
- execução sem shell;
- Application Engine e fallback externo;
- ADR-0005.

## 0.3.0 — Workspaces persistentes

- catálogo versionado e atômico;
- criação, edição, alternância e restauração.

## 0.2.0 — Browser Engine

- navegador incorporado, perfis separados e ciclo de vida.

## Consolidação documental — LEA-194

- visão, roadmap, arquitetura e manual da Fábrica.

## 0.1.2 — Interface gráfica inicial

- janela responsiva e diagnóstico separado.

## 0.1.1 — Migração segura

- backup, restauração e atualizador.

## 0.1.0 — Fundação

- modelos, Engines básicos, adaptadores, testes e CI.

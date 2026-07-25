# Changelog

## 0.8.0 — Recording Engine

- implementa gravação individual por painel com FFmpeg x11grab;
- grava a geometria absoluta do painel em MP4/H.264;
- adiciona início, pausa, retomada e encerramento;
- alterna o botão Gravar para Parar;
- adiciona indicador GRAVANDO;
- finaliza o contêiner com SIGINT e evita processos órfãos;
- organiza vídeos e histórico por workspace, painel e data;
- adiciona testes e ADR-0009.

## 0.7.0 — Capture Engine

- captura individual com maim ou ImageMagick;
- botão Print, PNGs organizados e histórico JSONL;
- ADR-0008.

## 0.6.0 — PDF Engine

- PDF Adapter e Engine;
- visualizadores do sistema e fallback externo;
- ADR-0007.

## 0.5.0 — Terminal Engine

- Terminal Adapter e Engine;
- shell configurável e emuladores adaptados;
- ADR-0006.

## 0.4.0 — Application Engine e Panel Runtime

- Panel Runtime comum e Application Engine;
- incorporação X11 e fallback externo;
- ADR-0005.

## 0.3.0 — Workspaces persistentes

- catálogo versionado, atômico e restaurável.

## 0.2.0 — Browser Engine

- navegador incorporado e ciclo de vida.

## 0.1.x — Fundação

- arquitetura modular, migração e interface gráfica.

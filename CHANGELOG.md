# Changelog

## 0.9.0 — Plugin Engine

- adiciona manifestos declarativos com esquema e API versionados;
- descobre plugins somente em diretórios permitidos;
- ignora symlinks e rejeita IDs ou versões incompatíveis;
- exige ativação explícita;
- grava estado de ativação atomicamente;
- adiciona Plugin Adapter para painéis `custom`;
- executa comandos pelo Application Engine, sem shell;
- isola falhas e apresenta diagnósticos;
- adiciona gerenciador na GUI, exemplo e instalador;
- adiciona testes e ADR-0010.

## 0.8.0 — Recording Engine

- gravação individual com FFmpeg x11grab;
- botão Gravar/Parar, indicador e histórico;
- ADR-0009.

## 0.7.0 — Capture Engine

- captura individual com maim ou ImageMagick;
- botão Print e histórico;
- ADR-0008.

## 0.6.0 — PDF Engine

- PDF Adapter, visualizadores e fallback;
- ADR-0007.

## 0.5.0 — Terminal Engine

- Terminal Adapter, shells e emuladores;
- ADR-0006.

## 0.4.0 — Application Engine e Panel Runtime

- runtime comum, aplicações e fallback;
- ADR-0005.

## 0.3.0 — Workspaces persistentes

- catálogo versionado e restaurável.

## 0.2.0 — Browser Engine

- navegador incorporado e ciclo de vida.

## 0.1.x — Fundação

- arquitetura modular, migração e interface gráfica.

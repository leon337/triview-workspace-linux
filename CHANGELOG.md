# Changelog

## 0.6.0 — PDF Engine

- adiciona validação de arquivos PDF locais;
- implementa `PdfPanelAdapter` e `PdfEngine`;
- detecta Xreader, Evince, Atril, Okular, Zathura e MuPDF;
- reutiliza Panel Runtime para incorporação e fallback externo;
- preserva a abertura da GUI quando o arquivo foi movido ou é inválido;
- integra PDF ao registro genérico de controladores;
- adiciona testes de arquivo, adaptador, sessão e fallback;
- registra ADR-0007;
- atualiza candidato para `0.6.0`.

## 0.5.0 — Terminal Engine

- Terminal Adapter e Engine;
- shell configurável e emuladores adaptados;
- shell gráfico genérico;
- incorporação e fallback pelo Panel Runtime;
- ADR-0006.

## 0.4.0 — Application Engine e Panel Runtime

- Panel Runtime comum;
- execução sem shell;
- Application Engine e Adapter;
- incorporação X11 e fallback externo;
- ADR-0005.

## 0.3.0 — Workspaces persistentes

- catálogo versionado, gravação atômica e restauração;
- criação, edição, alternância e exclusão;
- Session Engine e Repository.

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

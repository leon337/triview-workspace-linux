# Changelog

## 0.5.0 — Terminal Engine

- adiciona `TerminalPanelAdapter` e `TerminalEngine`;
- permite shell configurável por painel;
- detecta xterm, XFCE Terminal, GNOME Terminal, Kitty, Alacritty e Konsole;
- permite priorizar emulador por `TRIVIEW_TERMINAL`;
- traduz argumentos por emulador sem shell intermediário;
- reutiliza Panel Runtime para incorporação, redimensionamento e encerramento;
- mantém fallback externo explícito;
- adiciona registro genérico de controladores de runtime;
- substitui a GUI específica por shell genérico para Browser, Application e Terminal;
- adiciona testes de emulador, shell e ciclo de vida;
- registra ADR-0006;
- atualiza candidato para `0.5.0`.

## 0.4.0 — Application Engine e Panel Runtime

- adiciona `PanelRuntime` comum;
- executa comandos sem `shell=True`;
- implementa `ApplicationEngine` e `ApplicationPanelAdapter`;
- incorpora aplicações compatíveis em X11;
- usa fallback externo controlado;
- adiciona candidato isolado e ADR-0005.

## 0.3.0 — Workspaces persistentes

- catálogo JSON versionado e atômico;
- criação, cópia, edição, renomeação e exclusão;
- restauração automática do último workspace;
- recuperação de catálogo corrompido;
- Session Engine e Repository desacoplados.

## 0.2.0 — Browser Engine

- Browser Adapter e Browser Engine;
- Brave/Chromium incorporado em X11;
- perfis separados, redimensionamento e fallback.

## Consolidação documental — LEA-194

- visão, roadmap, histórico, arquitetura e manual da Fábrica de Softwares.

## 0.1.2 — Interface gráfica inicial

- janela desktop responsiva e diagnóstico separado.

## 0.1.1 — Migração segura

- backup, restauração, releases versionadas e atualizador.

## 0.1.0 — Fundação

- modelos, Layout Engine, Workspace Engine, adaptadores, testes e CI.

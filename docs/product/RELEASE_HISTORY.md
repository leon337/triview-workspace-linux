# Histórico de versões

Este documento explica a evolução do produto em linguagem de produto. O `CHANGELOG.md` permanece como registro técnico.

## Linha do tempo

```text
Ideia inicial: organizar três janelas do Brave
        ↓
0.1.0: fundação modular
        ↓
0.1.1: migração e atualização segura
        ↓
0.1.2: primeira interface gráfica
        ↓
LEA-194: consolidação documental
        ↓
0.2.0: Browser Engine validado em X11
        ↓
0.3.0: workspaces persistentes validados
        ↓
0.4.0: Application Engine em candidato isolado
        ↓
Trem LEA-198–205
```

## `0.1.0` — Fundação modular

A ideia de abrir três navegadores evoluiu para uma plataforma de workspaces.

Entregas:

- modelos de workspace, layout e painel;
- Layout Engine e Workspace Engine;
- registro de adaptadores;
- testes e CI.

Rastreabilidade: LEA-191 / PR #1.

## `0.1.1` — Migração segura

Criou a passagem da instalação legada para a arquitetura modular.

Entregas:

- backup integral;
- preservação de configurações;
- releases versionadas e link `current`;
- restaurador e atualizador.

Rastreabilidade: LEA-192 / PR #2.

## `0.1.2` — Primeira interface gráfica

Entregou a janela desktop responsiva e separou a GUI do diagnóstico.

Rastreabilidade: LEA-193 / PR #3.

## Consolidação documental — LEA-194

Criou visão, princípios, roadmap, histórico, documentação arquitetural e manual da Fábrica de Softwares.

Rastreabilidade: LEA-194 / PR #4.

## `0.2.0` — Browser Engine

Transformou painéis navegador em hosts de conteúdo web real.

Entregas:

- `BrowserEngine` e `BrowserPanelAdapter`;
- Brave/Chromium em modo aplicativo;
- incorporação X11 com `xdotool`;
- perfis separados por painel;
- redimensionamento, reabertura e encerramento;
- fallback e estados visuais.

Aceite em 25/07/2026:

- ChatGPT e GitHub funcionaram simultaneamente;
- maximizar, restaurar e redimensionar preservaram os painéis.

Rastreabilidade: LEA-195 / PRs #5 e #6.

## `0.3.0` — Workspaces persistentes

Substituiu a configuração fixa por um catálogo local versionado.

Entregas:

- `WorkspaceRepository` e `WorkspaceSessionEngine`;
- gravação atômica e recuperação de corrupção;
- criação, cópia, renomeação, edição e exclusão;
- seleção de layouts;
- restauração automática do último workspace;
- dados separados das releases.

Aceite em 25/07/2026:

- criação, renomeação, alternância e edição confirmadas;
- último workspace restaurado após reiniciar;
- tipos ainda não implementados permaneceram corretamente marcados como planejados.

Rastreabilidade: LEA-196 / PR #7.

## `0.4.0` — Application Engine

Status: candidato do trem, ainda não promovido à `main`.

Objetivo: executar aplicações Linux reais em painéis, sem duplicar a lógica de processo e janela em cada Engine.

Entregas preparadas:

- `PanelRuntime` comum;
- execução de comandos sem shell;
- `ApplicationPanelAdapter` e `ApplicationEngine`;
- backend inicial X11;
- localização de janela por PID e pistas de classe/nome;
- incorporação quando compatível;
- fallback explícito para janela externa;
- redimensionamento, reabertura e encerramento;
- candidato isolado com dados próprios;
- testes e ADR-0005.

Limites:

- algumas aplicações não aceitam reparenting;
- Wayland nativo permanece posterior;
- Terminal e PDF reutilizarão a fundação nas LEAs seguintes;
- promoção depende de CI e teste no Linux Mint.

Rastreabilidade: LEA-197 / branch própria / trem `train/road-to-1.0`.

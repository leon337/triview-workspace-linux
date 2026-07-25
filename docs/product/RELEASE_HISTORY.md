# Histórico de versões

Este documento explica a evolução do produto em linguagem de produto. O `CHANGELOG.md` permanece como registro técnico das alterações por versão.

## Linha do tempo

```text
Ideia inicial: organizar três janelas do Brave
        ↓
0.1.0: fundação modular de workspaces
        ↓
0.1.1: migração e atualização segura
        ↓
0.1.2: primeira interface gráfica real
        ↓
LEA-194: consolidação estratégica e documental
        ↓
0.2.0: primeiro Browser Engine funcional em X11
        ↓
Próximo marco: workspaces persistentes
```

## `0.1.0` — Fundação modular

A ideia inicial de abrir três navegadores evoluiu para uma plataforma de workspaces. Foram criados os contratos centrais de domínio e os primeiros Engines.

Entregas principais:

- `WorkspaceSpec`, `LayoutSpec` e `PanelSpec`;
- Layout Engine baseado em proporções;
- Workspace Engine para orquestração;
- registro de adaptadores de painel;
- configuração inicial com três painéis móveis;
- testes automatizados e CI.

Limite da versão: ainda não existia uma janela gráfica funcional nem incorporação real de aplicações.

Rastreabilidade:

- Linear: LEA-191;
- GitHub: PR #1.

## `0.1.1` — Migração segura

A fundação modular alterou a estrutura do projeto e tornou o atualizador legado incompatível. Esta versão criou uma passagem segura entre as duas arquiteturas.

Entregas principais:

- detecção da instalação antiga;
- backup integral;
- preservação de URLs em `~/.config/triview-workspace/config.json`;
- instalação em diretórios versionados;
- link atômico `current`;
- restaurador do backup mais recente;
- novo atualizador.

Limite da versão: o atalho principal ainda executava a CLI de diagnóstico e encerrava sem manter uma janela aberta.

Rastreabilidade:

- Linear: LEA-192;
- GitHub: PR #2.

## `0.1.2` — Primeira interface gráfica

Esta versão corrigiu o comportamento do atalho e entregou a primeira casca gráfica funcional.

Entregas principais:

- janela desktop em Tkinter;
- três painéis móveis responsivos;
- recálculo do layout ao maximizar, restaurar e redimensionar;
- cabeçalho e estado visual dos painéis;
- CLI de diagnóstico separada;
- launcher gráfico sem terminal.

Limite da versão: os painéis ainda exibiam placeholders. Brave, GitHub e Terminal não estavam incorporados dentro deles.

Rastreabilidade:

- Linear: LEA-193;
- GitHub: PR #3.

## Consolidação documental — LEA-194

A LEA-194 não alterou a versão funcional do aplicativo. Ela criou a documentação estratégica e operacional necessária para orientar os próximos marcos sem confundir funcionalidades concluídas com planos futuros.

Entregas:

- visão e princípios do produto;
- roadmap;
- índice documental;
- responsabilidades dos Engines;
- manual da Fábrica de Softwares;
- governança da documentação.

Rastreabilidade:

- Linear: LEA-194;
- GitHub: PR #4.

## `0.2.0` — Primeiro Browser Engine funcional

Esta versão transforma os painéis navegador de placeholders em hosts capazes de abrir conteúdo web real em sessões X11 compatíveis.

Entregas principais:

- contrato `BrowserBackend` independente de Tkinter e do domínio;
- `BrowserEngine` para abertura, redimensionamento, reabertura e encerramento;
- `BrowserPanelAdapter` integrado ao registro de painéis;
- normalização e restrição de URLs a HTTP e HTTPS;
- backend inicial para Brave, Chromium ou Google Chrome compatível;
- execução em modo aplicativo;
- incorporação da janela com `xdotool windowreparent`;
- perfis separados por painel;
- estados visuais e mensagens de indisponibilidade;
- testes headless de contratos, URL, ciclo de vida e fallback;
- ADR-0003 sobre a decisão X11.

Limites da versão:

- exige sessão com `DISPLAY`;
- exige navegador Chromium compatível e `xdotool`;
- não fornece backend nativo de Wayland;
- persistência avançada de autenticação e sessões pertence ao futuro Session Engine;
- a incorporação visual precisa ser validada no Linux Mint real.

Rastreabilidade:

- Linear: LEA-195;
- GitHub: PR #5.

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
0.2.0: primeiro Browser Engine funcional e validado em X11
        ↓
0.3.0: workspaces persistentes e restauração automática
        ↓
Próximo marco: captura individual por painel
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

Rastreabilidade: Linear LEA-191 / GitHub PR #1.

## `0.1.1` — Migração segura

A fundação modular alterou a estrutura do projeto e tornou o atualizador legado incompatível. Esta versão criou uma passagem segura entre as duas arquiteturas.

Entregas principais:

- detecção da instalação antiga;
- backup integral;
- preservação de URLs;
- instalação em diretórios versionados;
- link atômico `current`;
- restaurador do backup mais recente;
- novo atualizador.

Rastreabilidade: Linear LEA-192 / GitHub PR #2.

## `0.1.2` — Primeira interface gráfica

Esta versão corrigiu o comportamento do atalho e entregou a primeira casca gráfica funcional.

Entregas principais:

- janela desktop em Tkinter;
- três painéis móveis responsivos;
- recálculo do layout;
- cabeçalho e estado visual dos painéis;
- CLI de diagnóstico separada;
- launcher gráfico sem terminal.

Rastreabilidade: Linear LEA-193 / GitHub PR #3.

## Consolidação documental — LEA-194

A LEA-194 não alterou a versão funcional do aplicativo. Ela criou a documentação estratégica e operacional necessária para orientar os próximos marcos.

Entregas:

- visão e princípios do produto;
- roadmap;
- índice documental;
- responsabilidades dos Engines;
- manual da Fábrica de Softwares;
- governança da documentação.

Rastreabilidade: Linear LEA-194 / GitHub PR #4.

## `0.2.0` — Primeiro Browser Engine funcional

Esta versão transformou os painéis navegador de placeholders em hosts capazes de abrir conteúdo web real em sessões X11 compatíveis.

Entregas principais:

- contrato `BrowserBackend`;
- `BrowserEngine` para ciclo de vida;
- `BrowserPanelAdapter`;
- normalização de URLs HTTP/HTTPS;
- backend Brave/Chromium em X11;
- incorporação com `xdotool windowreparent`;
- perfis separados por painel;
- estados visuais e fallback;
- testes headless e ADR-0003.

Validação de aceite:

- executada no Linux Mint em 25/07/2026;
- ChatGPT e GitHub funcionaram simultaneamente em painéis independentes;
- maximização, restauração e redimensionamento preservaram os limites.

Rastreabilidade: Linear LEA-195 / GitHub PRs #5 e #6.

## `0.3.0` — Workspaces persistentes

Esta versão transforma a configuração fixa em um catálogo local de áreas de trabalho que pode evoluir sem perder o estado do usuário.

Entregas principais:

- `WorkspaceRepository` com catálogo JSON versionado;
- `schema_version` explícito;
- gravação atômica com `os.replace`;
- restauração automática do último workspace ativo;
- criação de workspace por cópia;
- renomeação, edição e exclusão;
- edição dos títulos, tipos e destinos dos painéis;
- seleção de layouts disponíveis;
- `WorkspaceSessionEngine` independente de Tkinter;
- migração automática do bundle único legado;
- quarentena de JSON corrompido com restauração segura do padrão;
- catálogo em `XDG_DATA_HOME`, separado do código versionado;
- diagnóstico com catálogo, esquema e workspace ativo;
- testes de persistência, migração, recuperação e sessão.

Limites da versão:

- não persiste automaticamente cookies ou processos de navegador abertos;
- não cria layouts novos pela interface, apenas seleciona os disponíveis;
- captura, gravação, Application Engine e plugins permanecem posteriores;
- exige validação visual final no Linux Mint após atualização.

Rastreabilidade: Linear LEA-196 / pull request da LEA-196.

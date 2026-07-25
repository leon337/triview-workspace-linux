# Responsabilidades dos Engines

Este documento separa componentes existentes de componentes planejados. A palavra **implementado** indica código presente e integrado; **planejado** indica direção arquitetural ainda não entregue.

## Visão geral

```text
Interface gráfica / CLI
          ↓
Workspace Engine
   ├── Layout Engine
   ├── Panel Registry / adapters
   │      ├── Browser Adapter     [implementado]
   │      └── demais adapters     [planejados]
   ├── Browser Engine             [implementado em X11]
   ├── Session Engine             [planejado]
   ├── Capture Engine             [planejado]
   └── Plugin Engine              [planejado]
          ↓
Configuração, persistência, sistema gráfico e sistema operacional
```

## Workspace Engine

Status: **implementado na fundação**

Responsabilidades:

- receber um workspace e um layout;
- verificar compatibilidade entre número de painéis e slots;
- solicitar os limites calculados ao Layout Engine;
- localizar o adaptador adequado para cada painel;
- produzir a representação preparada para execução.

Não deve:

- desenhar diretamente a interface;
- executar comandos específicos de navegador;
- capturar tela;
- persistir sessões por conta própria.

## Layout Engine

Status: **implementado**

Responsabilidades:

- converter regiões normalizadas em retângulos de pixels;
- recalcular o layout para a dimensão atual da área útil;
- preservar proporção visual opcional;
- manter layouts independentes de resolução fixa.

Não deve:

- iniciar aplicações;
- controlar cookies ou sessões;
- gravar tela;
- decidir qual conteúdo pertence ao painel.

Próximas evoluções planejadas:

- breakpoints responsivos;
- ocupação maior da área maximizada;
- múltiplos layouts configuráveis;
- editor ou seletor de layout.

## Panel Registry e adaptadores

Status: **registro e Browser Adapter implementados; demais adaptadores planejados**

Responsabilidades:

- associar um tipo de painel ao adaptador compatível;
- proteger o domínio de detalhes de Brave, terminal, X11 ou Wayland;
- produzir solicitações de abertura ou incorporação;
- informar indisponibilidade de forma controlada.

Adaptadores:

- Browser Adapter: **implementado**;
- Application Adapter: **planejado**;
- Terminal Adapter: **planejado**;
- PDF Adapter: **planejado**;
- Custom/Plugin Adapter: **planejado**.

O `BrowserPanelAdapter` valida o alvo e produz uma solicitação neutra. Ele não executa processos e não conhece widgets Tkinter.

## Interface gráfica

Status: **implementada com Browser Engine inicial na versão 0.2.0**

Responsabilidades atuais:

- manter uma janela desktop aberta;
- exibir os painéis preparados;
- reagir ao redimensionamento;
- apresentar título, alvo e estado;
- oferecer abertura de painéis navegador compatíveis;
- reservar ações de print e gravação;
- manter fallback visual quando o backend não estiver disponível;
- solicitar encerramento das sessões ao fechar a janela.

Limites atuais:

- painéis de aplicação, terminal e PDF continuam como placeholders;
- print e gravação permanecem desativados;
- a incorporação de navegador depende do backend X11 inicial.

## Browser Engine

Status: **implementado inicialmente para X11 na versão 0.2.0**

Componentes:

- `BrowserEngine`: gerencia ciclo de vida das sessões;
- `BrowserBackend`: contrato para backends substituíveis;
- `BrowserPanelAdapter`: prepara metadados de abertura;
- `X11BraveBrowserBackend`: implementação inicial para Brave/Chromium;
- `BrowserBackendAvailability`: diagnóstico sem iniciar processos;
- normalizador de URLs HTTP e HTTPS.

Responsabilidades:

- validar e normalizar a URL do painel;
- verificar disponibilidade do backend;
- criar perfil local separado por painel;
- iniciar o navegador em modo aplicativo;
- incorporar a janela no host nativo do painel;
- redimensionar a janela junto com o painel;
- reabrir ou encerrar uma sessão;
- comunicar falhas sem derrubar a interface.

Backend X11 inicial:

```text
Painel Tkinter
     ↓ fornece winfo_id()
Browser Engine
     ↓ inicia Brave/Chromium --app
xdotool search
     ↓ localiza a janela X11
xdotool windowreparent
     ↓
Janela do navegador incorporada no painel
```

Requisitos:

- variável `DISPLAY` disponível;
- Brave, Chromium ou Google Chrome compatível;
- `xdotool`.

Limites:

- não é uma solução nativa de Wayland;
- a incorporação depende do comportamento do navegador e do gerenciador de janelas;
- autenticação avançada e restauração de sessões pertencem ao Session Engine;
- a CI valida contratos e fallback, mas a incorporação visual exige validação no Linux Mint real.

A decisão está registrada na [ADR-0003](../decisions/ADR-0003-browser-x11-reparenting.md).

## Application Engine

Status: **planejado**

Responsabilidades esperadas:

- iniciar aplicações Linux;
- avaliar se a aplicação aceita incorporação;
- controlar fallback para janela externa;
- acompanhar processo e encerramento;
- comunicar estado ao painel.

## Session Engine

Status: **planejado**

Responsabilidades esperadas:

- salvar e restaurar workspace ativo;
- manter configuração dos painéis;
- gerenciar perfis e sessões quando suportados;
- recuperar estado após encerramento inesperado;
- versionar dados persistidos.

## Capture Engine

Status: **planejado**

Responsabilidades esperadas:

- receber identidade e limites do painel;
- capturar imagem somente da área ou superfície correspondente;
- iniciar e encerrar gravação individual;
- produzir metadados de arquivo;
- organizar capturas por workspace, painel e data;
- selecionar backend compatível com X11 ou Wayland.

Não deve:

- decidir o layout;
- alterar o conteúdo do painel;
- armazenar configurações de sessão.

## Plugin Engine

Status: **planejado**

Responsabilidades esperadas:

- descobrir plugins permitidos;
- verificar versão e compatibilidade;
- registrar novos adaptadores de forma controlada;
- isolar falhas de plugin;
- impedir carregamento silencioso de componentes não confiáveis.

## Persistência

Status: **configuração JSON inicial implementada; gestão completa planejada**

Responsabilidades esperadas:

- armazenar workspaces e layouts;
- manter versão de esquema;
- aplicar migrações compatíveis;
- preservar dados durante atualização;
- suportar backup e restauração.

## Regras de dependência

1. A interface chama os Engines, não o contrário.
2. Layout não executa aplicações.
3. Adaptadores não definem o modelo persistente.
4. Backends específicos do sistema operacional implementam contratos neutros.
5. Captura não altera layout nem sessão.
6. Persistência não deve conhecer widgets gráficos.
7. Integrações X11 ou Wayland permanecem isoladas em backends ou adaptadores.

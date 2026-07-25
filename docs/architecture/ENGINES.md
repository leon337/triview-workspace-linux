# Responsabilidades dos Engines

Este documento separa componentes validados, candidatos e planejados.

## Visão geral

```text
Interface gráfica / CLI
          ↓
Workspace Session Engine ── Workspace Repository
          ↓
Workspace Engine
   ├── Layout Engine
   ├── Panel Registry
   │      ├── Browser Adapter       [validado]
   │      ├── Application Adapter   [candidato]
   │      └── demais adapters       [planejados]
   ├── Browser Engine               [validado X11]
   ├── Application Engine           [candidato]
   │      └── Panel Runtime         [candidato]
   ├── Capture / Recording          [planejados]
   └── Plugin Engine                [planejado]
```

## Workspace Engine

Status: **validado**

- combina workspace e layout;
- verifica compatibilidade entre painéis e slots;
- resolve cada painel no Panel Registry;
- produz `RuntimePanel` sem executar processos.

## Workspace Session Engine

Status: **validado na versão 0.3.0**

- mantém e alterna o workspace ativo;
- cria cópias, renomeia, edita e exclui;
- troca layouts compatíveis;
- delega persistência ao Repository.

## Workspace Repository

Status: **validado na versão 0.3.0**

- catálogo JSON com `schema_version`;
- gravação atômica;
- restauração do último workspace;
- migração e recuperação de corrupção;
- dados em `XDG_DATA_HOME`.

## Layout Engine

Status: **validado na fundação**

- converte regiões normalizadas em pixels;
- reage ao redimensionamento;
- preserva proporções opcionais;
- não executa aplicações.

Editor avançado e breakpoints pertencem à LEA-203.

## Panel Registry

Status: **Browser Adapter validado; Application Adapter em candidato**

- associa `PanelKind` a adaptadores;
- mantém o domínio independente de X11, Brave e programas Linux;
- produz solicitações neutras de abertura;
- usa placeholder para tipos ainda não implementados.

Adaptadores:

- Browser: validado;
- Application: implementado na LEA-197, aguardando aceite;
- Terminal: LEA-198;
- PDF: LEA-199;
- Custom/Plugin: LEA-202.

## Browser Engine

Status: **validado no Linux Mint/X11**

- normaliza URLs HTTP/HTTPS;
- cria perfis separados;
- inicia Brave/Chromium;
- incorpora com `xdotool`;
- redimensiona, reabre e encerra.

Decisão: [ADR-0003](../decisions/ADR-0003-browser-x11-reparenting.md).

## Panel Runtime

Status: **implementado no candidato LEA-197**

Fundação comum para painéis baseados em processos e janelas.

Responsabilidades:

- dividir comandos sem shell;
- resolver e validar executáveis;
- iniciar processo em sessão própria;
- localizar janela X11 por PID, classe ou nome;
- incorporar com `windowreparent`;
- redimensionar e encerrar;
- manter fallback externo explícito.

O runtime não conhece Tkinter, workspaces persistidos ou tipos específicos de aplicação.

## Application Engine

Status: **implementado no candidato 0.4.0; aguardando Linux Mint**

- valida disponibilidade por comando;
- abre aplicações configuradas pelo usuário;
- mantém uma sessão por painel;
- substitui sessão anterior ao reabrir;
- usa Panel Runtime para incorporação ou fallback;
- comunica estado incorporado ou externo à GUI.

Fluxo:

```text
PanelSpec(application)
        ↓
Application Adapter
        ↓
Application Engine
        ↓
Panel Runtime X11
   ├── janela incorporada
   └── fallback externo
```

Decisão: [ADR-0005](../decisions/ADR-0005-application-engine-panel-runtime.md).

## Interface gráfica

Status: **Application Engine integrado no candidato**

Estados suportados:

- `DISPONÍVEL`;
- `ABRINDO`;
- `ATIVO`;
- `EXTERNO`;
- `INDISPONÍVEL`;
- `ERRO`;
- `PLANEJADO`.

Ao trocar de workspace ou fechar a janela, Browser e Application Engines encerram as sessões que iniciaram.

## Engines planejados

### Terminal Engine — LEA-198

Reutilizará o Panel Runtime com shell configurável.

### PDF Engine — LEA-199

Validará arquivos e reutilizará o Panel Runtime para visualizadores compatíveis.

### Capture Engine — LEA-200

Capturará somente o alvo do painel e organizará arquivos por workspace, painel e data.

### Recording Engine — LEA-201

Controlará gravação individual e processos de backend.

### Plugin Engine — LEA-202

Usará API versionada, diretórios permitidos e isolamento de falhas.

### Layout Engine avançado — LEA-203

Adicionará breakpoints, modelos predefinidos e editor visual.

### Session Engine completo — LEA-204

Persistirá estado operacional suportado por tipo de painel.

### Workspace Hub — LEA-205

Organizará templates, importação, exportação, busca e favoritos.

## Regras de dependência

1. A interface chama Engines, nunca o contrário.
2. Adaptadores preparam solicitações e não iniciam processos.
3. Panel Runtime não conhece modelos persistidos nem widgets.
4. Comandos não são executados através de shell.
5. Persistência não conhece X11 ou processos.
6. Backends específicos implementam contratos neutros.
7. Candidatos não usam os dados da versão principal.

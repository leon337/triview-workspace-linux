# Responsabilidades dos Engines

Este documento separa componentes implementados de componentes planejados.

## Visão geral

```text
Interface gráfica / CLI
          ↓
Workspace Session Engine ── Workspace Repository
          ↓                         ↓
Workspace Engine          catálogo JSON versionado
   ├── Layout Engine
   ├── Panel Registry / adapters
   │      ├── Browser Adapter     [implementado]
   │      └── demais adapters     [planejados]
   ├── Browser Engine             [implementado em X11]
   ├── Capture Engine             [planejado]
   └── Plugin Engine              [planejado]
```

## Workspace Engine

Status: **implementado**

Responsabilidades:

- receber um workspace e um layout;
- verificar compatibilidade entre painéis e slots;
- solicitar limites ao Layout Engine;
- localizar o adaptador de cada painel;
- produzir a representação preparada para execução.

Não persiste sessões, não desenha a interface e não executa comandos específicos de navegador.

## Workspace Session Engine

Status: **implementado na versão 0.3.0**

Responsabilidades:

- manter o workspace ativo da sessão;
- alternar entre workspaces persistidos;
- criar cópias com identificadores seguros;
- renomear o workspace atual;
- atualizar os painéis;
- alterar o layout quando compatível;
- excluir o workspace atual sem permitir catálogo vazio;
- delegar gravação ao `WorkspaceRepository`.

O Engine não conhece widgets Tkinter nem o formato físico do arquivo JSON.

## Workspace Repository

Status: **implementado na versão 0.3.0**

Local padrão:

```text
$XDG_DATA_HOME/triview-workspace/workspaces.json
```

Quando `XDG_DATA_HOME` não existe:

```text
~/.local/share/triview-workspace/workspaces.json
```

Responsabilidades:

- manter `schema_version` explícito;
- armazenar layouts, workspaces e `active_workspace_id`;
- gravar por arquivo temporário e substituição atômica;
- restaurar o último workspace utilizado;
- migrar o bundle único legado;
- validar referências entre workspace e layout;
- preservar JSON corrompido em arquivo de quarentena;
- restaurar o workspace padrão após corrupção recuperável;
- manter os dados separados dos diretórios versionados do código.

Formato resumido:

```json
{
  "schema_version": 1,
  "active_workspace_id": "development-demo",
  "layouts": [],
  "workspaces": []
}
```

## Layout Engine

Status: **implementado**

Responsabilidades:

- converter regiões normalizadas em retângulos de pixels;
- recalcular o layout para a área útil atual;
- preservar proporção visual opcional;
- manter layouts independentes de resolução fixa.

A versão 0.3.0 permite selecionar layouts já registrados no catálogo. A criação e edição gráfica completa de layouts permanece planejada.

## Panel Registry e adaptadores

Status: **registro e Browser Adapter implementados**

Responsabilidades:

- associar um tipo de painel ao adaptador compatível;
- proteger o domínio de detalhes de Brave, terminal, X11 ou Wayland;
- produzir solicitações de abertura;
- informar indisponibilidade de forma controlada.

Adaptadores:

- Browser Adapter: **implementado**;
- Application Adapter: **planejado**;
- Terminal Adapter: **planejado**;
- PDF Adapter: **planejado**;
- Custom/Plugin Adapter: **planejado**.

## Interface gráfica

Status: **implementada com Browser Engine e gerenciamento persistente na versão 0.3.0**

Responsabilidades atuais:

- exibir painéis responsivos;
- abrir painéis navegador compatíveis;
- selecionar workspaces e layouts;
- criar uma cópia do workspace atual;
- renomear e excluir workspaces;
- editar título, tipo e destino dos painéis;
- apresentar recuperação de catálogo corrompido;
- encerrar navegadores ao trocar de workspace ou fechar a janela.

Limites atuais:

- aplicações, terminal e PDF continuam como placeholders;
- print e gravação permanecem desativados;
- não existe editor completo de slots de layout;
- a incorporação do navegador usa o backend X11 inicial.

## Browser Engine

Status: **implementado e validado em X11 na versão 0.2.0**

Componentes:

- `BrowserEngine`;
- `BrowserBackend`;
- `BrowserPanelAdapter`;
- `X11BraveBrowserBackend`;
- `BrowserBackendAvailability`;
- normalizador de URLs HTTP/HTTPS.

Fluxo:

```text
Painel Tkinter
     ↓ fornece winfo_id()
Browser Engine
     ↓ inicia Brave/Chromium --app
xdotool search
     ↓ localiza a janela X11
xdotool windowreparent
     ↓
Janela incorporada no painel
```

Requisitos:

- `DISPLAY` disponível;
- navegador Chromium compatível;
- `xdotool`.

Limite: não existe backend nativo de Wayland.

A decisão está registrada na [ADR-0003](../decisions/ADR-0003-browser-x11-reparenting.md).

## Application Engine

Status: **planejado**

- iniciar aplicações Linux;
- avaliar incorporação;
- controlar fallback para janela externa;
- acompanhar processo e encerramento;
- comunicar estado ao painel.

## Capture Engine

Status: **planejado**

- capturar apenas a área ou superfície do painel;
- produzir metadados;
- organizar arquivos por workspace, painel e data;
- selecionar backend X11 ou Wayland.

## Plugin Engine

Status: **planejado**

- descobrir plugins permitidos;
- verificar versão e compatibilidade;
- registrar adaptadores;
- isolar falhas;
- impedir carregamento silencioso de componentes não confiáveis.

## Regras de dependência

1. A interface chama Engines, não o contrário.
2. O Session Engine usa o Repository por contrato, sem conhecer JSON.
3. Persistência não conhece widgets gráficos.
4. Layout não executa aplicações.
5. Adaptadores não definem o modelo persistente.
6. Backends do sistema operacional implementam contratos neutros.
7. Captura não altera layout nem sessão.

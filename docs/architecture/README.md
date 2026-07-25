# Arquitetura da plataforma

> Índice geral: [Documentação do TriView Workspace](../README.md)  
> Responsabilidades detalhadas: [Engines](ENGINES.md)

## Princípio central

O núcleo gerencia **áreas de trabalho**, não programas específicos. Navegadores, aplicações, terminais, PDFs e plugins são tipos de painel resolvidos por adaptadores e Engines substituíveis.

## Camadas

```text
CLI / Interface gráfica
          ↓
Workspace Session Engine ── Workspace Repository ── catálogo versionado
          ↓
Workspace Engine
   ├── Layout Engine
   └── Panel Registry
          ├── Browser Adapter ── Browser Engine ── Backend X11 de navegador
          ├── Application Adapter ── Application Engine
          │                              ↓
          │                         Panel Runtime X11
          ├── Terminal Adapter                         [LEA-198]
          ├── PDF Adapter                              [LEA-199]
          └── Plugin Adapter                           [LEA-202]
```

## Componentes validados

### Workspace Session Engine e Repository

Mantêm o workspace ativo, catálogo JSON versionado, gravação atômica, recuperação de corrupção e operações de criação, edição, alternância e exclusão.

### Workspace Engine e Layout Engine

Preparam os painéis e convertem regiões proporcionais em limites de pixels sem iniciar processos.

### Browser Engine

Gerencia sessões web incorporadas com Brave/Chromium, X11 e `xdotool`. Foi validado no Linux Mint.

## Componentes do candidato LEA-197

### Panel Runtime

Camada reutilizável para painéis que executam processos Linux. Suas responsabilidades são:

- validar e resolver o executável;
- dividir argumentos sem entregar a entrada a um shell;
- iniciar e acompanhar o processo;
- localizar a janela X11 por PID, classe ou nome;
- incorporar a janela quando compatível;
- redimensionar e encerrar a sessão;
- manter fallback externo explícito.

O Panel Runtime não conhece Tkinter, workspaces persistidos ou regras específicas de aplicações.

### Application Engine

Gerencia uma sessão de aplicação por painel e usa o Panel Runtime para abrir, incorporar, redimensionar, reabrir e encerrar programas. Aplicações incompatíveis permanecem em uma janela externa controlada.

A decisão está registrada na [ADR-0005](../decisions/ADR-0005-application-engine-panel-runtime.md).

## Persistência e candidatos

A versão principal usa:

```text
~/.local/share/triview-workspace/workspaces.json
```

Candidatos do trem usam código, dados e estado separados:

```text
~/.local/share/triview-workspace-candidates/<lea>
~/.local/share/triview-workspace-candidate-data/<lea>
~/.local/state/triview-workspace-candidates/<lea>
```

Isso permite validar uma LEA sem modificar a versão estável.

## Estado da implementação

- Browser Engine: **validado em X11**;
- workspaces persistentes: **validados**;
- Application Engine e Panel Runtime: **implementados no candidato LEA-197**;
- Terminal Engine: **LEA-198**;
- PDF Engine: **LEA-199**;
- Capture Engine: **LEA-200**;
- Recording Engine: **LEA-201**;
- Plugin Engine: **LEA-202**;
- Layout Engine avançado: **LEA-203**;
- Session Engine completo: **LEA-204**;
- Workspace Hub: **LEA-205**;
- backend nativo de Wayland: evolução posterior.

## Regras de evolução

1. A interface chama Engines, nunca o contrário.
2. Adaptadores preparam solicitações, mas não iniciam processos.
3. Layout não executa aplicações.
4. Panel Runtime não conhece persistência ou widgets.
5. Comandos não são executados por shell.
6. Backends do sistema operacional implementam contratos neutros.
7. Candidatos não usam os dados da versão principal.
8. Uma LEA só é promovida após CI e teste real correspondente.

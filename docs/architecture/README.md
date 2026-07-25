# Arquitetura da plataforma

> Índice geral: [Documentação do TriView Workspace](../README.md)  
> Responsabilidades detalhadas: [Engines](ENGINES.md)

## Princípio central

O núcleo gerencia **áreas de trabalho**, não navegadores. Navegadores e aplicações são tipos de painel resolvidos por adaptadores e backends substituíveis.

## Camadas

```text
CLI / Interface gráfica
          ↓
Workspace Engine
   ├── Layout Engine
   └── Panel Registry
          ├── Browser Adapter ──→ Browser Engine ──→ Backend X11
          ├── Application Adapter                 [planejado]
          ├── Terminal Adapter                    [planejado]
          └── futuros adaptadores
          ↓
Configuração, persistência e integrações do sistema operacional
```

## Responsabilidades

### Workspace Engine

Orquestra a preparação de um workspace, verifica a compatibilidade entre workspace e layout e associa cada painel ao adaptador apropriado.

### Layout Engine

Recebe regiões normalizadas entre `0` e `1` e calcula os retângulos em pixels para a dimensão atual da janela. Uma região pode preservar uma proporção visual, como `9:19,5`, sem depender de coordenadas fixas.

### Panel Registry

O `PanelRegistry` desacopla o domínio das tecnologias de incorporação. O Browser Adapter já está implementado; adaptadores futuros podem ser adicionados sem modificar os modelos centrais.

### Browser Engine

Gerencia disponibilidade, abertura, redimensionamento e encerramento de sessões web. A implementação inicial utiliza um backend X11 separado, mantendo comandos de Brave/Chromium e `xdotool` fora do domínio, do Layout Engine e do Workspace Engine.

### Capture Engine

Reservado para uma tarefa posterior. A captura deverá receber a identidade e os limites do painel e produzir print ou gravação somente daquela área.

## Estado da implementação

- Workspace Engine: fundação implementada.
- Layout Engine: implementado e usado pela GUI.
- Panel Registry: implementado com Browser Adapter e fallback placeholder.
- Interface gráfica: Browser Engine inicial integrado na versão `0.2.0`.
- Browser Engine: implementado inicialmente para sessões X11 compatíveis.
- Application, Session, Capture e Plugin Engines: planejados.
- Backend nativo de Wayland: planejado.

Consulte [Responsabilidades dos Engines](ENGINES.md) para a separação completa entre componentes implementados e planejados.

## Regras de evolução

1. Nenhum painel conhece detalhes do gerenciador de janelas.
2. Nenhum layout executa aplicações.
3. Adaptadores não controlam o armazenamento de workspaces.
4. Backends de sistema operacional implementam contratos neutros.
5. Captura e gravação serão serviços independentes.
6. Formatos persistidos devem ser versionados antes de mudanças incompatíveis.
7. Integrações específicas de X11, Wayland, navegador ou terminal permanecem atrás de adaptadores ou backends.

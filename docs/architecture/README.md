# Arquitetura da plataforma

> Índice geral: [Documentação do TriView Workspace](../README.md)  
> Responsabilidades detalhadas: [Engines](ENGINES.md)

## Princípio central

O núcleo gerencia **áreas de trabalho**, não navegadores. Navegadores e aplicações são tipos de painel resolvidos por adaptadores e backends substituíveis.

## Camadas

```text
CLI / Interface gráfica
          ↓
Workspace Session Engine ──→ Workspace Repository ──→ catálogo JSON versionado
          ↓
Workspace Engine
   ├── Layout Engine
   └── Panel Registry
          ├── Browser Adapter ──→ Browser Engine ──→ Backend X11
          ├── Application Adapter                 [planejado]
          ├── Terminal Adapter                    [planejado]
          └── futuros adaptadores
```

## Responsabilidades

### Workspace Session Engine

Mantém o workspace ativo, alterna entre itens persistidos e executa operações de criar por cópia, renomear, editar, excluir e selecionar layout. Não conhece Tkinter nem o formato do arquivo.

### Workspace Repository

Armazena workspaces, layouts e o identificador ativo em um catálogo com `schema_version`. Usa gravação atômica, migra o bundle legado e preserva arquivos corrompidos antes do fallback.

### Workspace Engine

Orquestra a preparação de um workspace, verifica compatibilidade com o layout e associa cada painel ao adaptador apropriado.

### Layout Engine

Converte regiões normalizadas em retângulos de pixels para a dimensão atual da janela.

### Panel Registry

Desacopla o domínio das tecnologias de incorporação. O Browser Adapter está implementado e os demais permanecem planejados.

### Browser Engine

Gerencia disponibilidade, abertura, redimensionamento e encerramento de sessões web. A implementação inicial usa um backend X11 separado.

### Capture Engine

Reservado para tarefa posterior. Deverá produzir print ou gravação somente do painel solicitado.

## Persistência e atualização

O catálogo padrão fica em:

```text
~/.local/share/triview-workspace/workspaces.json
```

ou sob `XDG_DATA_HOME`. O atualizador troca apenas o diretório da versão ativa, portanto o catálogo persiste entre releases. Consulte a [ADR-0004](../decisions/ADR-0004-versioned-workspace-catalog.md).

## Estado da implementação

- Workspace Engine: implementado.
- Workspace Session Engine: implementado na `0.3.0`.
- Workspace Repository: implementado na `0.3.0`.
- Layout Engine: implementado.
- Panel Registry: Browser Adapter e fallback placeholder implementados.
- Interface gráfica: gerenciamento persistente integrado na `0.3.0`.
- Browser Engine: implementado e validado em X11.
- Application, Capture e Plugin Engines: planejados.
- Backend nativo de Wayland: planejado.

## Regras de evolução

1. Nenhum painel conhece detalhes do gerenciador de janelas.
2. Nenhum layout executa aplicações.
3. A interface usa Engines e não grava JSON diretamente.
4. O Session Engine não conhece widgets gráficos.
5. Persistência não conhece Tkinter.
6. Adaptadores não controlam o armazenamento de workspaces.
7. Backends de sistema operacional implementam contratos neutros.
8. Formatos persistidos devem ser versionados antes de mudanças incompatíveis.

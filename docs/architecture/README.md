# Arquitetura da plataforma

> Índice geral: [Documentação do TriView Workspace](../README.md)  
> Responsabilidades detalhadas: [Engines](ENGINES.md)

## Princípio central

O núcleo gerencia **áreas de trabalho**, não navegadores. Navegadores e aplicações são tipos de painel resolvidos por adaptadores.

## Camadas

```text
CLI/UI
  ↓
Workspace Engine
  ├── Layout Engine
  └── Panel Registry
          ├── Browser Adapter
          ├── Application Adapter
          ├── Terminal Adapter
          └── futuros adaptadores
  ↓
Infraestrutura de configuração e persistência
```

## Responsabilidades

### Workspace Engine

Orquestra a preparação de um workspace, verifica a compatibilidade entre workspace e layout e associa cada painel ao adaptador apropriado.

### Layout Engine

Recebe regiões normalizadas entre `0` e `1` e calcula os retângulos em pixels para a dimensão atual da janela. Uma região pode preservar uma proporção visual, como `9:19,5`, sem depender de coordenadas fixas.

### Panel Engine

O `PanelRegistry` desacopla o domínio das tecnologias de incorporação. Adaptadores reais serão adicionados sem modificar os modelos centrais.

### Capture Engine

Reservado para uma tarefa posterior. A captura deverá receber a identidade e os limites do painel e produzir print ou gravação somente daquela área.

## Estado da implementação

- Workspace Engine: fundação implementada.
- Layout Engine: implementado e usado pela GUI.
- Panel Registry: implementado com adaptador placeholder.
- Interface gráfica: casca funcional implementada na versão `0.1.2`.
- Browser, Application, Session, Capture e Plugin Engines: planejados.

Consulte [Responsabilidades dos Engines](ENGINES.md) para a separação completa entre componentes implementados e planejados.

## Regras de evolução

1. Nenhum painel conhece detalhes do gerenciador de janelas.
2. Nenhum layout executa aplicações.
3. Adaptadores não controlam o armazenamento de workspaces.
4. Captura e gravação serão serviços independentes.
5. Formatos persistidos devem ser versionados antes de mudanças incompatíveis.
6. Integrações específicas de X11, Wayland, navegador ou terminal devem permanecer atrás de adaptadores.

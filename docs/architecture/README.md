# Arquitetura da plataforma

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

## Regras de evolução

1. Nenhum painel conhece detalhes do gerenciador de janelas.
2. Nenhum layout executa aplicações.
3. Adaptadores não controlam o armazenamento de workspaces.
4. Captura e gravação serão serviços independentes.
5. Formatos persistidos devem ser versionados antes de mudanças incompatíveis.

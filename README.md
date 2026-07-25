# TriView Workspace Linux

Plataforma modular de áreas de trabalho para Linux.

O produto gerencia **workspaces compostos por painéis independentes**. Navegadores, aplicações, terminais, PDFs e componentes futuros serão resolvidos por adaptadores, sem limitar o núcleo ao caso inicial de três janelas.

## Estado atual

- Versão funcional: `0.1.2`.
- Interface gráfica inicial: disponível.
- Três painéis responsivos: disponíveis.
- Migração, backup, restauração e atualização versionada: disponíveis.
- Navegadores e aplicações incorporados: planejados.
- Print e gravação individual por painel: planejados.
- Consolidação estratégica: LEA-194.

A versão atual é uma **casca gráfica funcional**. Os painéis ainda exibem placeholders e não incorporam Brave, GitHub ou Terminal.

## Documentação

A referência principal do projeto está em:

- [Índice central da documentação](docs/README.md)
- [Visão do produto](docs/product/VISION.md)
- [Roadmap](docs/product/ROADMAP.md)
- [Arquitetura](docs/architecture/README.md)
- [Responsabilidades dos Engines](docs/architecture/ENGINES.md)
- [Manual da Fábrica de Softwares](docs/factory/SOFTWARE_FACTORY_WORKFLOW.md)

## Executar localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
triview-workspace
```

Diagnóstico sem abrir a interface:

```bash
triview-workspace --diagnostic --workspace config/workspaces/three-mobile.json
```

## Estrutura

```text
src/triview_workspace/
├── domain/
├── engines/
├── infrastructure/
├── gui.py
├── gui_model.py
├── migration.py
└── cli.py

config/workspaces/
docs/
packaging/
scripts/
tests/
```

## Migração e atualização

A instalação antiga usa `~/.local/share/triview-workspace-linux`, enquanto as URLs ficam em `~/.config/triview-workspace/config.json`.

O pacote de migração cria backup, preserva as URLs e instala a aplicação em `~/.local/share/triview-workspace`. Após a migração, o atalho **Atualizar TriView Workspace** obtém a versão validada do GitHub, mantém backup da versão anterior e atualiza o atalho gráfico principal.

Consulte:

- [Migração](docs/migration.md)
- [Estratégia de atualização](docs/updater.md)

## Rastreabilidade

- Fundação modular: LEA-191 / PR #1.
- Migração segura: LEA-192 / PR #2.
- Interface gráfica inicial: LEA-193 / PR #3.
- Documentação estratégica: LEA-194.

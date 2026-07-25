# TriView Workspace Linux

Plataforma modular de áreas de trabalho para Linux.

O produto gerencia **workspaces compostos por painéis independentes**. Navegadores, aplicações, terminais, PDFs e componentes futuros são resolvidos por adaptadores, sem limitar o núcleo ao caso inicial de três janelas.

## Estado atual

- Versão funcional: `0.2.0`.
- Interface gráfica responsiva: disponível.
- Primeiro Browser Engine: disponível em sessões X11 compatíveis.
- Migração, backup, restauração e atualização versionada: disponíveis.
- Application Engine: planejado.
- Print e gravação individual por painel: planejados.
- Plugins e persistência completa de workspaces: planejados.

A versão `0.2.0` permite abrir conteúdo HTTP ou HTTPS dentro de painéis navegador por meio de Brave ou outro navegador Chromium compatível. O backend inicial utiliza X11 e `xdotool`. Quando os requisitos não estão disponíveis, a interface permanece aberta e mostra a causa da indisponibilidade.

## Requisitos do Browser Engine inicial

- Linux com sessão gráfica e variável `DISPLAY`;
- Brave, Chromium ou Google Chrome compatível;
- `xdotool` instalado.

No Linux Mint/Ubuntu, o utilitário pode ser instalado com:

```bash
sudo apt update
sudo apt install xdotool
```

O backend inicial não oferece incorporação nativa em Wayland. Essa evolução permanece separada para evitar acoplamento do núcleo a uma única tecnologia gráfica.

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
│   ├── browser.py
│   ├── layout.py
│   ├── panels.py
│   └── workspace.py
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
- Documentação estratégica: LEA-194 / PR #4.
- Primeiro Browser Engine funcional: LEA-195 / PR #5.

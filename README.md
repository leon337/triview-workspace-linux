# TriView Workspace Linux

Plataforma modular de áreas de trabalho para Linux.

## Estado da liberação

- versão de liberação: `1.0.0a1`;
- interface RC4 proporcional: aprovada no Linux Mint/X11;
- Browser Panels: incorporados em displays Xephyr autenticados, sem exposição externa;
- workspaces vivos: preservam processos, janelas, conversas, rolagem e foco durante a mesma execução;
- scroll e teclado nos navegadores incorporados: aprovados;
- diagnóstico caixa-preta: disponível com coleta sanitizada e pacote único;
- Application, Terminal, PDF, Capture, Recording e Plugin Engines: integrados;
- atualização estável: backup, validação, troca atômica e rollback.

O desempenho de vários workspaces vivos continua acompanhado separadamente. A política de otimização não pode encerrar conversas silenciosamente.

## Workspaces

O catálogo versionado fica em:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/triview-workspace/workspaces.json
```

Alterações são gravadas atomicamente e permanecem fora dos diretórios versionados. A interface permite criar, copiar, renomear, editar, selecionar e excluir workspaces, mantendo sempre ao menos um.

O workspace `Três Agentes GPT` mantém três Browser Panels independentes. Ao alternar para outro workspace e retornar, os mesmos runtimes continuam vivos durante a mesma execução do TriView.

## Requisitos do Browser Engine

No Linux Mint/Ubuntu com sessão X11:

```bash
sudo apt update
sudo apt install xdotool xauth xserver-xephyr x11-utils
```

Também é necessário Brave, Chromium ou Google Chrome compatível.

Cada Browser Panel é iniciado dentro de um Xephyr autenticado e incorporado ao host do TriView antes de ficar visível. Um backend nativo de Wayland permanece fora desta liberação.

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
triview-workspace --diagnostic
```

## Atualização

O controlador oficial usa o canal `stable` quando nenhuma escolha anterior existe:

```bash
bash scripts/update.sh --stable
```

O canal `testing` exige opt-in explícito e manifesto habilitado com commit SHA completo:

```bash
bash scripts/update.sh --testing
```

O manifesto de testes versionado permanece desabilitado depois da liberação. Consulte [a estratégia de atualização](docs/updater.md).

## Documentação

- [Índice central](docs/README.md)
- [Visão do produto](docs/product/VISION.md)
- [Roadmap](docs/product/ROADMAP.md)
- [Histórico de versões](docs/product/RELEASE_HISTORY.md)
- [Arquitetura](docs/architecture/README.md)
- [Responsabilidades dos Engines](docs/architecture/ENGINES.md)
- [Trem LEA-197–205](docs/factory/DEVELOPMENT_TRAIN_LEA-197-205.md)
- [Estratégia de atualização](docs/updater.md)
- [Manual da Fábrica de Softwares](docs/factory/SOFTWARE_FACTORY_WORKFLOW.md)

## Estrutura principal

```text
src/triview_workspace/
├── domain/
├── engines/
├── infrastructure/
├── diagnostic_blackbox.py
├── gui.py
├── gui_rc4.py
├── migration.py
└── cli.py
```

## Rastreabilidade

- LEA-191–205: fundação, Engines e trem de desenvolvimento;
- LEA-226: objetivo estratégico de liberação;
- LEA-229–246: validações físicas, instalador, atalhos e RC4;
- LEA-247–259: scroll, sessões vivas, contenção Xephyr e diagnóstico caixa-preta;
- LEA-260–263: integração no train, reconciliação com main e endurecimento da publicação.

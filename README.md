# TriView Workspace Linux

Plataforma modular de áreas de trabalho para Linux.

## Estado da liberação

- versão de liberação: `1.0.0a3`;
- interface RC4 proporcional: aprovada no Linux Mint/X11;
- Browser Panels: incorporados em displays Xephyr autenticados, sem exposição externa;
- workspaces vivos: preservam processos, janelas, conversas, rolagem e foco durante a mesma execução;
- scroll e teclado nos navegadores incorporados: aprovados;
- diagnóstico caixa-preta: controlador estável, coleta sanitizada e pacote único;
- Application, Terminal, PDF, Capture, Recording e Plugin Engines: integrados;
- atualização estável: backup, validação e troca atômica;
- rollback estável: valida backup controlado, preserva dados, troca `current` atomicamente e gera relatório;
- quatro atalhos estáveis: abrir, atualizar, diagnosticar e restaurar.

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

## Controladores estáveis

A atualização instala controladores versionados em:

```text
~/.local/share/triview-workspace/updater/
```

E os comandos oficiais em:

```text
~/.local/bin/triview-workspace
~/.local/bin/triview-workspace-update
~/.local/bin/triview-workspace-diagnose
~/.local/bin/triview-workspace-rollback
```

O lançador estável garante instância única, tenta ativar a janela existente, verifica dependências X11, registra stdout/stderr e exporta a proveniência disponível do runtime.

O diagnóstico estável inicia uma sessão caixa-preta, acompanha o aplicativo até o encerramento e gera um ZIP sanitizado. Quando a sessão completa falha, produz um pacote de contingência explicitamente não equivalente a PASS.

## Executar localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
triview-workspace
```

Diagnóstico estável:

```bash
triview-workspace-diagnose
```

Diagnóstico estrutural sem abrir a interface:

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

O manifesto de testes versionado permanece desabilitado depois da liberação.

Após uma atualização estável bem-sucedida, o atalho **Restaurar TriView Workspace** e o comando abaixo restauram o backup controlado mais recente sem substituir o catálogo ou os demais dados persistentes:

```bash
triview-workspace-rollback
```

O rollback valida compilação, diagnóstico e módulo principal antes da troca, cria um backup pré-rollback, substitui o link `current` atomicamente e registra relatório auditável. Consulte [a estratégia de atualização](docs/updater.md).

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
- LEA-260–264: integração no train, reconciliação com main, publicação e RC final;
- LEA-265–266: rollback estável verificável e RC da `1.0.0a2`;
- LEA-267: paridade dos controladores estáveis e liberação `1.0.0a3`.

# TriView Workspace Linux

Plataforma modular de áreas de trabalho para Linux.

O produto deixa de ser um simples organizador de três navegadores e passa a gerenciar **workspaces compostos por painéis independentes**. Um painel poderá representar navegador, aplicação, terminal, PDF ou outro tipo acrescentado por adaptadores.

## Estado

- Tarefa atual: [LEA-193](https://linear.app/leandro-carlos/issue/LEA-193/abrir-interface-grafica-real-apos-a-migracao)
- Versão: `0.1.2`
- Repositório: `leon337/triview-workspace-linux`

## Interface gráfica inicial

A versão 0.1.2 corrige o comportamento em que o atalho executava apenas o diagnóstico em JSON e encerrava. O comando principal agora abre uma janela desktop real que permanece visível.

A janela inicial apresenta:

- três painéis móveis responsivos;
- redimensionamento ao maximizar, restaurar ou alterar a janela;
- cabeçalho do workspace e estado de cada painel;
- ações provisórias de abrir, print e gravação, ainda desativadas até seus engines serem implementados.

A incorporação real de Brave, aplicações Linux, captura de imagem e gravação por painel pertence às tarefas seguintes.

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

A instalação antiga usa `~/.local/share/triview-workspace-linux`, enquanto as URLs ficam em `~/.config/triview-workspace/config.json`. O pacote `TriView-Workspace-Migrador-0.1.2.zip` cria backup, preserva as URLs e instala a aplicação em `~/.local/share/triview-workspace`.

Após a migração, o atalho **Atualizar TriView Workspace** obtém a versão validada do GitHub, mantém backup da versão anterior e atualiza o atalho gráfico principal.

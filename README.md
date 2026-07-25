# TriView Workspace Linux

Plataforma modular de áreas de trabalho para Linux.

O produto deixa de ser um simples organizador de três navegadores e passa a gerenciar **workspaces compostos por painéis independentes**. Um painel poderá representar navegador, aplicação, terminal, PDF ou outro tipo acrescentado por adaptadores.

## Estado

- Tarefa atual: [LEA-192](https://linear.app/leandro-carlos/issue/LEA-192/criar-migrador-seguro-da-versao-legada-e-atualizador-oficial)
- Versão: `0.1.1`
- Repositório: `leon337/triview-workspace-linux`

## Fundação disponível

- modelos independentes de workspace, layout e painel;
- Layout Engine baseado em proporções normalizadas;
- Panel Engine extensível por adaptadores;
- Workspace Engine para orquestração;
- configuração de exemplo com três painéis móveis;
- testes automatizados;
- documentação arquitetural e estratégia de atualização.

A incorporação real de Brave, aplicações Linux, captura de imagem e gravação por painel pertence às tarefas seguintes.

## Executar localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
triview-workspace --workspace config/workspaces/three-mobile.json
pytest
```

## Estrutura

```text
src/triview_workspace/
├── domain/
├── engines/
├── infrastructure/
├── migration.py
└── cli.py

config/workspaces/
docs/architecture/
docs/decisions/
packaging/
scripts/
tests/
```

## Migração da versão V0.1.0

A instalação antiga usa `~/.local/share/triview-workspace-linux`, enquanto as URLs ficam em `~/.config/triview-workspace/config.json`. Execute o pacote `TriView-Workspace-Migrador-0.1.1.zip` para criar backup, preservar as URLs e instalar a arquitetura modular em `~/.local/share/triview-workspace`.

O migrador suporta `--dry-run`, não apaga a versão antiga e inclui restauração do backup mais recente. Consulte [`docs/migration.md`](docs/migration.md).

## Atualizações

Após a primeira migração, o novo atualizador instala versões em diretórios separados, valida o código antes de ativá-lo e troca o link `current` somente após sucesso. Consulte [`docs/updater.md`](docs/updater.md).

# TriView Workspace Linux

Plataforma modular de áreas de trabalho para Linux.

O produto deixa de ser um simples organizador de três navegadores e passa a gerenciar **workspaces compostos por painéis independentes**. Um painel poderá representar navegador, aplicação, terminal, PDF ou outro tipo acrescentado por adaptadores.

## Estado

- Tarefa atual: [LEA-191](https://linear.app/leandro-carlos/issue/LEA-191/fundacao-modular-da-plataforma-workspace)
- Versão de fundação: `0.1.0`
- Repositório: `leon337/triview-workspace-linux`

## O que esta fundação entrega

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
└── cli.py

config/workspaces/
docs/architecture/
docs/decisions/
scripts/
tests/
```

## Atualizações

A estratégia está documentada em [`docs/updater.md`](docs/updater.md). O atualizador da primeira distribuição ZIP não deve ser considerado compatível automaticamente enquanto seu conteúdo e seu endereço de origem não forem validados. Esta fundação inclui um novo atualizador preparado para instalações Git e para futuras releases do GitHub.

# TriView Workspace Linux

Plataforma modular de áreas de trabalho para Linux.

O produto gerencia **workspaces compostos por painéis independentes**. Navegadores, aplicações, terminais, PDFs e plugins são resolvidos por adaptadores e Engines separados.

## Estado atual deste candidato

- Versão: `0.4.0`.
- Browser Engine: validado no Linux Mint/X11.
- Workspaces persistentes: validados no Linux Mint.
- Application Engine: implementado na LEA-197 e aguardando teste real.
- Panel Runtime comum: disponível para Application, Terminal e PDF Engines.
- Terminal, PDF, captura, gravação, plugins, layouts avançados, sessões completas e Hub: planejados nas LEAs 198–205.

A branch `main` permanece estável em `0.3.0`. Este código pertence ao trem `train/road-to-1.0` e possui instalador isolado para não alterar a versão principal.

## Application Engine

Um painel do tipo `application` recebe um comando, por exemplo:

```text
xterm
xed
libreoffice --writer
```

O comando é dividido em argumentos e executado sem shell. O backend tenta localizar e incorporar a janela por X11. Quando o programa não aceita incorporação, ele permanece em uma janela externa e o painel mostra o estado **EXTERNO**.

Requisitos para incorporação:

- sessão X11 com `DISPLAY`;
- programa instalado;
- `xdotool`.

Sem `xdotool`, aplicações ainda podem abrir externamente.

## Instalar candidato isolado

O script abaixo instala a LEA-197 em diretórios separados da versão principal:

```bash
bash scripts/install-candidate.sh \
  LEA-197 \
  leonpcsn/lea-197-implementar-application-engine-e-panel-runtime-comum
```

O atalho criado se chama **TriView Workspace — LEA-197**.

Dados do candidato:

```text
~/.local/share/triview-workspace-candidate-data/lea-197
```

## Gerenciar workspaces

A barra superior permite selecionar, copiar, renomear, editar e excluir workspaces, além de restaurar automaticamente o último utilizado.

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

## Documentação

- [Índice central](docs/README.md)
- [Roadmap](docs/product/ROADMAP.md)
- [Histórico de versões](docs/product/RELEASE_HISTORY.md)
- [Arquitetura](docs/architecture/README.md)
- [Responsabilidades dos Engines](docs/architecture/ENGINES.md)
- [Trem LEA-197–205](docs/factory/DEVELOPMENT_TRAIN_LEA-197-205.md)
- [Registro da LEA-197](docs/work/LEA-197.md)

## Estrutura principal

```text
src/triview_workspace/
├── domain/
├── engines/
│   ├── application.py
│   ├── browser.py
│   ├── panel_runtime.py
│   ├── layout.py
│   ├── panels.py
│   ├── session.py
│   └── workspace.py
├── infrastructure/
├── gui.py
├── gui_model.py
└── cli.py
```

## Rastreabilidade

- LEA-191 a LEA-196: fundação, atualização, GUI, documentação, Browser e persistência.
- LEA-197: Application Engine e Panel Runtime comum.
- LEA-198 a LEA-205: branches e tarefas preparadas no trem de desenvolvimento.

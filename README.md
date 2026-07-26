# TriView Workspace Linux

Plataforma modular de áreas de trabalho para Linux.

O produto gerencia **workspaces compostos por painéis independentes**. Navegadores, aplicações, terminais, PDFs e componentes futuros são resolvidos por adaptadores, sem limitar o núcleo ao caso inicial de três janelas.

## Estado atual

- Versão funcional estável: `0.3.1`.
- Interface gráfica responsiva: disponível.
- Browser Engine: validado no Linux Mint/X11.
- Workspaces persistentes: disponíveis.
- Criação, cópia, edição, renomeação, seleção e exclusão: disponíveis.
- Restauração automática do último workspace: disponível.
- Migração, backup, restauração e atualização versionada: disponíveis.
- Canal controlado de testes: preparado e fixado inicialmente na LEA-197.
- Application Engine, captura, gravação e plugins: permanecem fora da `main` até o aceite sequencial.

A versão `0.3.1` mantém o comportamento funcional da `0.3.0` e corrige o atualizador. O catálogo versionado continua em `~/.local/share/triview-workspace/workspaces.json` ou no diretório indicado por `XDG_DATA_HOME`. Alterações são gravadas de forma atômica e sobrevivem às atualizações, porque ficam separadas dos diretórios versionados do código.

## Gerenciar workspaces

A barra superior permite:

- selecionar um workspace salvo;
- criar uma cópia do workspace atual;
- renomear o workspace;
- editar título, tipo e destino dos painéis;
- selecionar layouts disponíveis;
- excluir workspaces, mantendo sempre ao menos um;
- restaurar automaticamente o último workspace utilizado na próxima abertura.

Quando o catálogo JSON está corrompido, o arquivo é preservado com sufixo `corrupt-<data>` e a aplicação restaura o workspace padrão, informando o ocorrido.

## Requisitos do Browser Engine inicial

- Linux com sessão gráfica e variável `DISPLAY`;
- Brave, Chromium ou Google Chrome compatível;
- `xdotool` instalado.

No Linux Mint/Ubuntu:

```bash
sudo apt update
sudo apt install xdotool
```

O backend inicial não oferece incorporação nativa em Wayland.

## Executar localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
triview-workspace
```

Diagnóstico do último workspace persistido, sem abrir a interface:

```bash
triview-workspace --diagnostic
```

Abrir e importar explicitamente um bundle legado:

```bash
triview-workspace --workspace config/workspaces/three-mobile.json
```

Usar um catálogo alternativo para testes:

```bash
triview-workspace --data-file /tmp/triview-workspaces.json
```

## Documentação

- [Índice central](docs/README.md)
- [Visão do produto](docs/product/VISION.md)
- [Estratégia de atualização](docs/updater.md)

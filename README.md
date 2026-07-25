# TriView Workspace Linux

Plataforma modular de áreas de trabalho para Linux.

## Estado deste candidato

- versão candidata: `0.5.0`;
- `main`: estável em `0.3.0`;
- Browser Engine: validado;
- workspaces persistentes: validados;
- Application Engine: candidato LEA-197;
- Terminal Engine: candidato LEA-198;
- PDF, captura, gravação, plugins, layouts avançados, sessões e Hub: LEA-199–205.

## Painéis executáveis

### Browser

Abre conteúdo HTTP/HTTPS em Brave ou Chromium incorporado por X11.

### Application

Executa um programa Linux configurado, por exemplo `xed` ou `libreoffice --writer`. A janela é incorporada quando compatível ou mantida externamente com estado **EXTERNO**.

### Terminal

O destino representa o shell, por exemplo:

```text
bash
bash --noprofile
zsh
```

O Terminal Engine detecta `xterm`, `xfce4-terminal`, `gnome-terminal`, `kitty`, `alacritty` ou `konsole`. A variável `TRIVIEW_TERMINAL` pode priorizar um deles.

## Requisitos X11

```bash
sudo apt update
sudo apt install xdotool
```

Um emulador de terminal também precisa estar instalado. Sem incorporação, Application e Terminal Engines usam fallback externo controlado.

## Instalar o candidato LEA-198

```bash
bash scripts/install-candidate.sh \
  LEA-198 \
  leonpcsn/lea-198-implementar-terminal-engine-incorporado
```

O atalho criado é **TriView Workspace — LEA-198** e usa dados separados da versão principal.

## Executar localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
triview-workspace
```

## Documentação

- [Índice central](docs/README.md)
- [Roadmap](docs/product/ROADMAP.md)
- [Arquitetura](docs/architecture/README.md)
- [Trem LEA-197–205](docs/factory/DEVELOPMENT_TRAIN_LEA-197-205.md)
- [LEA-197](docs/work/LEA-197.md)
- [LEA-198](docs/work/LEA-198.md)

## Rastreabilidade

- LEA-191–196: base validada;
- LEA-197: Application Engine e Panel Runtime;
- LEA-198: Terminal Engine e shell gráfico genérico;
- LEA-199–205: etapas seguintes do trem.

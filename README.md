# TriView Workspace Linux

Plataforma modular de áreas de trabalho para Linux.

## Estado deste candidato

- versão candidata: `0.7.0`;
- `main`: estável em `0.3.0`;
- Browser e workspaces persistentes: validados;
- Application, Terminal e PDF Engines: integrados ao trem;
- Capture Engine: candidato LEA-200;
- Recording, Plugin, Layout, Session e Hub: LEA-201–205.

## Captura por painel

O botão **Print** captura somente a moldura do painel selecionado. O backend inicial usa `maim` ou ImageMagick `import` em X11.

Arquivos:

```text
~/Pictures/TriView Workspace/Captures/<workspace>/<painel>/<data>/<hora>.png
```

Histórico:

```text
~/Pictures/TriView Workspace/Captures/capture-history.jsonl
```

## Instalar o candidato LEA-200

```bash
bash scripts/install-candidate.sh \
  LEA-200 \
  leonpcsn/lea-200-implementar-capture-engine-por-painel
```

O atalho criado é **TriView Workspace — LEA-200** e usa dados separados da versão principal.

## Requisitos

```bash
sudo apt update
sudo apt install xdotool maim
```

Alternativa para captura: `imagemagick`.

## Documentação

- [Índice](docs/README.md)
- [Roadmap](docs/product/ROADMAP.md)
- [Arquitetura](docs/architecture/README.md)
- [Trem LEA-197–205](docs/factory/DEVELOPMENT_TRAIN_LEA-197-205.md)
- [LEA-197](docs/work/LEA-197.md)
- [LEA-198](docs/work/LEA-198.md)
- [LEA-199](docs/work/LEA-199.md)
- [LEA-200](docs/work/LEA-200.md)

## Rastreabilidade

- LEA-191–196: base validada;
- LEA-197–199: painéis executáveis integrados ao trem;
- LEA-200: captura individual;
- LEA-201–205: etapas seguintes.

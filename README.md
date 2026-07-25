# TriView Workspace Linux

Plataforma modular de áreas de trabalho para Linux.

## Estado deste candidato

- versão candidata: `0.6.0`;
- `main`: estável em `0.3.0`;
- Browser e workspaces persistentes: validados;
- Application e Terminal Engines: integrados ao trem;
- PDF Engine: candidato LEA-199;
- Capture, Recording, Plugin, Layout, Session e Hub: LEA-200–205.

## Tipos de painel disponíveis no trem

- `browser`: URL HTTP/HTTPS;
- `application`: comando de programa Linux;
- `terminal`: shell, como `bash`;
- `pdf`: caminho completo de um arquivo local `.pdf`.

O PDF Engine detecta Xreader, Evince, Atril, Okular, Zathura ou MuPDF. O arquivo é incorporado quando o visualizador aceita X11 reparenting; caso contrário, abre como janela **EXTERNA** controlada.

## Instalar o candidato LEA-199

```bash
bash scripts/install-candidate.sh \
  LEA-199 \
  leonpcsn/lea-199-implementar-pdf-engine-incorporado
```

O atalho criado é **TriView Workspace — LEA-199** e usa dados separados da versão principal.

## Requisitos

```bash
sudo apt update
sudo apt install xdotool
```

Também é necessário um visualizador PDF instalado para painéis `pdf`.

## Documentação

- [Índice](docs/README.md)
- [Roadmap](docs/product/ROADMAP.md)
- [Arquitetura](docs/architecture/README.md)
- [Trem LEA-197–205](docs/factory/DEVELOPMENT_TRAIN_LEA-197-205.md)
- [LEA-197](docs/work/LEA-197.md)
- [LEA-198](docs/work/LEA-198.md)
- [LEA-199](docs/work/LEA-199.md)

## Rastreabilidade

- LEA-191–196: base validada;
- LEA-197: Application Engine e Panel Runtime;
- LEA-198: Terminal Engine e shell genérico;
- LEA-199: PDF Engine;
- LEA-200–205: etapas seguintes.

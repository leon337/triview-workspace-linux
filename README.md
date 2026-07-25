# TriView Workspace Linux

Plataforma modular de áreas de trabalho para Linux.

## Estado deste candidato

- versão candidata: `0.8.0`;
- `main`: estável em `0.3.0`;
- Browser e workspaces persistentes: validados;
- Application, Terminal, PDF e Capture Engines: integrados ao trem;
- Recording Engine: candidato LEA-201;
- Plugin, Layout, Session e Hub: LEA-202–205.

## Gravação por painel

O botão **Gravar** inicia uma sessão FFmpeg somente sobre a geometria do painel. Durante a gravação, o botão muda para **Parar** e o painel exibe **GRAVANDO**.

Arquivos:

```text
~/Videos/TriView Workspace/Recordings/<workspace>/<painel>/<data>/<hora>.mp4
```

O marco inicial grava vídeo H.264 sem áudio.

## Instalar o candidato LEA-201

```bash
bash scripts/install-candidate.sh \
  LEA-201 \
  leonpcsn/lea-201-implementar-recording-engine-por-painel
```

O atalho criado é **TriView Workspace — LEA-201** e usa dados separados da versão principal.

## Requisitos

```bash
sudo apt update
sudo apt install xdotool maim ffmpeg
```

## Documentação

- [Índice](docs/README.md)
- [Roadmap](docs/product/ROADMAP.md)
- [Trem LEA-197–205](docs/factory/DEVELOPMENT_TRAIN_LEA-197-205.md)
- [LEA-197](docs/work/LEA-197.md)
- [LEA-198](docs/work/LEA-198.md)
- [LEA-199](docs/work/LEA-199.md)
- [LEA-200](docs/work/LEA-200.md)
- [LEA-201](docs/work/LEA-201.md)

## Rastreabilidade

- LEA-191–196: base validada;
- LEA-197–200: painéis executáveis e captura integrados ao trem;
- LEA-201: gravação individual;
- LEA-202–205: etapas seguintes.

# TriView Workspace Linux

Plataforma modular de áreas de trabalho para Linux.

## Estado deste candidato

- versão candidata: `0.9.0`;
- `main`: estável em `0.3.0`;
- Browser e workspaces persistentes: validados;
- Application, Terminal, PDF, Capture e Recording Engines: integrados ao trem;
- Plugin Engine: candidato LEA-202;
- Layout, Session e Hub: LEA-203–205.

## Plugins declarativos

Plugins vivem em:

```text
${XDG_DATA_HOME:-~/.local/share}/triview-workspace/plugins/<id>/manifest.json
```

Eles não carregam código Python. Cada manifesto declara um comando versionado e permanece desativado até autorização explícita no botão **Plugins**.

Painel:

```text
Tipo: custom
Destino: plugin:text-editor
```

## Instalar o candidato e o exemplo

```bash
bash scripts/install-candidate.sh \
  LEA-202 \
  leonpcsn/lea-202-implementar-plugin-engine-seguro

bash scripts/install-example-plugin.sh
```

O atalho criado é **TriView Workspace — LEA-202**. O exemplo usa o editor `xed`, quando instalado.

## Segurança

- manifesto e API versionados;
- ativação explícita;
- IDs e diretórios validados;
- symlinks ignorados;
- execução sem shell;
- argumentos adicionais somente quando autorizados;
- falha isolada com diagnóstico.

## Documentação

- [Índice](docs/README.md)
- [Roadmap](docs/product/ROADMAP.md)
- [Trem LEA-197–205](docs/factory/DEVELOPMENT_TRAIN_LEA-197-205.md)
- [LEA-197](docs/work/LEA-197.md)
- [LEA-198](docs/work/LEA-198.md)
- [LEA-199](docs/work/LEA-199.md)
- [LEA-200](docs/work/LEA-200.md)
- [LEA-201](docs/work/LEA-201.md)
- [LEA-202](docs/work/LEA-202.md)

## Rastreabilidade

- LEA-191–196: base validada;
- LEA-197–201: painéis, captura e gravação integrados ao trem;
- LEA-202: Plugin Engine seguro;
- LEA-203–205: etapas seguintes.

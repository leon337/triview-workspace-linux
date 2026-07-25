# Estratégia de atualização

## Situação da versão legada

O atualizador da V0.1.0 instalava em `~/.local/share/triview-workspace-linux` e dependia de arquivos monolíticos na raiz. Esse contrato é incompatível com a arquitetura modular em `src/triview_workspace/`.

## Migração oficial

A primeira passagem para a arquitetura modular usa o pacote `TriView-Workspace-Migrador-0.1.2`. Ele:

- cria backup da instalação antiga;
- preserva configurações legadas;
- instala em `~/.local/share/triview-workspace/releases/<versão>`;
- mantém o link atômico `current`;
- não apaga a versão antiga;
- cria comandos e atalhos novos.

## Atualizações posteriores

Após a migração, `scripts/update.sh`:

1. tenta baixar a release estável mais recente;
2. enquanto não houver release, usa a branch `main`;
3. copia a versão atual para o diretório de backup;
4. copia o catálogo persistente `workspaces.json` quando ele existe;
5. compila o código baixado;
6. executa o diagnóstico com um catálogo temporário isolado;
7. instala em um novo diretório versionado;
8. troca o link `current` somente depois do sucesso;
9. recria o comando e o atalho gráfico;
10. mantém dados pessoais fora do diretório versionado;
11. informa requisitos opcionais ausentes do Browser Engine.

O diagnóstico do pacote baixado usa `--data-file` apontando para o diretório temporário. Assim, validar uma atualização não altera o último workspace selecionado pelo usuário.

## Catálogo persistente da versão 0.3.0

O catálogo padrão fica em:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/triview-workspace/workspaces.json
```

Ele não fica dentro de `releases/<versão>`. A troca da versão ativa não remove, substitui ou reinicializa esse arquivo.

Antes da atualização, uma cópia adicional é salva em:

```text
~/.local/share/triview-workspace-backups/update-<data>/workspaces.json
```

O próprio aplicativo também grava o catálogo por substituição atômica e preserva arquivos corrompidos com nome de quarentena.

## Browser Engine

A atualização não instala pacotes do sistema sem autorização. Ao final, avisa quando não encontra:

- `xdotool`;
- Brave, Chromium ou Google Chrome compatível.

No Linux Mint/Ubuntu:

```bash
sudo apt update
sudo apt install xdotool
```

A ausência desses componentes não invalida a atualização. A interface continua abrindo e explica por que o painel navegador está indisponível.

## Restauração

`scripts/restore-latest.sh` restaura a cópia mais recente da aplicação e das configurações legadas. O catálogo `workspaces.json` também fica registrado nos backups de atualização gerados a partir da versão 0.3.0.

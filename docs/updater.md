# Estratégia de atualização

## Situação da versão legada

O atualizador da V0.1.0 foi recuperado e analisado. Ele instala em `~/.local/share/triview-workspace-linux`, clona o repositório e exige arquivos monolíticos na raiz (`app.py`, `launcher.sh`, `update.sh`, `uninstall.sh`, `VERSION`). Esse contrato é incompatível com a arquitetura em `src/triview_workspace/`.

## Migração oficial

A primeira passagem para a arquitetura modular deve ser feita com o pacote `TriView-Workspace-Migrador-0.1.2`. Ele:

- cria backup da instalação antiga;
- preserva `~/.config/triview-workspace/config.json`;
- instala em `~/.local/share/triview-workspace/releases/<versão>`;
- mantém um link atômico `current`;
- não apaga a versão antiga;
- cria comandos e atalhos novos;
- configura o atalho principal para abrir a interface gráfica sem terminal.

## Atualizações posteriores

Após a migração, `scripts/update.sh`:

1. tenta baixar a release estável mais recente;
2. enquanto não houver release, usa a branch `main`;
3. compila o código e executa a CLI em modo `--diagnostic` para validar o workspace sem abrir uma janela;
4. instala em um novo diretório versionado;
5. troca o link `current` somente depois do sucesso;
6. recria o comando e o atalho gráfico principal;
7. mantém dados e backups separados do código;
8. informa requisitos opcionais ausentes para o Browser Engine.

## Evolução da interface

Na versão `0.1.1`, o comando principal chamava a CLI de verificação, que imprimia JSON e encerrava. A versão `0.1.2` alterou o comportamento padrão para abrir a GUI e preservou o diagnóstico apenas quando `--diagnostic` é informado.

A versão `0.2.0` adiciona o primeiro Browser Engine. A atualização do código continua automática, mas o atualizador não instala pacotes do sistema sem autorização. Ao final, ele avisa quando não encontra:

- `xdotool`;
- Brave, Chromium ou Google Chrome compatível.

No Linux Mint/Ubuntu, `xdotool` pode ser instalado com:

```bash
sudo apt update
sudo apt install xdotool
```

A ausência desses componentes não invalida a atualização. A interface continua abrindo e apresenta o motivo pelo qual o painel navegador está indisponível.

## Restauração

`scripts/restore-latest.sh` restaura a cópia mais recente da aplicação e das configurações legadas. A nova instalação permanece disponível para inspeção.

# Estratégia de atualização

## Instalação principal

A instalação estável usa:

```text
~/.local/share/triview-workspace/releases/<versão>
~/.local/share/triview-workspace/current
```

O catálogo persistente permanece fora das releases:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/triview-workspace/workspaces.json
```

Antes de qualquer troca, a versão ativa e o catálogo são copiados para:

```text
~/.local/share/triview-workspace-backups/update-<data>/
```

A nova versão é validada em diretório isolado. O link `current` é substituído atomicamente somente depois de compilação, diagnóstico e importação do módulo principal concluírem com sucesso.

## Controlador e núcleo

`scripts/update.sh` é o controlador de canal. `scripts/update-core.sh` contém o atualizador legado endurecido e compatível com instalações anteriores.

Depois de uma atualização bem-sucedida, os dois arquivos são instalados em:

```text
~/.local/share/triview-workspace/updater/update.sh
~/.local/share/triview-workspace/updater/update-core.sh
```

O atalho oficial executa o controlador, mostra o resultado e grava o log em:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/triview-workspace/update-<data>.log
```

## Canal stable

`stable` é o canal padrão quando não existe escolha explícita por argumento, variável de ambiente ou arquivo persistido.

```bash
bash scripts/update.sh --stable
```

O canal estável consulta a release mais recente. Enquanto nenhuma release existir, usa a branch `main`. Depois do sucesso, grava `stable` em:

```text
~/.local/share/triview-workspace/UPDATE_CHANNEL
```

## Canal testing

O canal de testes nunca é selecionado implicitamente. Ele exige uma destas escolhas:

```bash
bash scripts/update.sh --testing
```

```bash
TRIVIEW_UPDATE_CHANNEL=testing bash scripts/update.sh
```

ou arquivo `UPDATE_CHANNEL` contendo `testing`.

Além do opt-in, o manifesto deve:

- usar `schema_version: 1`;
- declarar `channel: testing`;
- estar explicitamente habilitado;
- identificar candidato, versão, módulo e status;
- fixar um commit SHA hexadecimal completo de 40 caracteres.

O manifesto versionado em `config/update-channels/testing.json` fica desabilitado após a liberação 1.0.0a1. Uma nova campanha de testes deve habilitar deliberadamente um manifesto revisado e auditável.

## Publicação

O workflow de publicação não cria tag ou release imediatamente após o push. Primeiro executa:

1. instalação das dependências de desenvolvimento;
2. compilação de `src` e `tests`;
3. validação sintática de todos os scripts shell;
4. suíte pytest completa;
5. integração real da roda em X11;
6. presença e classificação dos dispositivos XTEST;
7. contenção Xephyr autenticada.

Somente quando o job `verify` termina em PASS o job `release` pode criar a tag `v<versão>` e a GitHub Release apontando para o SHA exato de `main`.

## Restauração e rollback

O atualizador preserva a versão anterior e o catálogo antes da troca. Os atalhos oficiais de rollback e os scripts de restauração operam sobre esses backups sem remover os dados persistentes do usuário.

O diagnóstico do pacote baixado usa um catálogo temporário. Validar uma atualização não altera o último workspace selecionado.

## Requisitos do sistema

No Linux Mint/Ubuntu com X11:

```bash
sudo apt update
sudo apt install xdotool xauth xserver-xephyr x11-utils
```

Também é necessário um navegador Brave, Chromium ou Google Chrome compatível. A ausência de dependências do Browser Engine deve ser informada; nunca deve transformar uma atualização parcial em versão ativa.

# Estratégia de atualização

## Versão principal

A instalação principal usa:

```text
~/.local/share/triview-workspace/releases/<versão>
~/.local/share/triview-workspace/current
```

O atualizador `scripts/update.sh` baixa a release mais recente ou a branch `main`, valida o pacote, cria backup e troca o link `current` somente após sucesso.

Dados persistentes ficam fora das releases:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/triview-workspace/workspaces.json
```

Antes da atualização, o catálogo é copiado para:

```text
~/.local/share/triview-workspace-backups/update-<data>/workspaces.json
```

O diagnóstico do pacote baixado usa um catálogo temporário para não alterar o último workspace do usuário.

## Candidatos do trem LEA-197–205

Candidatos não são instalados sobre a versão principal. O script `scripts/install-candidate.sh` recebe um identificador e uma branch:

```bash
bash scripts/install-candidate.sh LEA-197 \
  leonpcsn/lea-197-implementar-application-engine-e-panel-runtime-comum
```

Cada candidato usa:

```text
~/.local/share/triview-workspace-candidates/<lea>
~/.local/share/triview-workspace-candidate-data/<lea>
~/.local/state/triview-workspace-candidates/<lea>
```

E cria um atalho separado:

```text
TriView Workspace — LEA-XXX
```

Consequências:

- a branch `main` e seu link `current` não são modificados;
- o catálogo da versão principal não é lido nem gravado;
- vários candidatos podem coexistir;
- remover um candidato não afeta a versão estável;
- uma LEA pode ser testada antes de ser promovida.

## Requisitos do sistema

O instalador não instala pacotes do sistema sem autorização.

Browser e incorporação de aplicações em X11 utilizam `xdotool`:

```bash
sudo apt update
sudo apt install xdotool
```

Sem `xdotool`:

- Browser Engine fica indisponível;
- Application Engine pode abrir programas externamente, mas não incorporá-los.

Programas configurados em painéis `application` também precisam estar instalados e executáveis.

## Migração e restauração

A primeira passagem da instalação legada usa o migrador oficial. `scripts/restore-latest.sh` restaura a cópia mais recente da aplicação e das configurações registradas nos backups.

Candidatos são intencionalmente descartáveis e não participam da restauração da versão principal.

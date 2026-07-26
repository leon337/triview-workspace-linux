# Estratégia de atualização

## Objetivo operacional

O usuário atualiza o TriView pelo atalho **Atualizar TriView Workspace**. O fluxo não exige clonagem, troca manual de branch ou execução de instaladores de candidato.

A atualização possui dois canais:

- `stable`: release oficial mais recente ou `main` quando ainda não existe release;
- `testing`: somente o candidato explicitamente autorizado no manifesto controlado.

## Bootstrap 0.3.1

A versão `0.3.1` corrige somente o mecanismo de atualização. Ela não promove as funcionalidades das LEAs 197–205 para a `main`.

Na primeira execução do atalho antigo, a `main` atualizada instala o bootstrap `0.3.1`. Na execução seguinte, o novo controlador consulta o canal de testes e instala apenas a LEA autorizada.

## Controlador persistente

O controlador passa a viver fora das releases:

```text
~/.local/share/triview-workspace/updater/update.sh
```

O atalho gráfico chama esse arquivo persistente. Assim, instalar uma branch candidata não substitui o mecanismo responsável por selecionar a próxima LEA.

O canal local fica em:

```text
~/.local/share/triview-workspace/UPDATE_CHANNEL
```

O candidato ativo fica registrado em:

```text
~/.local/share/triview-workspace/ACTIVE-CANDIDATE.json
```

## Canal de testes controlado

O manifesto oficial fica em:

```text
config/update-channels/testing.json
```

Ele contém:

- identificador da LEA;
- versão esperada;
- commit SHA completo e imutável;
- módulo gráfico autorizado;
- estado operacional.

O atualizador rejeita:

- manifesto desativado ou incompleto;
- referência que não seja um SHA completo;
- versão diferente da autorizada;
- módulo sem função `main()`;
- pacote sem `pyproject.toml` ou código da aplicação.

## Fluxo de uma LEA por vez

```text
liberar LEA no manifesto
→ usuário clica em Atualizar
→ backup da versão e catálogo
→ download do commit fixado
→ compilação e diagnóstico isolado
→ validação do módulo gráfico
→ troca atômica do link current
→ teste no Linux Mint
→ registro de PASS ou FAIL
→ somente depois liberar a próxima LEA
```

Enquanto o manifesto continuar apontando para o mesmo commit, novos cliques não reinstalam o candidato.

## Preservação e rollback

Antes da troca, o atualizador copia:

```text
~/.local/share/triview-workspace/current
~/.local/share/triview-workspace/workspaces.json
```

para:

```text
~/.local/share/triview-workspace-backups/update-<data>/
```

O catálogo persistente permanece fora das releases. O link `current` é trocado somente após compilação, diagnóstico e validação do módulo.

## Candidato inicialmente autorizado

O canal de testes começa bloqueado na sequência da fábrica:

```text
LEA-197 — Application Engine e Panel Runtime — 0.4.0
```

A LEA-198 não deve ser liberada antes do aceite ou da correção da LEA-197.

## Requisitos do sistema

O atualizador não instala pacotes do sistema sem autorização. A incorporação X11 utiliza `xdotool`. Sem ele, aplicações podem abrir externamente, mas não serão incorporadas ao painel.

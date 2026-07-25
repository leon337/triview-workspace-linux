# Trem de desenvolvimento LEA-197–205

## Objetivo

Preparar as funcionalidades até o Workspace Hub sem alterar a versão estável antes dos testes de aceite.

## Ramos

- base estável: `main`;
- integração: `train/road-to-1.0`;
- uma branch própria para cada LEA;
- um PR, CI, documentação e candidato isolado por LEA.

## Sequência

1. LEA-197 — Application Engine e Panel Runtime;
2. LEA-198 — Terminal Engine;
3. LEA-199 — PDF Engine;
4. LEA-200 — Capture Engine;
5. LEA-201 — Recording Engine;
6. LEA-202 — Plugin Engine;
7. LEA-203 — Layout Engine avançado;
8. LEA-204 — Session Engine completo;
9. LEA-205 — Workspace Hub.

## Dependências

```text
LEA-197 ──┬── LEA-198
          ├── LEA-199
          ├── LEA-200 ── LEA-201
          └── LEA-202

LEA-196 ───── LEA-203

LEA-197 + LEA-198 + LEA-199 + LEA-203 ── LEA-204 ── LEA-205
```

## Regras de promoção

- código pode ser integrado ao ramo do trem após CI;
- `main` não recebe a LEA antes do teste correspondente;
- uma falha em uma dependência bloqueia a promoção das posteriores afetadas;
- correções são aplicadas na primeira branch responsável e propagadas para as dependentes;
- cada candidato usa código, dados e estado separados da versão principal.

## Candidatos isolados

O script `scripts/install-candidate.sh` instala uma branch em:

```text
~/.local/share/triview-workspace-candidates/<lea>
```

Os dados ficam em:

```text
~/.local/share/triview-workspace-candidate-data/<lea>
```

O instalador cria um atalho com o nome `TriView Workspace — LEA-XXX`. A versão principal e seu catálogo não são modificados.

## Estados no Linear

- LEA em implementação: **In Progress**;
- LEAs preparadas mas bloqueadas: **Todo**;
- implementação integrada e aguardando teste real: permanece **In Progress**;
- somente após aceite no Linux Mint: **Done**.

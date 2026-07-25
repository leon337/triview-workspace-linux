# ADR-0002 — Documentação como fonte oficial de verdade

- Status: aceito
- Data: 2026-07-25
- Tarefa: LEA-194

## Contexto

As primeiras entregas do TriView Workspace foram registradas em issues do Linear, pull requests, commits, README, changelog e conversas. A informação técnica estava rastreável, porém distribuída. Isso criava risco de:

- decisões permanecerem apenas nas conversas;
- planos futuros serem confundidos com recursos disponíveis;
- o roadmap depender de memória informal;
- novos colaboradores precisarem reconstruir o histórico a partir de várias fontes;
- processos da Fábrica de Softwares variarem entre tarefas.

## Decisão

O diretório `docs/` será a fonte oficial para visão do produto, princípios, roadmap, arquitetura, decisões, processo e histórico explicado de versões.

O Linear continuará sendo a fonte operacional das tarefas. O GitHub continuará sendo a fonte técnica do código, revisão, CI e integração. Os dois sistemas devem permanecer vinculados.

A hierarquia passa a ser:

```text
docs/            visão, arquitetura, processo e estado consolidado
Linear           trabalho planejado e executado
GitHub PR/commits implementação, revisão e integração
CHANGELOG         mudanças técnicas por versão
releases/pacotes  artefatos distribuídos
```

## Regras

1. O README da raiz deve apontar para `docs/README.md`.
2. Funcionalidades futuras devem ser identificadas como planejadas.
3. Uma funcionalidade só pode ser documentada como disponível após merge na branch principal.
4. Mudanças arquiteturais relevantes devem gerar ADR.
5. Mudanças funcionais devem atualizar changelog e histórico de versões.
6. Tarefas concluídas devem registrar issue, PR, CI e commit de merge.
7. Documentação deve ser validada por testes simples de existência e links internos.

## Consequências positivas

- continuidade do projeto sem depender da memória da conversa;
- separação clara entre disponível, experimental e planejado;
- onboarding mais rápido;
- decisões auditáveis;
- maior consistência entre Fábrica de Softwares, Linear e GitHub.

## Custos e riscos

- cada tarefa exige manutenção documental proporcional ao impacto;
- documentos podem ficar obsoletos se a definição de pronto não for aplicada;
- duplicação deve ser evitada por meio do índice central e referências cruzadas.

## Consequência operacional

Uma tarefa que altera produto, arquitetura, processo, versão ou experiência de instalação não está pronta enquanto sua documentação correspondente permanecer desatualizada.

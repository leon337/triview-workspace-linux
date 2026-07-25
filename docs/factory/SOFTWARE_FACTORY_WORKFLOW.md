# Manual operacional da Fábrica de Softwares

Este documento define o fluxo padrão para transformar uma ideia aprovada em uma entrega rastreável, testada e atualizável.

## Fluxo principal

```text
Ideia
  ↓
Refinamento de escopo
  ↓
Tarefa no Linear
  ↓
Branch no GitHub
  ↓
Implementação limitada ao escopo
  ↓
Testes e documentação
  ↓
Pull request
  ↓
CI e revisão
  ↓
Merge
  ↓
Release ou atualização, quando aplicável
  ↓
Validação do usuário
  ↓
Próxima tarefa
```

## 1. Entrada da ideia

A ideia inicial deve ser convertida em um problema e um resultado esperado.

Perguntas mínimas:

- qual problema será resolvido;
- quem utilizará a funcionalidade;
- qual resultado observável deve existir;
- o que pertence ao MVP;
- o que fica explicitamente fora do escopo;
- quais riscos podem impedir a entrega.

A implementação não deve começar com requisitos contraditórios ou sem um resultado verificável.

## 2. Refinamento

Antes de criar código, registrar:

- objetivo;
- escopo;
- limites;
- critérios de aceitação;
- dependências;
- riscos;
- estratégia de validação.

Quando houver decisão arquitetural relevante, criar ou atualizar uma ADR.

## 3. Criação da tarefa no Linear

Cada unidade de trabalho deve possuir uma issue própria.

Conteúdo mínimo:

- título objetivo;
- descrição do problema;
- objetivo;
- escopo;
- fora do escopo;
- critérios de aceitação;
- prioridade;
- projeto associado;
- responsável;
- estado inicial adequado.

Identificadores do Linear devem aparecer na branch e no pull request.

## 4. Criação da branch

Formato recomendado:

```text
<responsavel>/<identificador>-<descricao-curta>
```

Exemplo:

```text
leonpcsn/lea-194-consolidar-documentacao
```

Regras:

- partir da `main` atualizada;
- uma tarefa principal por branch;
- não misturar correções não relacionadas;
- não publicar segredos ou arquivos pessoais.

## 5. Implementação

A implementação deve:

- respeitar o escopo aprovado;
- manter separação entre domínio, interface e infraestrutura;
- tratar erros previsíveis;
- preservar compatibilidade quando exigido;
- atualizar ou criar testes;
- atualizar documentação correspondente.

Mudanças descobertas durante a tarefa que não são necessárias ao aceite devem virar nova issue, não expansão silenciosa do escopo.

## 6. Validação local

Executar o conjunto aplicável:

- testes unitários;
- testes de integração;
- compilação ou verificação de sintaxe;
- lint e tipagem, quando configurados;
- validação manual do fluxo principal;
- teste de migração ou atualização em ambiente isolado;
- teste de restauração quando dados forem alterados.

Resultados devem ser registrados no pull request.

## 7. Documentação

Toda mudança deve avaliar impacto em:

- `README.md`;
- `CHANGELOG.md`;
- documentação de produto;
- arquitetura;
- ADRs;
- migração e atualização;
- manual de usuário;
- roadmap.

Não declarar como disponível algo que continua planejado.

## 8. Pull request

O PR deve conter:

- objetivo;
- resumo das mudanças;
- testes executados;
- riscos e limites;
- instruções de validação;
- vínculo com a issue do Linear.

O PR não deve ser mesclado enquanto a CI estiver em execução ou falhando.

## 9. CI e revisão

A CI é uma barreira obrigatória, não apenas informativa.

Critérios mínimos:

- testes aprovados;
- compilação ou validação de sintaxe aprovada;
- ausência de regressão conhecida no escopo;
- documentação coerente com a implementação.

Achados de revisão devem ser corrigidos na mesma branch ou convertidos em tarefa separada quando forem claramente fora do escopo.

## 10. Merge

O merge deve ocorrer somente após:

- critérios de aceitação atendidos;
- CI concluída com sucesso;
- PR atualizado;
- versão e changelog ajustados quando necessário;
- riscos conhecidos registrados.

Método preferencial: squash, mantendo um commit final rastreável por tarefa, salvo quando o projeto exigir outra estratégia.

## 11. Release e atualização

Nem toda tarefa documental exige nova versão funcional.

Criar release ou pacote quando houver:

- alteração no comportamento da aplicação;
- correção que o usuário precise instalar;
- mudança de esquema ou migração;
- alteração no instalador ou atualizador;
- marco funcional aprovado.

A entrega deve incluir:

- número de versão;
- notas de mudança;
- pacote ou canal de atualização;
- checksum quando houver arquivo distribuído;
- instruções objetivas;
- plano de restauração quando aplicável.

## 12. Atualização do Linear

Após o merge:

- registrar PR e commit final;
- registrar testes e CI;
- anexar ou vincular pacote quando houver;
- marcar critérios concluídos;
- mover a issue para `Done`.

Uma tarefa não deve ser marcada como concluída apenas porque o código foi iniciado.

## 13. Validação do usuário

A validação real pode revelar:

- problema funcional;
- comportamento inesperado do ambiente;
- necessidade de refinamento visual;
- requisito não identificado.

Cada problema novo deve gerar uma correção rastreável. Não esconder falhas nem tratá-las como sucesso parcial.

## 14. Política de uma tarefa por vez

O fluxo padrão do projeto é concluir uma tarefa antes de iniciar a seguinte.

Exceções exigem justificativa, por exemplo:

- correção urgente bloqueando uso;
- tarefa de investigação sem alteração de código;
- dependência externa aguardando resposta.

Mesmo nas exceções, branches, issues e escopos permanecem separados.

## 15. Definição de pronto

Uma tarefa está pronta quando:

- o objetivo foi atingido;
- os critérios de aceitação foram verificados;
- testes aplicáveis passaram;
- CI passou;
- documentação foi atualizada;
- PR foi mesclado;
- Linear foi atualizado;
- pacote foi entregue quando necessário;
- limitações restantes foram registradas.

## 16. Rastreabilidade obrigatória

Cada entrega deve permitir reconstruir esta cadeia:

```text
Decisão ou necessidade
        ↓
Issue do Linear
        ↓
Branch
        ↓
Commits
        ↓
Pull request
        ↓
CI
        ↓
Merge
        ↓
Release/pacote
        ↓
Validação
```

Essa cadeia é o registro auditável da Fábrica de Softwares.

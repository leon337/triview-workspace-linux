# Checkpoint de passagem de bastão — TriView Workspace

## 1. Identificação

- Data do checkpoint: `2026-07-28`
- Repositório: `leon337/triview-workspace-linux`
- Objetivo estratégico no Linear: `LEA-226 — OBJ-TRIVIEW-01 — Finalizar e liberar o TriView para trabalho real`
- Pull request candidato: `PR #35 — RC4 — Interface proporcional aprovada`
- Branch candidata: `feat/triview-rc4-approved-ui`
- HEAD candidato no momento deste checkpoint: `1a0c71abd3e46f834fd7aec78d27f2daf171397b`
- Base do PR #35: `train/road-to-1.0`
- Estado do PR #35: `Draft`, aberto, não integrado ao trem nem à `main`
- Estado do objetivo: `IN_PROGRESS`
- Estado final exigido: `PASS_RELEASED_FOR_WORK`

> Este documento é o checkpoint canônico para continuar o trabalho em outro chat sem reconstruir o contexto manualmente.

---

## 2. Por que este chat foi iniciado

O chat começou para corrigir e concluir a implementação do TriView.

O TriView foi criado para permitir que Leo trabalhe com três chats do GPT ao mesmo tempo, usando cada chat como um agente especializado. O telefone também pode manter outro chat, ampliando as frentes de trabalho.

O objetivo não é apenas abrir várias janelas. O objetivo é criar uma sala operacional confiável, na qual vários agentes possam trabalhar sem exigir que Leo controle manualmente cada contexto, tarefa, falha e retomada.

Durante o trabalho, ficou evidente um problema organizacional mais amplo: muitos projetos e ideias são iniciados, mas objetivos anteriores ficam parados ou incompletos quando surge uma nova dificuldade ou oportunidade.

---

## 3. Visão estratégica consolidada

As peças discutidas neste chat formam um único sistema operacional da Fábrica de Softwares:

```text
CULTURA ORGANIZACIONAL
Define valores, comportamento, autoridade e limites
        ↓
MOP
Transforma os princípios em metodologia e procedimentos
        ↓
OLO / LOOP ORIENTADO POR OBJETIVO
Mantém o objetivo ativo até PASS, BLOCKED legítimo, CANCELED ou SUPERSEDED
        ↓
TRIVIEW
Sala visual de operações com múltiplos chats/agentes
        ↓
GITHUB + LINEAR
Código, tarefas, estados, decisões e evidências
        ↓
TIMELINE SOCIAL
Memória operacional apresentada como rede social dos chats e agentes
        ↓
JARVIS PREDIX
Diretor-geral informacional, inicialmente consultivo e orientado por voz
```

### Rede social dos chats e agentes

Conceito definido:

- cada chat funciona como um perfil;
- cada mensagem, resposta, decisão, execução, falha ou entrega gera evento/postagem;
- a MOP obriga a produção de eventos estruturados;
- o GitHub mantém a memória versionada da timeline;
- uma automação consulta periodicamente as mudanças no arquivo ou conjunto de arquivos da timeline;
- o sistema online atualiza o feed;
- evolução posterior: polling para webhooks;
- finalidade: memória, auditoria, busca, continuidade e visão global da fábrica.

### Jarvis PREDIX

Decisões preliminares:

- primeira versão será consultiva e informacional, sem mutações;
- voz será a interface principal;
- texto continuará existindo como confirmação visual, fontes e evidências;
- será um produto executivo separado, conectado à timeline social;
- deverá responder perguntas como “Como está o andamento da fábrica?” sem exigir auditorias manuais em chats, GitHub ou Linear.

---

## 4. Ordem estratégica aprovada por Leo

A sequência oficial aprovada foi:

1. finalizar e liberar o TriView;
2. remediar os sete pontos altos da MOP;
3. executar nova revisão independente da MOP;
4. finalizar a Cultura Organizacional;
5. consolidar os POPs;
6. reconciliar Cultura → MOP → POPs → Timeline;
7. iniciar a rede social como projeto-piloto;
8. planejar o Jarvis consultivo.

### Regra de foco

```text
WIP_ESTRATEGICO=1
OBJETIVO_ATIVO=FINALIZAR_E_LIBERAR_TRIVIEW
```

Novas ideias podem ser registradas, mas não interrompem o objetivo ativo.

---

## 5. Tarefas estratégicas preservadas

### TriView

- `LEA-226` — objetivo estratégico principal;
- `LEA-227` — reconciliar GitHub, Linear, documentação e estado local;
- `LEA-228` — fixar baseline canônica e consolidar RC4;
- `LEA-229` — executar aceite funcional completo no Linux Mint;
- `LEA-230` — remediar falhas do candidato até PASS funcional;
- `LEA-231` — validar instalação, atualização, diagnóstico, backup e rollback;
- `LEA-232` — executar RC independente de prontidão para release;
- `LEA-233` — aprovar promoção e liberar versão estável;
- `LEA-234` — confirmar liberação para trabalho real e encerrar objetivo;
- `LEA-238` — corrigir roteamento do Terminal para engine incorporado;
- `LEA-239` — remover ou reparar atalhos órfãos;
- `LEA-240` — entregar workspace operacional com três chats GPT;
- `LEA-241` — corrigir congelamento da RC4 e captura do desktop.

### Depois do TriView

- `LEA-225` — remediar os sete achados altos da MOP;
- `LEA-235` — finalizar e reconciliar Cultura Organizacional PREDIX;
- `LEA-236` — planejar e iniciar rede social dos chats e agentes;
- `LEA-237` — planejar Jarvis PREDIX consultivo por voz.

---

## 6. Trabalho executado neste chat

### 6.1 LEA-227 — reconciliação

Resultado: concluída.

Foi verificado que:

- `main` permanece como linha estável;
- `train/road-to-1.0` contém o trem funcional anterior;
- PR #35 é a linha visual RC4 candidata;
- PR #33 foi absorvido pela RC4;
- PR #34 possuía divergências visuais próprias, posteriormente tratado como substituído pela RC4 aprovada;
- estados do Linear foram reconciliados com o trabalho realmente integrado e ainda não aceito em ambiente real.

### 6.2 LEA-228 — baseline canônica

Resultado: concluída.

Baseline inicialmente fixada:

- PR #35;
- branch `feat/triview-rc4-approved-ui`;
- versão `1.0.0a1`;
- CI verde;
- candidato isolado, sem promoção para `train` ou `main`.

O instalador foi endurecido para:

- resolver branch/tag para SHA imutável;
- baixar o snapshot pelo SHA;
- registrar `candidate-release.json`;
- preservar o candidato anterior por link `previous`;
- trocar o candidato ativo de forma atômica;
- separar dados e estado do candidato da versão estável;
- abrir a entrada RC4 correta.

### 6.3 Primeiro teste real — vídeo `1000827436.mp4`

O teste mostrou:

- instalação isolada: PASS;
- abertura da interface: PASS;
- ChatGPT incorporado: PASS;
- GitHub incorporado: PASS;
- Terminal abriu externamente: FAIL;
- Terminal permaneceu aberto depois do fechamento do TriView: FAIL associado;
- atalho legado `triview-workspace-dev.desktop` estava quebrado.

### 6.4 LEA-238 — Terminal externo

Causa comprovada:

```json
{
  "id": "terminal",
  "kind": "application",
  "target": "x-terminal-emulator"
}
```

Essa configuração roteava o painel para `ApplicationRuntimeController` e ignorava o backend de Terminal incorporado.

Correção integrada na branch candidata:

```json
{
  "id": "terminal",
  "kind": "terminal",
  "target": "bash -l"
}
```

Resultado remoto:

- PR de remediação: `#37`;
- integrado somente na branch candidata do PR #35;
- novo HEAD: `1a0c71abd3e46f834fd7aec78d27f2daf171397b`;
- CI run `130`: PASS;
- pytest: `125 PASS`, `0 falhas`, `0 erros`, `0 ignorados`;
- nenhuma promoção para `train` ou `main`.

O Terminal incorporado ainda não recebeu reteste conclusivo no Linux Mint porque surgiu uma falha mais crítica na janela principal.

### 6.5 Segundo teste real — vídeo `1000827446.mp4`

A primeira análise do vídeo foi incorreta: concentrou-se nos painéis e não identificou o comportamento global da janela.

Leo esclareceu a falha real:

- TriView abre e fica congelado;
- não minimiza;
- não maximiza;
- não restaura;
- menus do TriView não aparecem;
- Menu Iniciar fica atrás da aplicação;
- ferramenta de captura aparece atrás da aplicação;
- cliques não geram resposta útil;
- a janela domina a frente do computador;
- não é possível sair normalmente;
- é necessário reiniciar o computador.

Essa falha é crítica e bloqueia qualquer novo teste de engines.

---

## 7. Diagnóstico técnico atual da falha crítica

### Hipótese 1 — causa principal provável

O código da RC4 executa:

```python
root.overrideredirect(True)
```

Isso remove a janela do gerenciamento normal do Cinnamon/Muffin e faz o TriView simular sua própria barra, maximização, restauração e minimização.

Efeitos compatíveis com o relato:

- janela não gerenciada;
- comportamento de sempre à frente;
- Menu Iniciar e captura atrás;
- Alt+Tab e minimizar inconsistentes;
- controles próprios sem garantia de integração com o gerenciador de janelas.

O código também volta a ativar `overrideredirect(True)` depois do evento `<Map>`, podendo recolocar a janela no estado problemático após minimizar/restaurar.

### Hipótese 2 — menus com grab preso

Menus globais e de painéis usam `tk_popup()`.

Se o popup ficar oculto, abrir atrás ou falhar, o grab de entrada pode não ser liberado. Isso pode bloquear cliques na aplicação e no desktop.

### Hipótese 3 — tempestade de eventos de geometria

Possível ciclo:

```text
<Configure>
→ _schedule_compact_chrome
→ _apply_compact_chrome
→ update_idletasks
→ alterações de tamanho/layout
→ novo <Configure>
→ repetição
```

Esse ciclo pode saturar o thread principal do Tkinter e fazer a interface parecer congelada.

### Hipótese 4 — ausência de fail-safe

A aplicação não possui um mecanismo confiável de saída emergencial quando a camada gráfica entra em estado inválido.

---

## 8. Estado atual exato

| Item | Estado |
|---|---|
| Objetivo LEA-226 | In Progress |
| LEA-227 | Done |
| LEA-228 | Done |
| LEA-229 | In Progress, bloqueada pela LEA-241 |
| LEA-230 | In Progress |
| LEA-238 | Done remoto, reteste real pendente |
| LEA-239 | Todo |
| LEA-240 | Todo |
| LEA-241 | In Progress, prioridade urgente |
| PR #35 | Draft, aberto, mergeável |
| Branch candidata | `feat/triview-rc4-approved-ui` |
| HEAD candidato | `1a0c71abd3e46f834fd7aec78d27f2daf171397b` |
| CI do HEAD | PASS, run 130 |
| Testes automatizados | 125 PASS |
| Promoção para trem/main | Não executada |
| Aceite Linux Mint | FAIL crítico na janela principal |
| Objetivo concluído | Não |

### Observação de rastreabilidade local

O HEAD candidato atual no GitHub é `1a0c71...`. A sequência anterior orientou instalar esse SHA. O vídeo não exibiu diretamente o arquivo `candidate-release.json`; portanto, antes do próximo reteste, convém confirmar o SHA efetivamente instalado no computador.

---

## 9. Próxima tarefa obrigatória — LEA-241

### Objetivo

Corrigir o congelamento da RC4 e devolver o controle normal do desktop ao usuário.

### Remediação mínima obrigatória

1. remover `root.overrideredirect(True)` da baseline funcional;
2. usar janela gerenciada pelo Cinnamon/Muffin;
3. manter temporariamente a barra de título nativa, mesmo que visualmente menos elegante;
4. usar maximização compatível com o window manager;
5. remover o código que reativa borderless no `<Map>`;
6. proteger todos os `tk_popup()` com `try/finally` e `grab_release()`;
7. reduzir ou eliminar ciclos de `<Configure>` + `update_idletasks()`;
8. adicionar saída emergencial, por exemplo `Ctrl+Alt+Q` ou `Ctrl+Shift+Escape`, documentada e testada;
9. adicionar testes automatizados para o contrato de janela gerenciada e menus seguros;
10. executar CI;
11. integrar somente na branch candidata do PR #35;
12. gerar novo SHA imutável;
13. só então solicitar novo teste no Linux Mint.

### Critérios de aceite real da LEA-241

- TriView não fica sempre à frente;
- Menu Iniciar aparece normalmente;
- Alt+Tab troca de aplicação;
- minimizar funciona;
- maximizar funciona;
- restaurar funciona;
- menus global e de painel aparecem e fecham sem grab preso;
- ferramenta de captura aparece acima quando solicitada;
- fechamento não exige reinício;
- atalho de emergência encerra o TriView;
- nenhum dado estável é alterado;
- sem promoção para `train` ou `main`.

### Ordem após PASS da LEA-241

1. retomar a LEA-229 exatamente no teste interrompido;
2. revalidar o Terminal incorporado;
3. seguir PDF, captura, gravação, plugins, layouts, sessões e Workspace Hub;
4. executar LEA-240 com três chats GPT simultâneos;
5. corrigir atalhos órfãos pela LEA-239;
6. validar instalação, atualização, diagnóstico, backup e rollback;
7. RC independente;
8. gate humano via Visualize para promoção;
9. instalar release estável;
10. encerrar LEA-226 apenas como `PASS_RELEASED_FOR_WORK`.

---

## 10. Regras operacionais para o próximo chat

1. Trabalhar em português do Brasil.
2. Usar GitHub e Linear como fontes de verdade operacional.
3. Não usar Codex.
4. Não promover para `train/road-to-1.0` ou `main` sem gate explícito.
5. Não confundir tarefa criada com tarefa executada.
6. Continuar o loop até PASS ou BLOCKED legítimo.
7. Não pedir “posso continuar?” em operações rotineiras já autorizadas.
8. Usar Visualize quando houver uma decisão humana real com alternativas, impactos e riscos.
9. Não usar Visualize apenas para apresentar status comum.
10. Não gerar imagens quando o pedido for explicação ou análise, salvo solicitação explícita.
11. Ao analisar vídeo, observar comportamento global da janela, resposta a cliques, ordem de sobreposição, menus, barra do sistema e efeitos após fechar, não apenas o conteúdo dos painéis.
12. Distinguir sempre: proposto, criado, implementado, integrado, testado automaticamente, testado no Linux Mint, aceito e liberado.
13. Preservar dados da versão estável.
14. Não solicitar novo teste inseguro antes de a correção possuir CI verde e SHA imutável.
15. Registrar cada falha real no Linear com causa, evidência e condição de retomada.

---

## 11. Recuperação emergencial durante testes

Caso uma versão antiga prenda a sessão gráfica:

```text
Ctrl + Alt + F3
```

Entrar com o usuário e executar:

```bash
pkill -f triview_workspace
```

Retornar à sessão gráfica com:

```text
Ctrl + Alt + F7
```

Dependendo da configuração do Linux Mint, o retorno pode ocorrer com `Ctrl + Alt + F1`.

Esse procedimento é apenas contingência. O candidato corrigido deve possuir um fail-safe interno e não depender disso.

---

## 12. Sete achados altos da MOP preservados para depois do TriView

A remediação MOP-04 permanece registrada e não pode ser esquecida:

1. ordenação causal e ingestão entre fontes independentes;
2. recuperação de webhooks que nunca chegaram ao inbox;
3. armazenamento seguro e versionado de RunState e Decision Capsules;
4. kill switch tecnicamente vinculante e fail-closed;
5. executor determinístico, PEP, command broker e sandbox;
6. journal de migração, crash recovery e rollback coordenado;
7. consistência distribuída GitHub–Linear–estado durável e tratamento de `PARTIAL_SYNC`.

Retomar após o encerramento formal do TriView.

---

## 13. Condição de passagem de bastão

O próximo chat deve iniciar lendo este arquivo e o prompt complementar:

- `docs/handoffs/TRIVIEW_CHECKPOINT_2026-07-28.md`
- `docs/handoffs/TRIVIEW_CONTINUATION_PROMPT_2026-07-28.md`

A primeira ação não deve ser pedir um novo resumo ao usuário. Deve ser verificar GitHub e Linear, confirmar se o HEAD e os estados ainda correspondem ao checkpoint e retomar a LEA-241.

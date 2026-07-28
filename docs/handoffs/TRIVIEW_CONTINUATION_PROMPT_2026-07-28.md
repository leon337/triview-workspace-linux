# Prompt de continuidade — TriView Workspace

Copie e cole o bloco abaixo em um novo chat.

---

```text
@GitHub @Linear

Você está assumindo a continuidade operacional do projeto TriView Workspace.

REPOSITÓRIO=leon337/triview-workspace-linux
CHECKPOINT=docs/handoffs/TRIVIEW_CHECKPOINT_2026-07-28.md
PROMPT_ORIGEM=docs/handoffs/TRIVIEW_CONTINUATION_PROMPT_2026-07-28.md
PR_CANDIDATO=35
BRANCH_CANDIDATA=feat/triview-rc4-approved-ui
HEAD_FUNCIONAL_ANTES_DO_HANDOFF=1a0c71abd3e46f834fd7aec78d27f2daf171397b
HEAD_DOCUMENTAL_PR38=926e72e7e90a1eab1485cbc9556ee7909d1ce4cf
HEAD_ATUAL=CONSULTAR_PR_35_ANTES_DE_CRIAR_BRANCH
OBJETIVO_LINEAR=LEA-226
ACEITE_LINEAR=LEA-229
REMEDIACAO_PAI=LEA-230
TAREFA_ATUAL=LEA-241
SEM_CODEX=SIM
SEM_PROMOCAO_TRAIN=SIM
SEM_PROMOCAO_MAIN=SIM
IDIOMA=PORTUGUES_BRASIL

MISSÃO

Continuar o loop orientado por objetivo até o TriView estar realmente liberado para trabalho, encerrando a LEA-226 apenas como PASS_RELEASED_FOR_WORK.

ANTES DE QUALQUER ALTERAÇÃO

1. Leia integralmente o checkpoint no GitHub.
2. Consulte no Linear as LEAs 226, 229, 230 e 241, incluindo relações e comentários.
3. Consulte o estado atual do PR #35 e confirme branch, HEAD, Draft, CI e ausência de promoção.
4. Trate o HEAD indicado no checkpoint como referência histórica; use como base somente o HEAD atual confirmado no PR #35.
5. Compare o estado atual com o checkpoint.
6. Caso exista divergência, registre-a antes de executar mudanças.
7. Não peça ao usuário para repetir o histórico.

CONTEXTO CRÍTICO

O TriView RC4 apresentou uma falha grave no Linux Mint:

- abre e domina a frente do computador;
- não minimiza, maximiza ou restaura;
- menus do TriView não aparecem;
- Menu Iniciar e captura aparecem atrás;
- cliques não produzem resposta útil;
- o usuário precisa reiniciar o computador para recuperar o controle.

O Terminal também abriu externamente no teste anterior. A correção de roteamento já foi integrada na branch candidata e possui testes automáticos verdes, mas o reteste real do Terminal está bloqueado pela falha da janela principal.

DIAGNÓSTICO ATUAL

Hipóteses prioritárias já registradas na LEA-241:

1. root.overrideredirect(True) remove a janela do gerenciamento normal do Cinnamon/Muffin;
2. tk_popup() pode deixar grab preso quando o menu fica oculto ou falha;
3. ciclo <Configure> → _apply_compact_chrome → update_idletasks → novo <Configure> pode saturar o thread Tk;
4. o evento <Map> volta a ativar borderless após minimizar/restaurar;
5. não existe saída emergencial confiável.

EXECUÇÃO OBRIGATÓRIA DA LEA-241

1. Crie uma branch de remediação a partir do HEAD atual verificado do PR #35.
2. Remova o uso funcional de root.overrideredirect(True) da baseline de teste.
3. Devolva a janela ao gerenciamento normal do Cinnamon/Muffin.
4. Preserve inicialmente a barra de título nativa; estética não pode superar segurança operacional.
5. Substitua a maximização manual por mecanismo compatível com o gerenciador de janelas.
6. Remova a reativação de borderless no evento <Map>.
7. Proteja todos os tk_popup() com try/finally e grab_release().
8. Elimine ou limite o ciclo recursivo de Configure/update_idletasks.
9. Adicione um atalho de emergência documentado e testado para fechar o TriView.
10. Adicione testes automatizados que impeçam regressão de:
   - janela não gerenciada;
   - reativação de borderless;
   - popup sem liberação garantida;
   - event storm evidente;
   - ausência de escape de emergência.
11. Execute CI.
12. Não pare após criar a tarefa ou o PR.
13. Corrija falhas automáticas encontradas.
14. Integre somente na branch candidata do PR #35 após CI verde.
15. Fixe novo SHA imutável.
16. Atualize Linear e GitHub com causa, correção, testes e novo HEAD.
17. Somente então entregue ao usuário um comando seguro de instalação/reteste.

CRITÉRIOS DE ACEITE REAL DA LEA-241

- TriView não fica sempre à frente;
- Menu Iniciar aparece;
- Alt+Tab funciona;
- minimizar funciona;
- maximizar funciona;
- restaurar funciona;
- menus global e dos painéis aparecem e fecham;
- captura aparece acima quando acionada;
- fechar não exige reinício;
- saída emergencial funciona;
- nenhum dado estável é alterado;
- nenhuma promoção para train/road-to-1.0 ou main.

DEPOIS DO PASS DA LEA-241

Retome a LEA-229 exatamente no ponto interrompido:

1. revalidar Terminal incorporado;
2. validar PDF;
3. validar captura;
4. validar gravação;
5. validar plugins;
6. validar layouts;
7. validar sessões;
8. validar Workspace Hub;
9. executar LEA-240 com três chats GPT simultâneos;
10. executar LEA-239 para atalhos órfãos;
11. validar instalação, atualização, diagnóstico, backup e rollback;
12. executar RC independente;
13. apresentar gate de promoção ao Leo via Visualize;
14. promover somente com autorização explícita;
15. instalar e validar a release estável;
16. encerrar LEA-226 apenas como PASS_RELEASED_FOR_WORK.

REGRAS DE COMUNICAÇÃO E GOVERNANÇA

- Trabalhe em português do Brasil.
- Não use Codex.
- Não trate criação de LEA como execução.
- Não diga que o loop continuará depois da resposta sem execução real ou runtime durável.
- Use Visualize somente em decisão humana real com opções, recomendação, impactos e reversibilidade.
- Não gere imagem quando o pedido for explicação ou análise.
- Ao analisar vídeos, observe a janela inteira, sobreposição, menus, cliques, sistema operacional e efeitos após fechar.
- Distingua sempre: proposto, criado, implementado, integrado, testado automaticamente, testado no Linux Mint, aceito e liberado.
- Não solicite teste perigoso antes de CI verde e SHA imutável.
- Preserve a instalação estável e os dados do usuário.
- Continue o loop até PASS ou BLOCKED legítimo.

PRIMEIRA RESPOSTA AO USUÁRIO

Não faça apenas um resumo. Depois de verificar o estado, informe:

- o que foi confirmado;
- qualquer divergência encontrada;
- quais ações reais já foram executadas;
- o estado da LEA-241;
- o próximo gate operacional.
```

---

## Resultado esperado do novo chat

O novo chat deve recuperar o contexto pelo GitHub e Linear, continuar a remediação da LEA-241 e não reiniciar a discussão conceitual do projeto.

# Princípios do produto

## 1. O núcleo gerencia workspaces

O conceito principal é a área de trabalho. Navegadores, terminais, aplicações e documentos são tipos de painel e não devem controlar a arquitetura central.

## 2. Layouts são proporcionais

A organização visual deve usar regiões normalizadas e recalcular dimensões quando a janela mudar. Coordenadas fixas podem existir apenas em integrações específicas e nunca como regra principal do produto.

## 3. Cada painel é independente

Um painel deve possuir identidade, tipo, alvo, estado e ações próprias. A evolução de um tipo de painel não deve exigir alterações profundas nos demais.

## 4. Implementado e planejado não se confundem

A documentação, a interface e os releases devem distinguir claramente:

- **disponível:** implementado, testado e integrado;
- **experimental:** implementado, porém sujeito a limitações conhecidas;
- **planejado:** ainda não entregue.

## 5. Captura é um serviço separado

Print e gravação não devem ser responsabilidades do Layout Engine nem dos adaptadores de painel. O Capture Engine receberá a identidade e os limites do painel e executará a captura através do backend compatível com a sessão gráfica.

## 6. Segurança antes de atualização

Toda atualização deve preservar dados, criar backup e validar a nova versão antes de ativá-la. A instalação anterior não deve ser destruída durante uma migração sem confirmação e mecanismo de restauração.

## 7. Evolução incremental

Cada tarefa deve produzir uma mudança limitada, testável e rastreável. A sequência preferida é:

1. definir o problema;
2. registrar a tarefa;
3. implementar somente o escopo aprovado;
4. validar;
5. documentar;
6. integrar;
7. entregar atualização quando houver mudança funcional.

## 8. Adaptadores protegem o domínio

Detalhes de Brave, Chrome, terminal, X11, Wayland ou outras tecnologias devem ficar atrás de contratos e adaptadores. Os modelos centrais não devem conhecer comandos específicos do sistema.

## 9. Persistência deve ser versionada

Workspaces, sessões e configurações persistidas deverão possuir versão de esquema antes de mudanças incompatíveis.

## 10. Experiência visual serve ao conteúdo

Margens, cabeçalhos e controles devem consumir apenas o espaço necessário. Quando os painéis reais forem incorporados, a maior parte da área útil deve ser destinada ao conteúdo.

## 11. Observabilidade é obrigatória

Falhas de inicialização, atualização, incorporação e captura devem gerar mensagens claras e logs localizáveis pelo usuário.

## 12. O repositório é a fonte técnica oficial

Decisões aprovadas, estado do produto, roadmap, releases e processo de desenvolvimento devem permanecer no repositório e vinculados às tarefas do Linear.

# TriView Visual Evolution 1.0

## 1. Objetivo

Transformar a interface atual do TriView em uma central de trabalho desktop moderna, clara e responsiva, preservando o funcionamento das LEAs 198–205 e preparando a base visual para a versão 1.0.

A mudança deve ser percebida imediatamente pelo usuário, não apenas pela troca de cores, mas pela reorganização estrutural da aplicação.

## 2. Problemas observados

- cabeçalho montado por múltiplas classes usando `pack(side="right")`;
- ordem dos botões dependente da cadeia de herança;
- selo de versão alterado por busca recursiva baseada em texto;
- ações cortadas em telas menores;
- cartões muito altos e com grande área vazia;
- pouca distinção entre navegação, conteúdo e estado;
- componentes Tkinter estilizados localmente, sem fonte única de verdade;
- diálogos visuais desconectados da tela principal;
- estados semânticos não centralizados.

## 3. Princípios do novo design

1. **Clareza operacional:** o usuário deve identificar rapidamente onde está, o que está ativo e qual ação executar.
2. **Densidade equilibrada:** utilizar melhor o espaço sem tornar a interface apertada.
3. **Consistência:** todos os componentes devem compartilhar tokens visuais.
4. **Responsividade real:** reorganizar componentes, não apenas reduzir largura.
5. **Evolução sem regressão:** manter dados, integrações e comportamento atual.
6. **Identidade própria:** aparência técnica e moderna, sem copiar outros produtos.

## 4. Wireframe conceitual

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ TriView  Workspace atual: Desenvolvimento                 v1.0 • Operacional │
├──────────────┬───────────────────────────────────────────────────────────────┤
│              │ [Workspace] [Layout] [Hub] [Plugins]            [⋯ Sistema] │
│ NAVEGAÇÃO    ├───────────────────────────────────────────────────────────────┤
│              │                                                               │
│ • Visão geral│   ┌────────────────┐ ┌────────────────┐ ┌────────────────┐   │
│ • Workspaces │   │ ChatGPT        │ │ GitHub         │ │ Terminal       │   │
│ • Layouts    │   │ Browser        │ │ Browser        │ │ Bash           │   │
│ • Hub        │   │ DISPONÍVEL     │ │ DISPONÍVEL     │ │ ATIVO          │   │
│ • Plugins    │   │                │ │                │ │                │   │
│              │   │ conteúdo       │ │ conteúdo       │ │ conteúdo       │   │
│              │   │                │ │                │ │                │   │
│              │   │ [Abrir] [⋯]    │ │ [Abrir] [⋯]    │ │ [Reabrir] [⋯] │   │
│              │   └────────────────┘ └────────────────┘ └────────────────┘   │
│              │                                                               │
├──────────────┴───────────────────────────────────────────────────────────────┤
│ 3 painéis • 1 ativo • sessão salva • dados locais                    21:36  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 5. Estrutura visual proposta

### 5.1 Barra superior

Responsabilidades:

- marca TriView;
- workspace ativo;
- modo operacional;
- versão única da aplicação;
- acesso às ações globais.

A barra superior não deve ser construída por subclasses adicionando botões individualmente. Ela deve receber uma coleção declarativa de ações.

### 5.2 Navegação lateral

Primeira fase:

- Visão geral;
- Workspaces;
- Layouts;
- Workspace Hub;
- Plugins.

Em telas estreitas, a navegação poderá recolher para ícones.

### 5.3 Área principal

- grade de painéis;
- espaçamento adaptável;
- cartões com altura mínima e expansão controlada;
- conteúdo incorporado ocupando a maior área possível.

### 5.4 Barra de status

Exibir:

- quantidade de painéis;
- painéis ativos;
- estado de persistência;
- modo de execução;
- mensagens temporárias.

## 6. Design system

### 6.1 Tokens de cor

```text
background.base       #07101F
background.surface    #0D1729
background.elevated   #132038
border.default        #263752
text.primary          #F4F7FB
text.secondary        #9EB0C9
accent.primary        #22B8F0
accent.secondary      #6D7CFF
state.success         #22C55E
state.warning         #F59E0B
state.danger          #EF4444
state.info            #0EA5E9
```

As cores poderão ser ajustadas durante a validação de contraste.

### 6.2 Espaçamento

Escala base:

```text
4, 8, 12, 16, 24, 32
```

### 6.3 Tipografia

- títulos: peso forte;
- textos operacionais: peso regular;
- destinos e comandos: fonte monoespaçada quando disponível;
- evitar textos longos centralizados dentro dos cartões.

### 6.4 Estados

| Estado | Significado | Tratamento |
|---|---|---|
| DISPONÍVEL | pode ser aberto | azul/ciano |
| ATIVO | sessão em execução | verde |
| PLANEJADO | ainda não implementado | neutro |
| INDISPONÍVEL | dependência ausente ou falha | vermelho |
| EXTERNO | executando fora da aplicação | âmbar |

## 7. Arquitetura visual

### 7.1 Novos módulos propostos

```text
src/triview_workspace/ui/
├── __init__.py
├── theme.py
├── tokens.py
├── components.py
├── header.py
├── navigation.py
├── status_bar.py
└── dialogs.py
```

### 7.2 Responsabilidades

- `tokens.py`: valores visuais imutáveis;
- `theme.py`: configuração de estilos Tk/ttk;
- `components.py`: botões, badges, cards e campos reutilizáveis;
- `header.py`: cabeçalho único e declarativo;
- `navigation.py`: navegação lateral;
- `status_bar.py`: status global;
- `dialogs.py`: base comum para diálogos.

### 7.3 Fonte única de versão

Criar uma constante central:

```text
APP_VERSION
APP_CHANNEL
APP_STAGE
```

Nenhuma camada deverá procurar labels pelo texto para substituir o selo.

### 7.4 Registro declarativo de ações

Exemplo conceitual:

```text
HeaderAction(id, label, command, group, priority, visibility)
```

As extensões registram ações; o cabeçalho decide ordem, agrupamento e responsividade.

## 8. Estratégia de implementação

### Etapa 1 — estabilização

- corrigir o selo;
- impedir cortes no cabeçalho;
- eliminar a busca recursiva baseada em prefixos de texto;
- adicionar testes de regressão.

### Etapa 2 — fundação visual

- criar tokens;
- criar tema;
- criar componentes reutilizáveis;
- aplicar na janela principal.

### Etapa 3 — novo shell

- barra superior;
- navegação;
- área principal;
- barra de status.

### Etapa 4 — cartões

- novo cabeçalho do cartão;
- novo bloco de estado;
- ações compactas;
- melhor uso do conteúdo incorporado.

### Etapa 5 — diálogos

- editor de painéis;
- editor de layout;
- Workspace Hub;
- mensagens operacionais.

### Etapa 6 — validação

- 1024×600;
- 1366×768;
- 1920×1080;
- abertura e incorporação de terminal/editor;
- persistência de workspaces;
- recuperação de sessão;
- compatibilidade Linux Mint.

## 9. Riscos

### Risco 1 — regressão funcional

Mitigação: manter motores e persistência isolados da camada visual.

### Risco 2 — herança atual dificultar o redesign

Mitigação: introduzir componentes novos gradualmente e reduzir mutações pós-construção.

### Risco 3 — limitações do Tkinter

Mitigação: concluir a evolução 1.0 no toolkit atual e avaliar migração futura separadamente.

### Risco 4 — interface pesada em notebook antigo

Mitigação: evitar animações complexas, imagens grandes e atualização contínua desnecessária.

## 10. Critério de conclusão

O redesign será considerado concluído quando:

- a aparência indicar claramente uma nova geração do produto;
- a interface permanecer funcional em telas pequenas;
- os recursos das LEAs 198–205 continuarem operacionais;
- o cabeçalho tiver uma única arquitetura;
- os cartões e diálogos usarem o mesmo design system;
- testes automatizados e validação manual no Linux Mint forem aprovados.

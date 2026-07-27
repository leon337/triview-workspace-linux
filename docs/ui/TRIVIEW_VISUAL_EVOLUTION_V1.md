# TriView Visual Evolution 1.0

## Estado da implementação

A primeira implementação funcional do redesign foi concluída no candidato da branch `feat/triview-visual-evolution-v1`.

### Entregue

- design system central em `ui_design.py`;
- versão única `1.0.0a1`;
- cabeçalho declarativo e responsivo;
- reorganização automática do cabeçalho abaixo de 1180 px;
- remoção da substituição recursiva de selos por texto;
- ações `Workspace Hub`, `Novo layout` e `Plugins` registradas por ID e prioridade;
- cartões de painéis redesenhados;
- barra global de status e métricas;
- editor de painéis redesenhado;
- editor de layouts redesenhado;
- Workspace Hub redesenhado;
- entrada principal corrigida para iniciar o shell completo;
- testes automatizados do design system;
- CI aprovada no HEAD inicial da implementação.

### Validação manual pendente

- 1024×600 no Linux Mint;
- 1366×768 no Linux Mint;
- abertura e incorporação do terminal;
- abertura e incorporação do editor;
- Workspace Hub;
- criação de layout;
- persistência e recuperação de sessão.

## Objetivo

Transformar a interface atual do TriView em uma central de trabalho desktop moderna, clara e responsiva, preservando o funcionamento das LEAs 198–205 e preparando a base visual para a versão 1.0.

## Problemas corrigidos

- cabeçalho montado por múltiplas classes usando `pack(side="right")`;
- ordem dos botões dependente da cadeia de herança;
- selo de versão alterado por busca recursiva baseada em texto;
- ações cortadas em telas menores;
- cartões com grande área vazia e pouca hierarquia;
- componentes sem fonte visual única;
- diálogos desconectados da tela principal;
- entrada principal apontando para uma camada incompleta da aplicação.

## Arquitetura aplicada

```text
Extensões
   │
   ├── Workspace Hub
   ├── Novo layout
   └── Plugins
           │
           ▼
Registro declarativo de ações
           │
           ▼
Cabeçalho central responsivo
           │
           ├── modo wide: ações na mesma linha
           └── modo compact: ações em uma terceira linha
```

## Design system

A fonte central de cores, estados, botões, tipografia e responsividade está em:

```text
src/triview_workspace/ui_design.py
```

Estados padronizados:

- `PLANEJADO`;
- `DISPONÍVEL`;
- `INDISPONÍVEL`;
- `ABRINDO`;
- `ATIVO`;
- `EXTERNO`;
- `ERRO`;
- `GRAVANDO`;
- `GRAVADO`.

## Fonte única de versão

A versão é definida em:

```text
src/triview_workspace/__init__.py
pyproject.toml
```

A interface deriva o selo dessa versão. As camadas não procuram mais labels pelo texto para substituir o selo.

## Critérios de conclusão

- [x] cabeçalho com arquitetura única;
- [x] ações ordenadas independentemente da cadeia de herança;
- [x] versão com fonte explícita;
- [x] design system central;
- [x] cartões redesenhados;
- [x] editor de painéis redesenhado;
- [x] editor de layouts redesenhado;
- [x] Workspace Hub redesenhado;
- [x] entrada principal carrega o shell completo;
- [x] testes automatizados básicos;
- [x] CI aprovada;
- [ ] validação funcional manual no Linux Mint;
- [ ] revisão visual final após capturas reais;

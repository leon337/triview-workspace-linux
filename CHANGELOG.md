# Changelog

## 0.4.0 — Application Engine e Panel Runtime

- adiciona `PanelRuntime` comum para processos e janelas não web;
- divide comandos com `shlex` e executa sem `shell=True`;
- valida e resolve o executável antes da abertura;
- adiciona `ApplicationPanelAdapter` ao registro de painéis;
- implementa `ApplicationEngine` com sessões independentes;
- implementa backend X11 com localização por PID, classe e nome;
- incorpora aplicações compatíveis com `xdotool windowreparent`;
- usa fallback explícito para janela externa quando a incorporação falha;
- adiciona estados Disponível, Abrindo, Ativo, Externo, Indisponível e Erro;
- redimensiona e encerra aplicações controladas;
- preserva Browser Engine e workspaces persistentes;
- adiciona instalador isolado de candidatos do trem;
- adiciona testes de comando, adaptador, ciclo de vida e fallback;
- registra ADR-0005 e o trem LEA-197–205.

Limite: a promoção para `main` depende de CI e validação real no Linux Mint. O backend inicial de incorporação continua baseado em X11.

## 0.3.0 — Workspaces persistentes

- adiciona catálogo JSON com `schema_version` explícito;
- grava alterações de forma atômica, sem expor arquivo parcial;
- restaura automaticamente o último workspace utilizado;
- permite criar uma cópia, renomear, editar e excluir workspaces;
- permite editar títulos, tipos e destinos dos painéis;
- permite selecionar layouts disponíveis;
- preserva ao menos um workspace para impedir catálogo vazio;
- migra automaticamente o bundle único legado para o catálogo versionado;
- preserva arquivos corrompidos com sufixo de quarentena e restaura o padrão;
- adiciona `WorkspaceSessionEngine` desacoplado da interface;
- adiciona `WorkspaceRepository` em infraestrutura;
- mantém dados fora dos diretórios versionados do atualizador;
- estende o diagnóstico com esquema, catálogo e workspace ativo;
- adiciona testes de persistência, migração, recuperação e ciclo de sessão;
- atualiza interface, README, arquitetura, roadmap e histórico.

## 0.2.0 — Primeiro Browser Engine funcional

- adiciona contrato explícito para backends de navegador;
- valida e normaliza URLs HTTP e HTTPS;
- adiciona `BrowserPanelAdapter` ao registro de painéis da interface;
- implementa backend inicial para Brave/Chromium em X11;
- incorpora a janela do navegador no host nativo do painel com `xdotool`;
- cria perfis locais separados por identidade de painel;
- adiciona estados visuais disponível, abrindo, ativo, indisponível e erro;
- mantém a interface aberta quando o backend não está disponível;
- redimensiona a janela incorporada junto com o painel;
- encerra sessões abertas ao fechar o TriView Workspace;
- preserva o modo CLI `--diagnostic` sem abrir a interface;
- adiciona testes de URL, adaptador, ciclo de vida e fallback;
- registra a ADR-0003 sobre a estratégia X11 inicial;
- atualiza roadmap, histórico, README e documentação dos Engines.

## Consolidação documental — LEA-194

- adiciona índice central em `docs/README.md`;
- registra visão, princípios e roadmap do produto;
- consolida o histórico explicado das versões iniciais;
- documenta responsabilidades e estado dos Engines;
- cria o manual operacional da Fábrica de Softwares;
- registra a ADR-0002 sobre governança documental;
- adiciona testes para arquivos obrigatórios e links Markdown internos.

## 0.1.2 — Interface gráfica inicial

- corrige o atalho principal;
- adiciona janela desktop real;
- exibe três painéis móveis responsivos;
- recalcula o layout ao redimensionar;
- mantém a CLI com `--diagnostic`.

## 0.1.1 — Migração segura

- adiciona migrador da instalação legada;
- cria backup integral;
- instala versões com troca atômica;
- adiciona restaurador e atualizador.

## 0.1.0 — Fundação

- estrutura modular inicial;
- modelos de workspace, layout e painel;
- Layout Engine proporcional;
- registro extensível de adaptadores;
- testes automatizados e documentação arquitetural.

# ADR-0005 — Application Engine sobre um Panel Runtime comum

Status: aceito

Data: 2026-07-25

## Contexto

Browser, aplicações, terminais e visualizadores PDF precisam controlar processos, localizar janelas, incorporar superfícies, redimensionar e encerrar sessões. Repetir essa lógica em cada Engine aumentaria acoplamento e divergência.

Também existem aplicações Linux que não aceitam `windowreparent`, reutilizam processos existentes ou não expõem uma janela X11 previsível. O produto precisa continuar útil nesses casos.

## Decisão

Criar um `Panel Runtime` neutro para processos e janelas, separado da GUI e dos modelos persistentes.

O runtime oferece:

- resolução segura de executáveis sem `shell=True`;
- inicialização de processo em sessão própria;
- localização de janela por PID e pistas de classe/nome;
- incorporação com `xdotool windowreparent` quando suportada;
- redimensionamento e encerramento controlados;
- fallback para janela externa quando a incorporação não for possível.

O `Application Engine` usa esse runtime e registra um `ApplicationPanelAdapter`. Terminal e PDF deverão reutilizar a mesma fundação nas LEAs seguintes.

## Segurança

- comandos são divididos com `shlex` e executados como lista de argumentos;
- nenhuma linha é entregue a um shell;
- o executável precisa existir e ser executável;
- falhas não encerram a interface;
- fallback externo é explícito no estado visual;
- processos iniciados pelo TriView são encerrados pelo respectivo Engine.

## Consequências

### Positivas

- fundação compartilhada para Application, Terminal e PDF Engines;
- menor duplicação de código X11;
- fallback controlado para programas incompatíveis;
- testes headless dos contratos e do ciclo de vida;
- futura substituição por backend Wayland sem alterar o domínio.

### Limites

- o primeiro backend de incorporação continua dependente de X11 e `xdotool`;
- aplicações que reutilizam processos ou janelas existentes podem cair no modo externo;
- compatibilidade visual exige teste no Linux Mint real;
- o runtime não concede privilégios nem instala programas ausentes.

## Alternativas rejeitadas

1. Duplicar a lógica do Browser Engine em cada novo Engine: rejeitada por acoplamento e manutenção.
2. Exigir incorporação para toda aplicação: rejeitada porque muitas aplicações não aceitam reparenting.
3. Executar comandos através de shell: rejeitada por risco de interpretação de operadores e expansão.

# LEA-229 — Primeiro resultado no Linux Mint

## Candidato

- PR: #35
- HEAD testado: `96689f8c61984a72d4cbc325ae377774315df8d3`
- versão: `1.0.0a1`
- evidência: vídeo `1000827436.mp4`

## Resultado sequencial

1. instalação isolada por SHA: PASS;
2. atalho candidato no menu: PASS;
3. abertura da RC4: PASS;
4. painel ChatGPT incorporado: PASS;
5. painel GitHub incorporado: PASS;
6. painel Terminal: FAIL — estado `EXTERNO`;
7. encerramento: a janela externa do Terminal permaneceu aberta;
8. resíduo: `triview-workspace-dev.desktop` aponta para launcher inexistente.

## Primeira causa responsável

O seed `config/workspaces/three-mobile.json` declara o painel Terminal como `application` com target `x-terminal-emulator`. A aplicação seleciona `ApplicationRuntimeController`, portanto o controlador RC4 `EmbeddedOnlyTerminalBackend` não participa da abertura.

## Veredito

`FAIL_LEA_198_CONFIGURATION_ROUTING`

A remediação deve alterar o painel para `kind=terminal`, usar um shell válido como target, adicionar regressão e retomar o aceite nesta etapa.

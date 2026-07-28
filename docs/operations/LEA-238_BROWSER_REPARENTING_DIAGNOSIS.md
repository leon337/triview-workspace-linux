# LEA-238 — Diagnóstico da regressão de incorporação do Browser

## Evidência Linux Mint

- Terminal incorporado corretamente no terceiro painel.
- ChatGPT 1 e ChatGPT 2 abriram como janelas externas.
- Configuração persistida dos painéis permaneceu correta.

## Causa técnica

O backend atômico do navegador executava a confirmação do parent X11 **antes** de mapear a janela Chromium. No Cinnamon/Muffin, uma janela Chromium pode ser retomada pelo gerenciador de janelas no momento do `windowmap`, voltando a ser filha da raiz e aparecendo externamente.

O fluxo anterior era:

```text
unmap -> reparent -> confirmar parent -> map
```

A confirmação era verdadeira enquanto a janela ainda estava oculta, mas não validava o estado final depois do mapeamento.

## Contrato corrigido

```text
unmap -> reparent -> move -> map -> confirmar parent estável
```

Se o Muffin retomar a janela, a transação é repetida de forma limitada. Se não houver parent estável, a abertura falha fechada e encerra a janela/processo, sem aceitar fallback externo.

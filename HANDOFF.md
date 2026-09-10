# Handoff — Maestro fork standalone (2026-09-10)

## Estado e escopo

Fork local baseado em `Blizaine/Maestro v2.0.1`, executado por scripts Bash e
ambiente Python local. Os scripts e menus do antigo launcher foram removidos.
Compatibilidade com configurações legadas ainda existe no backend; referências
históricas não significam dependência do launcher.

O HEAD verificado antes desta revisão é `1c3a241`, que já inclui o alinhamento
dos headers e a versão anterior deste handoff. As correções descritas abaixo
estão no working tree, sem commit nem push. Não use uma contagem antiga de
commits à frente do remoto como estado atual; consulte `git status` e `git log`.

## Como executar

Siga [README — Install](README.md#install) para criar `app/env` com Python 3.12,
PyTorch 2.7.1/CUDA 12.8 e dependências, e construir a UI.

```bash
./start_local.sh                 # 127.0.0.1:7860
./start_local.sh --port 7900     # porta explícita
./start_local.sh --share         # 0.0.0.0, acesso LAN
./start_local.sh --compile       # encaminha --compile ao backend
./stop_local.sh
```

O script seleciona `env-sol` → `env-rtx50` → `env`, informa GPU/driver,
constrói a UI se `ui/dist/index.html` estiver ausente, inicia o backend e
aguarda resposta HTTP de sucesso. O probe usa loopback e ignora proxies do
ambiente, inclusive com `--share`. Portas inválidas são rejeitadas antes do
lançamento. PID e log ficam em `app/.launcher.pid` e `app/.launcher.log`.

`SERVER_NAME` explícito agora prevalece sobre `PINOKIO_SHARE_LOCAL`. Assim,
a variável legada não inverte o comportamento de `start_local.sh`. Em execução
direta de `launch.py`, ela continua servindo de fallback sem `SERVER_NAME`.

Rebuild após mudanças de frontend: `cd ui && npm run build`. O script não
detecta código-fonte mais recente quando já existe um bundle.

## Implementações confirmadas

- **Interface reorganizada:** cinco abas centrais no header: Projects,
  Director, Editor, Medias e Configurations. Projects é a página inicial.
- **Projects:** espaços de trabalho com criação, pesquisa, abertura e exclusão
  confirmada. Atalhos para Director, Editor, Medias e produções salvas.
- **Director:** Planning e Studio na mesma seção. Revisão/aprovação e progresso
  de produção continuam acessíveis, inclusive em telas pequenas.
- **Skills:** Music Video e Short Film disponíveis; Video Podcast e Viral
  Video permanecem desabilitados como funcionalidades futuras.
- **Configurations:** página própria com Performance, Integrations e Notifications.
- **Barra de status:** única e global, em toda a largura inferior. Projeto ativo,
  contagem de mídias, GPU/VRAM, CPU/RAM e modelo; detalhes expansíveis acima.
- **Editor:** troca de abas preserva histórico e salva alterações pendentes.
- **Compatibilidade:** atalhos antigos para Studio/Director/Editor selecionam a
  aba correspondente; a flag legada não oculta mais a navegação Director.
- **Documentação:** CHANGELOG corrigido para os defaults atuais; README substitui menus removidos por instruções standalone. Mensagens
  de erro de PyTorch e porta não encaminham mais ao antigo launcher.
- **Controle:** `ui/scripts/control-gauntlet.mjs` verifica snapshots, revisão
  persistida, reordenação e operações na timeline.
- **Acesso remoto integrado removido:** serviço Tailscale, rotas, controles
  da interface, guia de configuração e dependência de QR code foram removidos.
  Notificações e acesso LAN via `--share` permanecem.

## Histórico corrigido

- `ac399a5`: defaults do Director.
- `d3f59b6`: limpeza de documentação e exclusão de documentos pessoais/runner.
- `d798e60`: adicionou **documentação**, não implementação de monitoramento.
  O relatório de monitoramento descrevia uma coleta temporária da sessão,
  sem serviço permanente. Logs e UI de acompanhamento existentes não devem
  ser confundidos com um coletor contínuo novo.
- `2f96b76`: removeu a antiga suíte Python. Ela não foi restaurada integralmente.
  Esta revisão adiciona apenas `tests/test_standalone_launch.py` para as
  regressões de execução standalone. Os testes em `ui/` permanecem disponíveis.

## Validação

Na análise anterior às correções:

- UI: `npm run build` aprovado, incluindo TypeScript; avisos de bundle grande
  e import estático/dinâmico, sem erro de build.
- `npm run test:control`: aprovado.
- Instância existente: `/`, `/classic/` e `/docs` responderam HTTP 200.
- Imports: torch `2.7.1+cu128`, mmgp `3.7.12`, diffusers `0.36.0`,
  transformers `4.57.1`, fastapi `0.141.1`, gradio `5.29.0` aprovados.
- CUDA 12.8 disponível; RTX 3060, driver 595.84.

Após as correções: os três testes standalone passaram (incluindo seis casos
de precedência, seis entradas de porta inválidas e dois ciclos de início/parada).
Os testes de controle da UI, a sintaxe Bash/Python e `git diff --check` também
passaram. Para repetir sem carregar modelos:

```bash
python3 tests/test_standalone_launch.py
bash -n start_local.sh stop_local.sh
python3 -m py_compile app/launch.py
(cd ui && npm run test:control)
git diff --check
```

O teste standalone cobre prioridade de endereço, porta inválida e início/parada
com backend HTTP temporário, tanto em loopback quanto com `--share`, incluindo
ambiente com proxy inválido. Não é um teste de geração ou do backend completo.

## Limites e próximos passos

- Reiniciar a instância real para carregar alterações de Python. A revisão
  preservou a instância aberta; o teste de ciclo de vida usa uma cópia isolada.
- Geração real de imagem/vídeo não foi executada nesta revisão.
- O launcher ainda encerra a instância do pidfile e um processo ocupando a porta
  solicitada. Escolha uma porta livre quando houver outros serviços locais.
- O backend pode escolher outra porta se a solicitada ficar ocupada durante
  o lançamento; o probe do script observa a porta solicitada. Essa corrida
  não é coberta pela validação atual.
- Não há coletor de monitoramento permanente entregue por esta revisão.

## Verificação visual da nova interface

Com o backend e o Vite (`cd ui && npm run dev`) ativos, execute:

```bash
python tests/test_application_shell.py
```

Requer Playwright com Chromium instalado. O teste usa cinco larguras de tela,
verifica centralização das abas e geometria do rodapé em todas as seções,
atalhos, configurações, revisão do Director, persistência do Editor e CRUD de
projetos. As gravações de projetos exercitadas pelo teste são interceptadas;
as fixtures não são persistidas no backend. Capturas e resultado vão para
`/tmp/maestro-overhaul` por padrão.

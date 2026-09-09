# Aplicação local: monitoramento de 09/09/2026

Aplicação aberta em http://127.0.0.1:7860/ pelo navegador padrão. Processo 306397 executando `launch.py`, com diretório de trabalho confirmado em `/home/yuri/Documentos/maestro/app`. Interface servida de `/home/yuri/Documentos/maestro/ui/dist`.

O lançamento foi direto pelo terminal. Apenas o interpretador e as dependências foram reutilizados de `/home/yuri/Aplicativos/pinokio/api/Maestro.git/app/env/bin/python`; o código e as configurações são desta pasta de projeto. A outra instância, porta 42003, já estava aberta e foi preservada.

## Observações iniciais

- Backend inicializado, com 199 modelos registrados (registro não significa pesos disponíveis).
- Navegação real entre Studio, Director e Editor, com zero erros JavaScript e zero respostas HTTP >= 400 nas sessões automatizadas.
- Carregamento inicial do documento: aproximadamente 204 ms no Chromium local; isso não mede tempo de geração nem conclusão de todas as consultas assíncronas.
- Layout móvel em 390 px sem overflow horizontal; captura salva.
- 28/28 consultas de telemetria bem-sucedidas entre 2026-09-09T13:54:46 e 2026-09-09T13:57:03 (horário do sistema em UTC).
- Latência da telemetria: mediana 5.5 ms, mínimo 3.8 ms, máximo 91.4 ms. Amostra local sem carga de geração.
- RAM residente do processo: aproximadamente 1,36 GiB após carregar a interface.
- CPU em intervalo separado de 10 segundos: 1,1% de um núcleo.
- VRAM atribuída à nova instância: 122 MiB; nenhum modelo de geração carregado.
- GPU global: aproximadamente 9,5 GiB ocupados em uma RTX 3060 de 12 GiB. O `llama-server` do Unsloth já utilizava 8.876 MiB. A atividade global da GPU não deve ser atribuída a esta instância do Maestro.

## Pontos identificados

A instalação local iniciou com configurações próprias, sem pastas de modelos vinculadas e com galeria vazia. O primeiro boot aplicou automaticamente o perfil 4.5 de memória. Os modelos selecionáveis ainda podem exigir download ou vinculação de pesos existentes.

O runtime informou ausência de kernels CUDA GGUF, Lightx2v NVFP4 e H3 Sol Engine. Há caminhos de fallback; isso pode afetar execuções que utilizem esses formatos, mas não provocou falha de inicialização. Triton, SageAttention e FlashAttention foram reconhecidos. Dois guias DramaBox estão ausentes; o código contém prompts de fallback correspondentes.

Não foi iniciada uma geração de imagem/vídeo. Portanto, qualidade, velocidade sob carga e comportamento do fluxo de aprovação com modelos reais continuam sem medição nesta sessão.

## Coleta e arquivos

A aplicação permanece aberta. Um coletor separado foi iniciado para 60 amostras, espaçadas em 5 segundos (aproximadamente cinco minutos no total); a janela ainda estava em andamento ao escrever este relatório. O coletor termina automaticamente, enquanto o servidor continua aberto. Não há promessa de acompanhamento humano/agente permanente após a resposta.

- Log do servidor: `/tmp/maestro-project-monitor/server.log`
- Amostras incrementais: `/tmp/maestro-project-monitor/samples.jsonl`
- Navegação e erros: `/tmp/maestro-project-monitor/navigation.json`
- Carregamento inicial: `/tmp/maestro-project-monitor/browser.json`
- CPU/VRAM por processo: `/tmp/maestro-project-monitor/idle.json`
- Capturas: `/tmp/maestro-project-monitor/studio.png`, `director.png`, `editor.png`, `mobile.png`.

Esses arquivos estão em diretório temporário e podem desaparecer após limpeza/reinicialização do sistema.

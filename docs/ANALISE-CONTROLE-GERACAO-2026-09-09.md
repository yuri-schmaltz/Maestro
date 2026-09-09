# Análise do fluxo e controle de geração — Maestro

Data: 09/09/2026. Escopo: checkout local em `main`, versão declarada 2.0.1, incluindo alterações locais ainda não commitadas. Análise de código, interfaces declaradas e testes direcionados; não houve avaliação visual no navegador nem geração com modelos/GPU.

## Diagnóstico

O Maestro já oferece bastante controle técnico, mas o controle criativo está distribuído entre Studio, Director, dashboard, fila e Editor. O maior ganho virá de tornar explícito o que a IA pode decidir, permitir aprovação por etapa e vincular cada execução à versão aprovada.

O objetivo recomendado é: **ideia → plano editável → imagens de referência aprovadas → pedido congelado → geração seletiva → comparação de tomadas → edição**. Automatização continua disponível como escolha consciente.

## O que existe de fato

| Área | Recursos encontrados | Oportunidade |
|---|---|---|
| Studio | Modelos, referências, LoRAs, parâmetros, planejamento por janelas e envio à fila | Unificar a revisão da intenção, referências e parâmetros efetivos |
| Director | Planejamento estruturado; modo manual; pausas para prompts e imagens | Aprovação persistente e granular, inclusive quando há fila |
| Dashboard | Imagens, keyframes, prompts, diferenças do polish, marcações e regeneração por cena | Transformar acompanhamento e correção em espaço central de pré-produção |
| Recuperação | Checkpoints, revisões de projetos Director, cópia de assets e Load Settings | Vincular aprovação e tomadas aos artefatos existentes |
| Editor | Histórico, versões de projeto, bloqueio de trilhas e retorno de um clipe pela IA | Unificar seleção da tomada aprovada entre produção e timeline |
| Reutilização | Recipes, biblioteca de personagens Omni e referências | Presets também para regras criativas, com escopo claro por projeto |

Evidências: `ui/src/components/Sidebar/DirectorPanel.tsx:549`, `ui/src/components/DirectorDashboard/DirectorDashboard.tsx:187`, `app/services/director_pipeline.py:1234`, `app/services/director/schema.py`, `ui/src/editor/useEditorStore.ts`, `ui/src/components/Recipes/RecipesOverlay.tsx`.

Há trabalho local em andamento: painel `GenerationReviewPanel`, resumo em `generationPlan.ts`, revisão no botão Generate e edição/reordenação das janelas H3. Deve ser aproveitado, mas não tratado como funcionalidade final validada ponta a ponta.

O `HANDOFF.md` descreve outro worktree e uma sprint 2.1 com observabilidade, hooks e componentes que não encontrei nos caminhos indicados neste checkout. Suas alegações de entrega/testes não comprovam o estado desta aplicação. O manifesto local também não lista `cmdk` ou `comlink`.

## Lacunas prioritárias e evidências

### 1. A confirmação local ainda não está vinculada ao pedido executado — P0

Em `ui/src/stores/useStore.ts:6055`, `confirmGenerationReview` descarta o plano e chama `startGeneration`, que consulta novamente o estado e recalcula decisões. Existe congelamento posterior da configuração no caminho de envio, mas não do pedido que foi revisado.

Consequência: a interface não garante que a configuração examinada seja a executada se o estado mudar entre revisão e envio. É uma lacuna de contrato constatada no código; não reproduzi uma corrida no navegador.

Proposta: criar um plano resolvido e versionado, incluindo prompts efetivos por janela, assets, funções das referências, modelo, parâmetros e política de IA. Confirmar esse identificador/revisão. Mudanças posteriores criam outra revisão ou invalidam a aprovação.

Critério de aceite: alterar o formulário depois de abrir a revisão nunca muda silenciosamente o job aprovado; o backend executa aquela revisão ou pede revisão atualizada.

### 2. Planejamento posterior à revisão e fila automática — P0

O Studio pode adiar o enhancement até a execução quando há geração em andamento (`useStore.ts:6200`). O painel informa esse adiamento, mas também afirma que mostra o pedido exato. Para múltiplas janelas, seu resumo não contém a lista completa de prompts efetivos.

No Director, `enqueue_director_pipeline` e `update_director_queue_entry` forçam `auto_mode=True` (`app/services/director_pipeline.py:3245` e `:3276`). Há pausas reais no modo manual, em `:5466` e `:5601`, mas a fila elimina esse comportamento. O teste de fila confirma o modo automático como comportamento atual esperado. Revisões previamente preparadas já conseguem reutilizar planos e imagens; isso deve ser preservado.

Proposta: separar tarefas de planejamento das de renderização. Se a GPU estiver ocupada, o planejamento pode aguardar; ao terminar, o projeto fica “aguardando revisão”, sem iniciar vídeo automaticamente no modo supervisionado. A fila deve continuar com outros trabalhos aptos, sem manter recursos ocupados esperando o usuário.

Critério de aceite: um job supervisionado nunca transforma um prompt revisado por IA e começa a renderizar sem disponibilizar essa nova versão para aprovação. Fechar/reabrir o navegador preserva a etapa pendente.

### 3. O resumo pré-geração precisa ser completo e específico ao fluxo — P0

`GenerationReviewPanel.tsx` mostra prompt, modelo, resolução, duração, steps, CFG, seed, nomes das LoRAs e quantidade. Não mostra miniaturas/funções dos assets, pesos de LoRA, prompt negativo ou todas as opções específicas do workflow. O texto e as unidades são predominantemente de vídeo, embora o plano aceite imagem, áudio e ferramentas. Algumas dimensões são explicitamente aproximadas.

Proposta: revisão adaptada ao workflow, com referências visuais e sua função, prompt original versus efetivo, pesos, quantidade/unidades corretas e distinção entre valores resolvidos e pendentes. Uma única função/serviço deve resolver o pedido para revisão e execução; tabelas e regras duplicadas tendem a divergir.

Critério de aceite: a revisão não apresenta valor estimado como definitivo nem omite uma entrada que altera materialmente a geração; o payload aprovado corresponde ao consumido pelo executor.

### 4. Automação não expressa quais decisões criativas estão autorizadas — P1

O Director inicia com `directorAutoMode: true` (`useStore.ts:9803`); a revisão recorrente local do Studio começa desligada (`:9196`). Há modos Faithful/Creative, prompts estruturados e proteções de diálogo, mas isso não equivale a bloqueios editáveis por campo em um projeto.

Proposta: oferecer perfis “Manual”, “Assistido” e “Automático”. No assistido, permitir marcar: preservar fala literal, identidade, figurino, cenário, ordem dos eventos e duração; permitir à IA sugerir câmera, luz ou detalhamento apenas onde autorizado. Exibir as alterações e permitir aceitá-las por campo.

Exemplo: “Ana entra, diz ‘cheguei’ e senta.” O usuário fixa fala e sequência; a IA propõe enquadramento. Qualquer nova ação aparece como sugestão, sem substituir o plano aprovado.

Critério de aceite: o planejamento não altera campos bloqueados; incompatibilidades são explicadas antes do render. Isso controla o pedido, não garante aderência perfeita do modelo no vídeo final.

### 5. Reordenação de janelas exige revalidação temporal e narrativa — P1

O código local de `moveH3Window` (`useStore.ts:9221`) move objetos de janela e renumera índices, preservando seus demais campos, inclusive tempos/frames. A interface sinaliza que a continuidade ainda reflete a ordem original (`PromptInput.tsx:400`).

Proposta: distinguir “mover uma cena inteira” de “trocar o prompt de um intervalo”. Recalcular o que depende da operação: intervalos, estados de entrada/saída, transições e vínculos de áudio/referência. Invalidar aprovações dependentes e apresentar o impacto antes de regenerar.

Critério de aceite: uma troca de ordem não produz intervalos fora de sequência nem reutiliza continuidade antiga como se ainda estivesse validada. A geometria e a semântica precisam de verificações separadas.

### 6. Correção por cena existe; comparação e aprovação podem ficar mais claras — P1/P2

O dashboard já permite editar prompts e regenerar imagens/vídeos por cena. O backend já possui revisões Director; o Editor possui versões e histórico de intervenções de IA. Portanto, a proposta não é criar outro histórico paralelo.

Proposta: agrupar tomadas por cena, mostrar antes/depois e parâmetros alterados, escolher uma tomada aprovada, proteger essa seleção de regenerações em lote e enviar a escolha ao Editor. Preservar o resultado anterior enquanto uma nova tentativa é avaliada.

Critério de aceite: gerar uma alternativa não substitui a tomada aprovada; é possível compará-las e retornar à anterior com sua configuração.

## Fluxo de trabalho proposto

1. **Briefing:** objetivo, formato, duração, cenas obrigatórias, personagens, referências e restrições.
2. **Plano:** roteiro e cartões por cena, com duração, ação, fala, câmera, assets e liberdade permitida à IA. Aprovar individualmente ou em lote.
3. **Storyboard:** escolher imagens iniciais e keyframes onde o modelo os utilizar; gerar alternativas só das cenas selecionadas. Cenas sem imagem obrigatória continuam com referências e descrição visual.
4. **Revisão final:** conferir prompts efetivos e parâmetros já resolvidos; mostrar o que mudou desde a aprovação anterior e estimativa de tempo quando disponível.
5. **Fila:** executar cenas/revisões aprovadas. Planejamento ainda pendente aparece como tal e não concede autorização implícita para render.
6. **Tomadas:** comparar alternativas, marcar aprovada/revisar/descartada e regenerar seletivamente.
7. **Editor:** importar tomadas escolhidas, mantendo vínculo com cena e revisão de origem.

O dashboard existente é a base mais próxima para o espaço de planejamento; a sidebar pode manter os ajustes da cena selecionada. Evitar exigir que o usuário gerencie simultaneamente listas diferentes de cenas no Director, Studio e Editor.

## Sequência de implementação

| Ordem | Entrega | Impacto | Esforço relativo |
|---|---|---|---|
| 1 | Plano resolvido único + revisão congelada + validação no envio | Confiança no que será executado | Médio/alto |
| 2 | Aprovação persistente e fila que respeita o modo supervisionado | Controle mesmo com jobs longos e navegador fechado | Alto |
| 3 | Resumo completo por workflow, incluindo assets e prompts por janela | Detectar erros antes de consumir GPU | Médio |
| 4 | Bloqueios criativos e aprovação das sugestões da IA | Preservar intenção e narrativa | Médio/alto |
| 5 | Storyboard editável e revalidação das dependências | Controlar ritmo, continuidade e referências | Alto |
| 6 | Comparação de tomadas e regeneração seletiva integrada ao Editor | Reduzir retrabalho | Médio/alto |
| 7 | Presets criativos e testes curtos por cena | Acelerar iteração já controlada | Médio |

Esforços são relativos, sem estimativa de prazo. A ordem segue dependências: uma interface de aprovação precisa de um contrato confiável de execução para entregar o benefício prometido.

Um rascunho de imagem ou trecho curto pode ajudar a validar composição/estilo, mas não deve ser apresentado como previsão fiel do vídeo final, sobretudo se mudar modelo, resolução ou receita.

## Orientação técnica

- Evoluir o schema de planejamento e as revisões existentes; acrescentar identificadores estáveis de cena, revisão aprovada, dependências e configuração resolvida. Não confundir aprovação de prompt, imagem e tomada final.
- Centralizar a preparação do pedido usada por preview/revisão/envio. O store principal tem 13.821 linhas e já repete decisões entre revisão e geração; extrair esse trecho é uma refatoração diretamente ligada ao problema.
- Registrar parâmetros efetivos, seeds resolvidos, identificação de modelo/LoRA, assets e transformações de prompt. Seed fixo ajuda a comparar, mas não promete reprodução idêntica entre runtimes ou receitas diferentes.
- Fazer a aplicação impor bloqueios e aprovações; instruir o LLM a respeitá-los é apenas uma camada auxiliar.
- Persistir estados como rascunho, planejando, aguardando revisão, aprovado, na fila, gerando e concluído, com transições verificadas no servidor. Reutilizar os checkpoints atuais.
- Ao mudar uma referência compartilhada, listar cenas afetadas; revisitar apenas os artefatos dependentes. Escolhas já aprovadas devem continuar recuperáveis.

## Validação e limites

- `python3 -m unittest discover -s tests -p 'test_director_projects_queue.py'`: 9 testes passaram.
- `python3 -m unittest discover -s tests -p 'test_settings_roundtrip.py'`: 8 testes passaram; esta suíte verifica contratos por inspeção estática de código.
- `cd ui && ./node_modules/.bin/tsc -b --pretty false`: passou sem erros.
- Não encontrei testes dedicados ao novo painel/resumo de revisão na busca realizada. Os testes acima não provam sua integração ponta a ponta.
- Não foram executados modelos, benchmarks de GPU, testes de qualidade visual ou navegação interativa. As observações de interface decorrem do código React.
- As alterações locais existentes foram preservadas. Este levantamento adiciona documentação, sem implementar o roadmap.

Testes necessários ao implementar: revisão versus payload executado; planejamento adiado exigindo aprovação; reconexão em etapa pendente; invalidar aprovação após alteração; reordenar cenas com durações diferentes; preservar tomada aprovada ao gerar alternativa; revisão de imagem/áudio sem unidades de vídeo.

Métricas sugeridas: jobs cujo pedido divergiu do aprovado; alterações indevidas em campos bloqueados; renders descartados por erro de configuração; tempo e tentativas até aprovar uma cena. Não há medição inicial dessas métricas neste levantamento.

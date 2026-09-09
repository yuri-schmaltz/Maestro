# Controle de geração: implementação e gauntlet

Data: 09/09/2026. Referência: [análise inicial](ANALISE-CONTROLE-GERACAO-2026-09-09.md).

## Fluxo implementado

No Studio, a revisão fica habilitada por padrão. O servidor prepara e salva a solicitação antes da aprovação: prompts efetivos, janelas, seed resolvido, referências e parâmetros. O painel permite comparar o texto original, inspecionar os parâmetros e salvar uma nova revisão dos prompts. Gerar ou adicionar à fila envia o identificador da revisão salva; alterações posteriores no formulário não alteram esse pedido. Os arquivos de referência são verificados por hash na confirmação e novamente na execução. Uma revisão pronta pode ser recuperada após recarregar a página; planejamento interrompido por reinício do servidor aparece como falha recuperável.

No Director, o modo manual passou a ser o padrão e é respeitado também na fila. Há três aprovações: plano de cenas, storyboard e solicitação final de renderização. É possível editar prompts, bloquear campos, aprovar cada cena e regenerar uma imagem durante a revisão do storyboard. Editar uma cena invalida sua aprovação na interface. O último checkpoint apresenta os parâmetros compilados e congela o pedido que será executado.

Os checkpoints são persistidos. Esperar uma aprovação encerra o worker daquela etapa e permite que a fila processe outro projeto. A retomada preserva o plano e as aprovações; revisões desatualizadas são rejeitadas. Uma falha ao salvar a aprovação impede o despacho da geração.

As regenerações de cenas registram tomadas alternativas, com os prompts e referências associados. O painel permite comparar e escolher tomadas. Uma alternativa não substitui automaticamente uma tomada marcada como boa. Escolher uma imagem sinaliza que o vídeo precisa ser atualizado; timelines já importadas não são reescritas automaticamente.

Reordenar janelas preserva os intervalos de tempo e as referências vinculadas às posições. As pistas de continuidade são invalidadas e um aviso solicita revisão dos prompts.

## Ciclos de implementação e revisão

1. Separação entre preparação e execução; revisão persistida e submissão da cópia aprovada.
2. Aprovações do Director e liberação da fila durante espera humana; preservação de metadados, locks e digest da revisão.
3. Compilação antes da aprovação final, seed fixado e prevenção de uma nova expansão automática do prompt aprovado.
4. Histórico e seleção de tomadas, revisão das janelas e testes de interface em desktop e celular.
5. Correções encontradas na regressão: frontend ainda forçava modo automático na fila; restauração acrescentava defaults que alteravam o digest; falha de persistência podia deixar estado inconsistente; projetos aguardando retomada precisavam continuar sendo acompanhados; regeneração de imagem precisava restaurar o checkpoint salvo após reinício.

## Validação reproduzível

O runner está em `scripts/control_gauntlet.py`. Requer dependências do frontend instaladas e um Python com `starlette` e `requests`. Para o navegador, instalar também `playwright` e seu Chromium e iniciar o Vite:

```bash
cd ui
npm run dev -- --host 127.0.0.1 --port 5173
```

Em outro terminal, na raiz:

```bash
python scripts/control_gauntlet.py --browser http://127.0.0.1:5173
```

A bateria compreende 182 testes Python em oito suítes, verificações TypeScript de isolamento do snapshot e ordenação, build de produção e testes Playwright dos componentes reais com APIs simuladas. Os cenários incluem aprovação desatualizada, referência modificada, submissão repetida, falha de gravação, restauração, cancelamento, fila, três checkpoints completos e envio exato da revisão salva. ESLint também foi executado nos novos componentes e utilitários de revisão.

## Limites conhecidos

- A validação usa engines e APIs simuladas. Não houve geração real em GPU nem validação da qualidade audiovisual dos modelos.
- Avatar e video blend usam revisão de uma cópia congelada da configuração; a geometria final desses renderizadores ainda é calculada na execução e o painel informa essa diferença.
- Os bloqueios protegem campos de prompt; não são restrições semânticas por personagem, fala ou objeto. A solicitação final compilada exige sua própria aprovação.
- Rascunhos e marcações individuais de aprovação de cenas ficam na interface até confirmar a etapa. O checkpoint da etapa e o plano confirmado são persistidos.
- O histórico captura os parâmetros de cena disponíveis; não reconstrói todos os parâmetros de execuções antigas. Comparação de tomadas não recompõe automaticamente montagens existentes.
- Estimativas de geometria indicadas como aproximadas no painel não substituem metadados do arquivo final. O build mantém os avisos existentes sobre tamanho do bundle e importação do editor.
- Previews de baixo custo, presets criativos e bloqueios semânticos detalhados da análise inicial permanecem evoluções futuras; não fazem parte desta entrega.

As alterações preexistentes no workspace foram preservadas. Nenhum commit, publicação ou envio externo foi realizado.

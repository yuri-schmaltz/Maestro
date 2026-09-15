# Walkthrough: Plano 2 — Estabilidade de Hardware e Gerenciamento de Recursos

## Visão Geral das Entregas do Plano 2

O **Plano 2 (Estabilidade de Hardware)** foi implementado com sucesso para prevenir quedas por *CUDA Out of Memory* (OOM) em GPUs de 8GB a 12GB e impedir corrupção de arquivos em renderizações de vídeos longos por espaço de disco insuficiente.

---

## 1. Módulo de Otimização de Hardware e VRAM
- **Arquivo criado:** [`app/shared/utils/gpu_cleanup.py`](file:///c:/Users/u60897/Documents/cue/app/shared/utils/gpu_cleanup.py)
- **Funcionalidades:**
  - `force_cuda_cleanup()`: executa coleta agressiva de lixo (`gc.collect()`), esvazia os pools de memória alocados do PyTorch CUDA (`torch.cuda.empty_cache()`) e coleta memória entre processos (`torch.cuda.ipc_collect()`). Seguro para execução mesmo em ambientes sem CUDA/GPU.
  - `estimate_required_disk_gb(clip_count, resolution_preset, ...)`: fórmula preditiva realista que calcula o espaço em disco necessário baseado na resolução (720p vs 1080p+), multiplicador de duração e buffer de segurança de 5 GB.
  - `check_disk_space(target_dir, required_gb)`: validação atômica do ponto de montagem do diretório de saída do pipeline.

---

## 2. Integração nos Pontos Críticos do Pipeline (`app/services/director_pipeline.py`)
- **Preflight Preditivo de Disco:**
  - Substituição da checagem ingênua de 3 GB. O pipeline calcula dinamicamente a pegada esperada antes de ligar o LLM e aborta com mensagem informativa clara caso o disco não suporte o projeto completo.
- **Expurgo de VRAM nos Limites de Fase:**
  - Invocação preventiva de `force_cuda_cleanup()` na inicialização do pipeline.
  - Invocação de `force_cuda_cleanup()` imediatamente após o descarregamento do LLM (Fase 1 $\rightarrow$ Fase 2).
  - Invocação de `force_cuda_cleanup()` antes de carregar e alocar os modelos de difusão de vídeo (Fase 2 $\rightarrow$ Fase 3).
  - Invocação de `force_cuda_cleanup()` no cancelamento (`stop_pipeline`) para devolver a memória da GPU instantaneamente ao sistema.

---

## 3. Testes Automatizados Aprovados
- **Arquivo de teste:** [`tests/test_hardware_safety.py`](file:///c:/Users/u60897/Documents/cue/tests/test_hardware_safety.py)
- **Resultado:** 100% de sucesso (`12 passed` somando as suítes de segurança e hardware).
- Cobertura:
  1. Execução à prova de falhas de `force_cuda_cleanup()` com retorno de métricas.
  2. Escalabilidade proporcional da estimativa de disco por contagem de clipes e resolução.
  3. Verificação de espaço livre do disco no diretório ativo.
  4. Detecção assertiva de falta de espaço em limites excessivos.

---

## 4. Sincronização Remota
- Commit registrado e sincronizado no branch `main` do GitHub: `d1254fd` (*feat(hardware): implement VRAM cache purging and dynamic predictive disk preflight*).
- Working tree perfeitamente limpo.

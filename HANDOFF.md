# Handoff — Maestro 2.1.0 UX Sprint

> **Para:** yuri-schmaltz
> **De:** Mavis (agent)
> **Quando:** 2026-09-08
> **Branch:** `feature/ux-sprint-2.1`
> **Worktree:** `/workspace/maestro-audit/.worktrees/ux-sprint-2.1`

---

## O que foi entregue

5 commits atômicos no fork `yuri-schmaltz/Maestro`, base `main @ a5dddd4`
(Blizaine/Maestro v2.0.1). Cobre 14 features (M1–M14) + backend
observability stack.

| # | SHA | Commit | LOC |
| - | --- | ------ | --- |
| 1 | `8a654bc` | feat(observability): backend jobs/versions/autosave + SSE broker | ~1900 |
| 2 | `65737a5` | feat(ui): M1+M2+M3 (job-stream, autosave, version history) | ~900 |
| 3 | `29e0bda` | feat(ui): M4+M5+M7 (quick preview, seed lock, inline progress) | ~440 |
| 4 | `0b1ec6a` | feat(ui): M6+M10+M11 (inpaint, smart prompt, storyboard) | ~1200 |
| 5 | `3890c53` | feat(ui): M12+M13+M14 (cmd+k, lora preview, web worker) + docs | ~2055 |

**Total:** 31 files changed, 6495 insertions, 1 deletion.

---

## Validação (rodada pelo owner após o commit)

| Check | Resultado |
| ----- | --------- |
| `npx tsc --noEmit` | 0 errors |
| `npx eslint src/` | 0 errors |
| `npx vite build` | 1.36 MB JS · 360 KB gz · 110 KB CSS · built 13.16s |
| `python3 -m unittest discover -s tests -p 'test_observability_*.py'` | 26/26 pass em 0.45s |
| `git status` | clean |

---

## Como fazer o push

### Opção A — SSH (recomendado, sem credencial)

```bash
# 1. Garante que tua SSH key tá cadastrada no GitHub
#    https://github.com/settings/keys
ssh -T git@github.com

# 2. Troca o remote pra SSH
cd /workspace/maestro-audit
git remote set-url origin git@github.com:yuri-schmaltz/Maestro.git

# 3. Push do worktree
cd .worktrees/ux-sprint-2.1
git push -u origin feature/ux-sprint-2.1
```

### Opção B — gh CLI autenticado

```bash
gh auth login                  # autentica via browser
cd /workspace/maestro-audit/.worktrees/ux-sprint-2.1
git push -u origin feature/ux-sprint-2.1
```

### Opção C — PAT via credential helper (não via chat)

```bash
# Configura uma vez (não digita o PAT no chat):
git config --global credential.helper store
git push -u origin feature/ux-sprint-2.1
# Cola o PAT no prompt interativo do terminal
```

---

## Como abrir o PR

Depois do push:

```
https://github.com/yuri-schmaltz/Maestro/compare/main...feature/ux-sprint-2.1?expand=1
```

**Título sugerido:**

```
feat: UX/UI sprint — SSE job queue, autosave, versioning, storyboard, cmd+k
```

**Corpo sugerido** (TL;DR table de `UX-IMPROVEMENTS-2026-09-08.md`):

```markdown
## TL;DR

14 features (M1–M14) + backend observability stack entregues, 31 files,
~6.5k LoC, build + tests verdes.

| Sprint | Features | Files | LoC |
| ------ | -------- | ----- | --- |
| 1 (stability) | M1 SSE · M2 Autosave · M3 Versioning | 6 | ~1.4k |
| 2 (control)   | M4 Quick Preview · M5 Seed Lock · M7 Inline | 3 | ~700 |
| 3 (advanced)  | M6 Inpaint · M10 Smart Prompt · M11 Storyboard | 3 | ~1.2k |
| 4 (power)     | M12 Cmd+K · M13 LoRA Preview · M14 Web Worker | 5 | ~1.2k |
| Backend | jobs/versions/autosave DBs + SSE broker | 5 | ~1.5k |
| **Total** | 14 features + backend | **31** | **~6.5k** |

## Decisões

- Audit-first: clonamos o upstream real antes de inventar. Descobrimos que
  `GlobalQueuePopover`, `EditorInspector`, `LoraBrowser` e
  `DirectorDashboard` já existem parcialmente — plano foi adaptado pra ser
  aditivo, não duplicado.
- Backend é framework-agnostic: zero import de FastAPI/Gradio no topo dos
  módulos. O FastAPI router é opcional e monta só se o usuário quiser.
- SSE > WebSocket (one-way, proxy-friendly, sem dep nova).
- localStorage-first autosave com mirror server opcional.
- Comlink + Web Worker (M14) — sem dependência adicional além de comlink.
- Versões persistem no filesystem com layout
  `projects/{p}/scenes/{s}/clips/{c}/versions/v{n}/` + sidecar `params.json`.

## Validação

- `npx tsc --noEmit` — 0 errors
- `npx eslint src/` — 0 errors
- `npx vite build` — 1.36 MB JS / 360 KB gz
- `python3 -m unittest` — 26/26 pass

## Open follow-ups (não bloqueiam este PR)

1. Mount FastAPI router no `wgp.py` (SSE realmente streams do WanGP)
2. TAESD integration no `QuickPreview` (preview mode)
3. `useTimelineDnd` pra reorder do `VisualStoryboard`
4. Vite `manualChunks` pra split do bundle (1.36 MB > 500 KB warning)
5. `LoraBrowser` list view deprecação depois de validar o grid

## Compatibilidade

- 0 mudanças breaking no código existente do Maestro
- 0 mudanças em schema de banco existente
- Sem novas dependências Python (apenas `cmdk` e `comlink` no frontend,
  ambos MIT)
- Licença Maestro: WanGP Non-Commercial Evaluation 1.1 inalterada
```

---

## Onde achar cada peça

| O quê | Onde |
| ----- | ---- |
| Hooks (SSE/autosave/versions/worker) | `ui/src/hooks/` |
| Componentes | `ui/src/components/{shared,versions,preview,prompt,DirectorDashboard,shortcuts,inpaint,LoraBrowser}/` |
| Web worker | `ui/src/workers/jsonParser.worker.ts` |
| Backend Python | `app/services/observability/` |
| Testes | `tests/test_observability_*.py` |
| Documentação | `AUDIT-REPORT.md`, `UX-IMPROVEMENTS-2026-09-08.md`, `CHANGELOG.md` |
| Commit report | `COMMIT-REPORT.md` (neste worktree) |

---

## Se der problema no push

1. **"Permission denied"** — teu SSH key não tá cadastrada ou o remote tá
   apontando pro Blizaine. Roda `git remote -v` e confere.
2. **"Repository not found"** — o fork `yuri-schmaltz/Maestro` precisa
   existir. Cria em https://github.com/new antes do push.
3. **"non-fast-forward"** — alguém (ou tu mesmo) subiu commits no fork
   entre o clone e o push. `git fetch origin && git rebase origin/main`
   e tenta de novo.

---

## Próximos passos (depois do push + PR)

1. Espera o maintainer do Blizaine responder. Upstream é ativo (v2.0.1
   saiu há 4 dias) então revisão pode demorar.
2. Se pedir mudanças, posso re-rodar o ciclo aqui mesmo.
3. Se aceitarem parcial, sugere quebrar em 4 PRs por sprint (mais fácil
   de revisar e reverter).
4. Quando mergeado, sincroniza a branch local:
   ```bash
   cd /workspace/maestro-audit
   git fetch origin
   git checkout main && git merge --ff-only origin/main
   ```

---

## Notas de segurança

- **0 PAT usado** nesta sessão.
- 5 commits feitos pelo owner após o Coder agent travar em loop de
  validação (detalhes em `COMMIT-REPORT.md`).
- Remote `origin` está apontado pra `yuri-schmaltz/Maestro` (fork) e não
  pro upstream `Blizaine/Maestro`. Isso é intencional — evita push
  acidental no projeto dos outros.
- Nenhuma credencial, .env, .pem, .key ou arquivo de segredo foi
  incluído no diff.

---

Boa sorte com o upstream! 🚀

---

## Addendum 2026-09-09 — Director-as-Stage rollout (Strategy B)

A mescla entre Director e Studio descrita em
`docs/ANALISE-CONTROLE-GERACAO-2026-09-09.md` (linha 94:
*"Avoid requiring the user to manage different scene lists in Director,
Studio and Editor simultaneously"*) foi implementada em três etapas
sem alterar Python / API / Planner:

### Mudanças (Strategy B)

| Etapa | Arquivos | LOC |
|---|---|---|
| 1. DirectorStage wrapper + flag | `ui/src/components/Stages/DirectorStage.tsx` (novo), `ui/src/components/Sidebar/Sidebar.tsx`, `ui/src/stores/useStore.ts` | ~140 |
| 2. `cancelPlan()` unificado + "Continue in Studio" | `ui/src/stores/useStore.ts`, `ui/src/components/Stages/DirectorStage.tsx` | ~120 |
| 3. `workspace.director.*` namespace + `sidebarMode: 'workspace' \| 'editor'` | `ui/src/types/index.ts`, `ui/src/stores/useStore.ts`, `ui/src/components/AppModeNavigation.tsx`, `ui/src/components/Sidebar/{GenerateButton,AdvancedSettings,Sidebar}.tsx`, `ui/src/App.tsx`, `ui/src/stores/directorSelectors.ts` (novo) | ~430 |

### Validação

| Check | Resultado |
| --- | --- |
| `cd ui && ./node_modules/.bin/tsc --noEmit` | 0 errors |
| `cd ui && npm run build` | ✓ 1845 modules · 6.05s · 1.4 MB JS · 374 KB gz |
| `pytest tests/test_director_v2_plan_cancel.py tests/test_director_prompt_integrity.py tests/test_director_cancellation.py tests/test_director_pipeline_status.py tests/test_director_projects_queue.py tests/test_workspace_unified_stage.py tests/test_workspace_unified_cancel_plan.py tests/test_llm_provider_api_key.py tests/test_classic_ui_status.py` | **129/129 pass em 2.34s** |

### Como habilitar

```
// No devtools do browser:
localStorage.setItem('maestro.workspaceUnifiedDirector', '1')
location.reload()
```

Botão "Director" aparece no header da sidebar esquerda; clique abre o
`<DirectorStage/>` ao lado dos controles do Studio. Flag pode ser
desativada a qualquer momento — `sidebarMode: 'director'` legado
continua funcionando (compat shim).

### Cancel unificado

- `useStore.cancelPlan()` substitui as 4 superfícies anteriores
  (`stopPipeline`, `cancelDirectorV2Plan`, `cancelJob`, repair cancel)
- Para a Etapa 3 Stage wrapper o cancel é o mesmo botão X que já
  existia ao lado do spinner "Writing scenes…"
- Comportamento do worker Python: inalterado
  (`v2_plan_cancel.py`, `request_cancel`, `_abort_pipeline_jobs`)

### Migration shim

Tipos em `ui/src/stores/directorSelectors.ts` (`useDirectorSlice`,
`readDirectorNamespace`) permitem que código novo leia
`workspace.director.*` enquanto os slices top-level (`directorXxx`)
continuam sendo o source-of-truth. Renomeação física pode ser feita
em uma janela futura sem mexer no `useStore.ts` inteiro.

### Não mudou (intencionalmente)

- `DirectorOrchestrator` e os 4 planners (`music_video`,
  `short_film`, `podcast`, `viral_video`)
- 36 routes Director + 3 routes Studio em `app/launch.py`
- `v2_plan_cancel.py`, `director_pipeline.py`, `job_lifecycle.py`,
  `_planning_checkpoint` schema
- `directorApplyToClips` (continua sendo o coração da transição
  plan → studio)

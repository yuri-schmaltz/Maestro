# Handoff — Maestro fork standalone (2026-09-10)

> **Para:** próximo mantenedor do fork
> **De:** agente GitHub Copilot (sessão 2026-09-09/10)
> **Estado:** working tree em `main` @ `ac399a5`, 3 commits à frente de `origin/main`

---

## Resumo do fork

Fork local do Maestro (base `Blizaine/Maestro v2.0.1`) consolidado como **distribuição standalone**, sem dependência do launcher Pinokio. Tudo o que era Pinokio (instaladores, manifest, scripts de update, scripts de Start/Sol/Classic/Tailscale/SAM/Reset) foi removido; substituído por dois scripts Bash na raiz + instalação manual do venv Python.

### Como rodar

```bash
# 1. venv Python (uma vez — equivalent of pinokio install)
cd app && python3 -m venv env
env/bin/pip install --upgrade pip
env/bin/pip install torch==2.7.1 torchvision==0.22.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128
env/bin/pip install -r requirements.txt
touch env/.maestro_torch_v1.installed env/.maestro_flash_disabled_v2.installed

# 2. UI (uma vez — equivalent of pinokio update rebuilding ui)
cd ../ui && npm install && npm run build && cd ..

# 3. Sobe o backend (start automática UI build se ui/dist/ faltar)
./start_local.sh                  # loopback, porta 7860
./start_local.sh --port 7900      # porta custom
./start_local.sh --share          # 0.0.0.0 (LAN)
./start_local.sh --compile        # passa --compile para launch.py

./stop_local.sh                   # SIGTERM gracioso
```

`start_local.sh` é quem cuida de:
- Detectar venv disponível (`env-sol` → `env-rtx50` → `env` legacy)
- Mostrar GPU/driver via `nvidia-smi`
- Auto-build UI se `ui/dist/` ausente
- Limpar instância anterior (pidfile + holder da porta)
- Subir backend em background com log em `app/.launcher.log`
- Aguardar o bind (curl em loop de 1s, timeout 120s)

---

## Commits entregues nesta sessão (3)

### `ac399a5` — feat(ui): default Director-as-Stage to discoverable
**Problema:** a skill chooser (Music Video / Short Film) ficou invisível para quem abria o app fresco, porque o flag `workspaceUnifiedDirector` carregava `false` por default e `workspaceStage` carregava `'studio'`.

**Mudanças em `ui/src/stores/useStore.ts`:**
- `workspaceUnifiedDirector` agora default `true`; lê `'0'` explícito do localStorage como opt-out (null/undefined = opt-in)
- `workspaceStage` agora default `'director'` (era `'studio'`)

**Resultado:** primeiro launch abre o `<DirectorStage>` automaticamente com os 4 cards de skill visíveis (Music Video, Short Film, Video Podcast [coming soon], Viral Video [coming soon]). Fechar o Stage via botão "Close Director stage" da header; voltar via botão "Studio" no mesmo lugar.

**Migração:** usuários existentes que tinham `'1'` em localStorage não veem mudança (já estavam opt-in). Quem tinha o app aberto antes vai ver Stage abrir ao recarregar — esse é o novo discoverability.

### `d3f59b6` — Refactor README and documentation for launcher integration
**Escopo (já commitado por você antes):** restaurou `CONTRIBUTING.md`, `THIRD_PARTY_NOTICES.md`, `docs/RELEASE_NOTES_V2.0.md`, `docs/RELEASE_NOTES_V2.0.1.md`, `docs/TAILSCALE_REMOTE_ACCESS.md` do HEAD anterior, com limpeza de todas as referências a Pinokio (mantido `PINOKIO_SHARE_LOCAL` como nome técnico de env var que o `launch.py` ainda lê). Também confirmou deleção de 3 docs pessoais (`docs/ANALISE-*`, `IMPLEMENTACAO-*`, `MONITORAMENTO-*`) e de `scripts/control_gauntlet.py` (runner pessoal).

**O que mudou nos docs:**
- `CONTRIBUTING.md` reescrito para fluxo standalone (`python3 -m venv env && pip install -r requirements.txt`)
- `TAILSCALE_REMOTE_ACCESS.md` reescrito (passos não dependem mais do menu Pinokio)
- `RELEASE_NOTES_V2.0.md` + `v2.0.1.md`: seção Updating reescrita ("Run your normal update flow" em vez de "Use Update from Maestro's Pinokio page")
- Bulk substituições via sed em `README.md` (19 ocorrências) e `CHANGELOG.md` (4 ocorrências) preservando o histórico

### `d798e60` — feat: Implement gauntlet control and monitoring features
**Escopo (já commitado antes):** feature nova do fork com suite de "gauntlet control", monitoramento local, e logs LLM. Está no commit antes do cleanup e antes do HEAD atual, então ainda referenced em `docs/release_todo.md` (gitignored).

---

## Arquivos chave do fork

### Launchers (raiz)

| Arquivo | Função |
|---|---|
| `start_local.sh` | Sobe o backend, detecta venv, valida GPU, auto-build UI, aguarda bind |
| `stop_local.sh` | Para o backend via SIGTERM/SIGKILL grace |

### Backend (app/)

| Arquivo | Função |
|---|---|
| `app/launch.py` | Entry point FastAPI/Uvicorn (28.5K linhas) |
| `app/wgp.py` | Backend WanGP upstream (20K linhas) |
| `app/env/bin/python` | venv Python 3.12 com torch+CUDA 12.8 |
| `app/.launcher.{pid,log}` | Controle do `start_local.sh` |

### Frontend (ui/)

| Arquivo | Função |
|---|---|
| `ui/src/stores/useStore.ts` | Zustand store; mudou default de `workspaceUnifiedDirector`/`workspaceStage` |
| `ui/src/components/Stages/DirectorStage.tsx` | Renderiza o skill chooser |
| `ui/src/components/Sidebar/Sidebar.tsx` | Header com botão Director (linhas 321+) |
| `ui/src/components/MainContent/MainContent.tsx` | Header de mídias alinhado a `h-14` (próxima seção) |
| `ui/dist/assets/index-*.js` | Bundle Vite (1.4 MB) |

### Mudança de UI restante (não commitada)

Sessão atual ainda tem uma mudança em `ui/src/components/MainContent/MainContent.tsx` linha 891:

```diff
- <div className="px-2 md:px-6 py-2 md:py-3 border-b border-border flex items-center justify-between gap-2">
+ <div className="flex h-14 items-center justify-between gap-2 border-b border-border px-4">
```

**Por quê:** header de mídias (TabFilter + WorkspaceSelector) estava com altura responsiva (`py-2 md:py-3` = 40-44px) enquanto o header Maestro tem `h-14` (56px fixo). Os borders-bottom ficavam em eixos Y diferentes — visivelmente desalinhado.

**Fix:** ambos passam a usar `h-14` + `px-4` + `items-center` + `border-b` idênticos. TabFilter interno (`py-1`) fica centrado pelos 56px do container sem precisar ajustar.

**Status:** modificação em working tree, ainda não commitada. Rebuild UI feito (`npm run build` 5.64s, 1.41 MB JS).

---

## Tasks em aberto

1. **Commit do header alignment** — diff pronto em `ui/src/components/MainContent/MainContent.tsx`. Mensagem sugerida:
   ```
   fix(ui): align media gallery header with maestro header
   
   Both top bars now use h-14 + px-4 + border-b + items-center so the
   divider lines land on the same Y axis. The TabFilter's internal
   py-1 stays centred within the 56px container.
   ```

2. **CHANGELOG.md desatualizado** — a entrada `[Unreleased] / Director-as-Stage` ainda diz *"flag defaults to off"* (escrita antes do commit `ac399a5`). Vale atualizar para refletir o novo default `true` e o `workspaceStage: 'director'`.

3. **Backend ainda OK** — `app/env/` (9.2 GB), `app/ckpts/` (30 GB), `ui/dist/` todos intactos. `./start_local.sh` rodando em PID atual, basta `tail -f app/.launcher.log` para acompanhar.

4. **Smoke tests da pasta `tests/`** — foram **inteiramente removidos** no commit `2f96b76`. Se quiser reintroduzir, dá pra `git checkout 5f50095 -- tests/` para restaurar tudo de uma vez.

5. **Tailscale daemon-side** — o backend tem `services/remote_access.py` funcional, mas o glue entre ele e o `<DirectorStage>` UI é frágil. Toda a parte `tailscale_setup.js` Pinokio foi removida. Persistência fica em `app/settings/remote_access.json` quando o usuário ativa via Settings → Notifications → Private phone access.

---

## Verificações que rodei

- `start_local.sh` smoke test: bind em 17s, 3 endpoints HTTP 200 (`/`, `/classic/`, `/docs`)
- `stop_local.sh`: SIGTERM gracioso, libera porta
- GPU: NVIDIA GeForce RTX 3060 (SM 86), driver 595, CUDA 12.8 (via torch 2.7.1+cu128)
- 199 modelos disponíveis via `Maestro WanGP loaded`
- Build UI: tsc-via-vite em ~5-6s, 1.41 MB JS, 108 KB CSS, 0 type errors
- Python imports: `torch`, `mmgp 3.7.12`, `diffusers 0.36.0`, `transformers 4.57.1`, `fastapi 0.141.1`, `gradio 5.29.0` — todos OK

---

## Como retomar

Tudo já está commitado localmente em `main` (3 commits à frente de `origin/main`). Para publicar:

```bash
git push origin main
```

Para voltar ao skill chooser se ele sumir por alguma razão:

```bash
# console do browser (DevTools)
localStorage.setItem('maestro.workspaceUnifiedDirector', '1')
location.reload()
```

Para parar de ver o Director Stage e usar só o modo Studio:

```bash
# console do browser (DevTools)
localStorage.setItem('maestro.workspaceUnifiedDirector', '0')
location.reload()
```

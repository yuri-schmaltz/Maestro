# Walkthrough: Plano 1 — Segurança e Controle de Acesso Implementado

## Visão Geral das Modificações Realizadas

O **Plano 1 (Segurança e Controle de Acesso)** foi concluído com sucesso, cobrindo o endurecimento da API contra acessos remotos não autorizados (ao usar `--share`), proteção rigorosa contra *Path Traversal* e injeção automática de tokens no cliente web.

---

## 1. Módulo de Autenticação por Token
- **Arquivo criado:** [`app/services/security.py`](file:///c:/Users/u60897/Documents/cue/app/services/security.py)
- **Funcionalidades:**
  - `configure_security(api_key, require_auth, allow_unauthenticated_local)`: gerencia a chave ativa da API. Caso `--share` seja ativado ou `--require-auth` seja passado sem token explícito, gera automaticamente uma chave criptograficamente segura via `secrets.token_urlsafe(32)`.
  - `verify_api_key(request)`: valida o Bearer token nos cabeçalhos HTTP (`Authorization: Bearer <token>`) e em query params (`?api_key=...` para WebSockets).
  - Rotas locais (`127.0.0.1` / `localhost`) sem o modo `--share` permanecem desimpedidas por padrão para manter a simplicidade do desenvolvedor local.

---

## 2. Prevenção contra Path Traversal
- **Arquivo criado:** [`app/shared/utils/path_safety.py`](file:///c:/Users/u60897/Documents/cue/app/shared/utils/path_safety.py)
- **Funcionalidades:**
  - `is_safe_subpath(path, base)` e `resolve_safe_path(user_path, allowed_roots)`: garantem que qualquer arquivo de mídia, áudio ou projeto seja resolvido estritamente dentro dos diretórios autorizados do workspace, com suporte multiplataforma (tratando letras de unidade de disco no Windows).
  - Atualização de `_safe_join` em `app/launch.py` para usar a nova validação canônica de segurança.

---

## 3. Integração no Servidor (`app/launch.py`)
- **Flags de CLI adicionadas:**
  - `--api-key <token>`: define um token estático para a sessão.
  - `--require-auth`: força autenticação mesmo para requisições em loopback local.
  - `--share`: ativa o bind em `0.0.0.0` e automaticamente ativa a obrigatoriedade do Bearer token.
- **Middleware HTTP:**
  - Intercepta todas as requisições antes de chegarem aos endpoints, devolvendo HTTP 401 estruturado caso o token não seja fornecido ou seja inválido.
- **Banner de Inicialização:**
  - Exibe o status da segurança e imprime o token ativo quando o modo protegido é acionado.

---

## 4. Interceptor no Frontend (`ui/src/api/client.ts`)
- Injeção transparente de token: intercepta as chamadas `fetch` nativas da aplicação, anexando o cabeçalho `Authorization: Bearer <token>` a partir do `localStorage` (`cue_api_key`).
- Exportação dos helpers `getApiKey()` e `setApiKey()` para integração com telas de configuração.

---

## 5. Validação Automatizada
- **Arquivo de testes:** [`tests/test_api_security.py`](file:///c:/Users/u60897/Documents/cue/tests/test_api_security.py)
- **Resultados da execução (`pytest`):**
  - `8 passed in 0.60s`
  - Cobertura de cenários:
    1. Requisições permitidas com auth desativado.
    2. Bloqueio com HTTP 401 para clientes externos sem token.
    3. Aceite imediato com Bearer token válido.
    4. Permissão de loopback local no modo default.
    5. Bloqueio de loopback quando `--require-auth` estiver em modo estrito.
    6. Detecção e bloqueio de tentativas de Path Traversal (`..`).

---

## 6. Sincronização com o Repositório Remoto
- Commit registrado local e remotamente no branch `main`: `3550617` (*feat(security): implement Bearer token auth, path traversal protection, and client interceptor*).
- Árvore de trabalho limpa (`working tree clean`).

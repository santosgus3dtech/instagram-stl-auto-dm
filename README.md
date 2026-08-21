# Instagram STL Auto DM

Automacao oficial para enviar uma mensagem privada no Instagram quando alguem
comentar uma palavra-chave, como `STL`, em um post configurado.

O projeto usa Python, FastAPI, Webhooks da Meta, SQLite e Private Replies da API
oficial. A proposta e evitar automacao de interface, scraping ou Selenium.

## Estado atual

MVP iniciado com:

- endpoint `GET /webhook` para verificacao da Meta;
- endpoint `POST /webhook` para receber eventos de comentarios;
- validacao de assinatura `X-Hub-Signature-256`;
- filtro por `media_id` e palavra-chave;
- envio de Private Reply via endpoint de mensagens configuravel;
- idempotencia com SQLite para nao responder o mesmo comentario duas vezes;
- testes com payloads falsos, sem chamar a API real.

## Estrutura

```text
app/
  main.py
  config.py
  database.py
  security.py
  routes/
    webhook.py
  services/
    automations.py
    instagram.py
data/
tests/
.env.example
requirements.txt
run.py
```

## Instalar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

No Linux/Raspberry Pi:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configurar

Crie um `.env` baseado em `.env.example`.

```env
VERIFY_TOKEN=um_token_que_voce_inventar
META_APP_SECRET=seu_app_secret_da_meta
IG_ACCESS_TOKEN=seu_access_token
IG_USER_ID=seu_instagram_user_id
TARGET_MEDIA_ID=id_do_post
STL_KEYWORD=STL
STL_LINK=https://example.com/download/modelo.stl
GRAPH_VERSION=v26.0
```

Para varias automacoes, use `AUTOMATIONS_JSON`:

```env
AUTOMATIONS_JSON=[{"media_id":"180...","keyword":"STL","link":"https://example.com/modelo.stl"}]
```

## Rodar localmente

```bash
python run.py
```

Ou:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

URL local:

```text
http://localhost:8000
```

Para a Meta chamar seu webhook em desenvolvimento, exponha a porta com uma URL
HTTPS, por exemplo com ngrok ou Cloudflare Tunnel:

```text
https://seu-dominio-ou-tunnel/webhook
```

## Testar

```bash
pytest
```

## Fontes oficiais a acompanhar

Confirmado em 2026-08-16 nas documentacoes oficiais da Meta:

- [Private Replies para Instagram](https://developers.facebook.com/documentation/instagram-platform/private-replies)
- [Private Replies em Instagram Messaging](https://developers.facebook.com/documentation/business-messaging/instagram-messaging/features/private-replies)
- [Webhooks da Graph API](https://developers.facebook.com/docs/graph-api/webhooks/getting-started/)
- [Webhooks para Instagram](https://developers.facebook.com/docs/graph-api/webhooks/getting-started/webhooks-for-instagram/)
- [Permissions Reference](https://developers.facebook.com/docs/permissions/)

Antes de colocar em producao, revise no painel da Meta quais permissoes e
recursos precisam de App Review/Advanced Access para a conta e o tipo de login
escolhidos.

## Proximo passo

1. Criar/configurar o app no Meta for Developers.
2. Conectar uma conta Instagram Professional.
3. Obter `IG_USER_ID`, `IG_ACCESS_TOKEN`, `APP_SECRET` e o `TARGET_MEDIA_ID`.
4. Subir o backend com HTTPS publico.
5. Registrar o webhook no painel da Meta e assinar eventos de comentarios.
6. Fazer um teste real comentando `STL` no post configurado.

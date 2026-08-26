# Instagram STL Auto DM

Automacao oficial para enviar uma mensagem privada no Instagram quando alguem
comentar uma palavra-chave, como `STL`, em um post configurado.

O projeto usa Python, FastAPI, Webhooks da Meta, SQLite e Private Replies da API
oficial. A proposta e evitar automacao de interface, scraping ou Selenium.
Quando a Meta nao entrega webhooks em tempo real por causa de revisao/acesso, o
backend tambem pode consultar comentarios periodicamente como fallback.

## Estado atual

MVP iniciado com:

- endpoint `GET /webhook` para verificacao da Meta;
- endpoint `POST /webhook` para receber eventos de comentarios;
- validacao de assinatura `X-Hub-Signature-256`;
- filtro por `media_id` e palavra-chave;
- envio de Private Reply via endpoint de mensagens configuravel;
- idempotencia com SQLite para nao responder o mesmo comentario duas vezes;
- fallback opcional por polling de comentarios;
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

Se os webhooks da Meta nao chegarem, habilite o polling:

```env
COMMENT_POLLING_ENABLED=true
COMMENT_POLLING_INTERVAL_SECONDS=30
COMMENT_POLLING_LIMIT=25
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

## Rodar no Raspberry Pi

O Raspberry deve manter o backend ligado 24h. Use um servico `systemd` para
iniciar junto com o sistema e reiniciar se cair.

1. Copie ou clone este projeto no Raspberry:

```bash
sudo mkdir -p /opt/instagram-stl-auto-dm
sudo chown -R pi:pi /opt/instagram-stl-auto-dm
git clone <url-do-seu-repositorio> /opt/instagram-stl-auto-dm
```

Se voce ainda nao subiu para um repositorio remoto, copie a pasta por SSH/SCP
e mantenha o `.env` fora do Git.

2. Rode o setup:

```bash
cd /opt/instagram-stl-auto-dm
chmod +x deploy/raspberry-setup.sh
sudo ./deploy/raspberry-setup.sh
```

3. Edite o `.env` no Raspberry com os valores reais:

```bash
nano /opt/instagram-stl-auto-dm/.env
```

4. Inicie/reinicie o servico:

```bash
sudo systemctl restart instagram-stl-auto-dm
sudo systemctl status instagram-stl-auto-dm --no-pager
```

5. Teste no proprio Raspberry:

```bash
curl http://127.0.0.1:8000/health
```

6. Crie uma URL HTTPS publica apontando para `127.0.0.1:8000` e use no painel
da Meta:

```text
https://sua-url-publica/webhook
```

Para uso real, prefira uma URL fixa. Cloudflare Tunnel com dominio proprio,
ngrok com dominio reservado, Nginx com HTTPS ou uma VPS evitam trocar a URL de
callback toda vez que o tunel reiniciar.

Para um teste rapido sem dominio proprio, instale `cloudflared` e rode um
quick tunnel apontando para o servico local:

```bash
sudo systemctl status instagram-stl-auto-dm-tunnel --no-pager
journalctl -u instagram-stl-auto-dm-tunnel --no-pager -n 120 | grep -Eo 'https://[-a-zA-Z0-9.]+\.trycloudflare\.com' | tail -n 1
```

Use a URL retornada com `/webhook` no painel da Meta. Esse tipo de tunel e bom
para teste, mas a URL pode mudar quando o servico reinicia.

## Painel de status

O projeto tambem inclui um painel separado para monitorar o Raspberry e os
servicos da automacao. Ele roda na porta `8080` e mostra:

- se o Raspberry esta online;
- uptime, memoria, disco e temperatura;
- se `instagram-stl-auto-dm` esta ativo;
- se o tunnel publico esta ativo;
- URL publica atual do webhook, quando encontrada nos logs;
- console com logs do `systemd`;
- botao para reiniciar o backend e o tunnel.

No Raspberry:

```bash
sudo cp /opt/instagram-stl-auto-dm/deploy/raspberry-status.service /etc/systemd/system/raspberry-status.service
sudo systemctl daemon-reload
sudo systemctl enable raspberry-status
sudo systemctl restart raspberry-status
```

Abra na rede local:

```text
http://192.168.0.105:8080
```

JSON direto:

```text
http://192.168.0.105:8080/api/status
```

Logs:

```text
http://192.168.0.105:8080/api/logs/instagram-stl-auto-dm
http://192.168.0.105:8080/api/logs/instagram-stl-auto-dm-tunnel
```

Os botoes de restart do painel chamam estes endpoints:

```text
POST /api/services/instagram-stl-auto-dm/restart
POST /api/services/instagram-stl-auto-dm-tunnel/restart
```

Reiniciar `instagram-stl-auto-dm` mantem o tunnel ativo. Reiniciar
`instagram-stl-auto-dm-tunnel` pode gerar uma nova URL `trycloudflare.com`, que
tambem precisa ser atualizada no painel da Meta.

## Auditoria de seguidores do Instagram pessoal

O painel tambem tem uma area `Instagram pessoal` para comparar a lista oficial
de seguidores/seguindo exportada pela Central de Contas da Meta.

O fluxo seguro e:

1. Abra `https://accountscenter.instagram.com/info_and_permissions/dyi/`.
2. Exporte `Seguidores e seguindo` em formato `JSON`.
3. Baixe o ZIP gerado pela Meta.
4. No painel `http://192.168.0.105:8080`, envie o ZIP em `Instagram pessoal`.

O Raspberry extrai o ZIP, salva um historico local e mostra:

- quem voce segue e nao segue de volta;
- quem te segue e voce nao segue;
- novos seguidores desde a ultima importacao;
- quem deixou de te seguir desde a ultima importacao.

Tambem e possivel copiar ZIPs para `data/follow_audit/inbox`; o painel importa
automaticamente o arquivo ZIP mais recente dessa pasta.

Por padrao, este projeto nao usa Selenium para entrar no Instagram pessoal,
armazenar senha ou raspar telas. A parte principal automatizada comeca no ZIP
oficial gerado pela Central de Contas.

### Assistente Selenium opcional

Existe tambem um assistente Selenium em `tools/accounts_center_export.py` para
solicitar a exportacao pela Central de Contas usando um perfil persistente do
Chromium no Raspberry. Ele e conservador:

- nao salva cookies em JSON nem imprime sessao no log;
- usa o proprio perfil local do Chromium em `data/selenium/...`;
- antes de abrir a Central de Contas, valida a sessao em uma pagina comum do
  Instagram;
- para se encontrar login, 2FA, checkpoint ou verificacao de seguranca;
- salva status em `data/follow_audit/selenium_status.json`;
- baixa/importa ZIPs apenas pela pasta `data/follow_audit/inbox`.

Rodar apenas para checar se a sessao esta carregada:

```bash
.venv/bin/python tools/accounts_center_export.py --mode check-session --headless
```

Esse modo nao entra na Central de Contas; ele so confirma se o perfil persistente
do navegador ja esta autenticado no Instagram.

Solicitar a exportacao:

```bash
.venv/bin/python tools/accounts_center_export.py --mode request-export --headless
```

Timer diario opcional:

```bash
sudo cp /opt/instagram-stl-auto-dm/deploy/instagram-follow-export.service /etc/systemd/system/
sudo cp /opt/instagram-stl-auto-dm/deploy/instagram-follow-export.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now instagram-follow-export.timer
```

Se a Meta pedir login/verificacao, faca a acao manualmente numa sessao visivel e
rode de novo. O script nao tenta contornar validacoes.

## Reinicio automatico

Para reduzir risco de travamento ao longo dos dias, ha um timer opcional que
reinicia apenas o backend `instagram-stl-auto-dm` diariamente de madrugada. Ele
nao reinicia o Raspberry inteiro e nao reinicia o tunnel, entao a URL publica
continua a mesma.

Instalar/ativar no Raspberry:

```bash
sudo cp /opt/instagram-stl-auto-dm/deploy/instagram-stl-auto-dm-restart.service /etc/systemd/system/
sudo cp /opt/instagram-stl-auto-dm/deploy/instagram-stl-auto-dm-restart.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now instagram-stl-auto-dm-restart.timer
systemctl list-timers instagram-stl-auto-dm-restart.timer
```

Por padrao ele roda todos os dias as `04:10`, com ate 10 minutos de atraso
aleatorio.

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

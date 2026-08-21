import os
import hmac
import hashlib
import sqlite3

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse

load_dotenv()

app = FastAPI()

# --------------------------------------------------
# CONFIGURAÇÕES
# --------------------------------------------------

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
APP_SECRET = os.getenv("META_APP_SECRET")

IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
IG_USER_ID = os.getenv("IG_USER_ID")

# ID do post específico no qual queremos detectar "STL"
TARGET_MEDIA_ID = os.getenv("TARGET_MEDIA_ID")

# Link que será enviado
STL_LINK = os.getenv(
    "STL_LINK",
    "https://seusite.com/arquivo.stl"
)

# A versão fica configurável para facilitar futuras atualizações
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v26.0")

GRAPH_URL = (
    f"https://graph.instagram.com/"
    f"{GRAPH_VERSION}/{IG_USER_ID}/messages"
)

DATABASE = "instagram_bot.db"


# --------------------------------------------------
# BANCO DE DADOS
# evita responder duas vezes ao mesmo comentário
# --------------------------------------------------

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_comments (
                comment_id TEXT PRIMARY KEY
            )
        """)


def claim_comment(comment_id):
    """
    Tenta reservar o comentário.

    Retorna:
        True  -> ainda não havia sido processado
        False -> já foi processado
    """

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO processed_comments(comment_id)
            VALUES (?)
            """,
            (str(comment_id),)
        )

        return cursor.rowcount == 1


def release_comment(comment_id):
    """
    Se o envio falhar, remove do banco
    para permitir nova tentativa.
    """

    with sqlite3.connect(DATABASE) as conn:
        conn.execute(
            """
            DELETE FROM processed_comments
            WHERE comment_id = ?
            """,
            (str(comment_id),)
        )


init_db()


# --------------------------------------------------
# SEGURANÇA DO WEBHOOK
# --------------------------------------------------

def verify_signature(raw_body: bytes, signature: str | None):
    """
    Valida a assinatura enviada pela Meta.
    """

    if not APP_SECRET:
        return True

    if not signature:
        return False

    expected = (
        "sha256="
        + hmac.new(
            APP_SECRET.encode(),
            raw_body,
            hashlib.sha256
        ).hexdigest()
    )

    return hmac.compare_digest(expected, signature)


# --------------------------------------------------
# ENVIA PRIVATE REPLY
# --------------------------------------------------

def send_private_reply(comment_id: str):
    message = (
        "Oi! 👋\n\n"
        "Vi que você comentou STL 😊\n\n"
        "Aqui está o link:\n"
        f"{STL_LINK}\n\n"
        "Qualquer dúvida é só me chamar!"
    )

    payload = {
        "recipient": {
            "comment_id": str(comment_id)
        },
        "message": {
            "text": message
        }
    }

    headers = {
        "Authorization": f"Bearer {IG_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        GRAPH_URL,
        headers=headers,
        json=payload,
        timeout=20
    )

    if not response.ok:
        raise Exception(
            f"Erro Instagram API: "
            f"{response.status_code} - {response.text}"
        )

    return response.json()


# --------------------------------------------------
# VERIFICAÇÃO INICIAL DO WEBHOOK
# --------------------------------------------------

@app.get("/webhook")
async def verify_webhook(request: Request):

    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook verificado.")
        return PlainTextResponse(challenge)

    raise HTTPException(
        status_code=403,
        detail="Token de verificação inválido"
    )


# --------------------------------------------------
# RECEBE EVENTOS DO INSTAGRAM
# --------------------------------------------------

@app.post("/webhook")
async def instagram_webhook(request: Request):

    raw_body = await request.body()

    signature = request.headers.get(
        "x-hub-signature-256"
    )

    if not verify_signature(raw_body, signature):
        raise HTTPException(
            status_code=403,
            detail="Assinatura inválida"
        )

    data = await request.json()

    print("\n===== WEBHOOK =====")
    print(data)
    print("===================\n")

    for entry in data.get("entry", []):

        for change in entry.get("changes", []):

            # Só queremos eventos de comentários
            if change.get("field") != "comments":
                continue

            value = change.get("value", {})

            comment_id = value.get("id")
            comment_text = value.get("text", "")

            media = value.get("media", {})
            media_id = media.get("id")

            username = (
                value.get("from", {})
                .get("username", "desconhecido")
            )

            print(
                f"Comentário recebido:\n"
                f"Usuário: @{username}\n"
                f"Texto: {comment_text}\n"
                f"Post: {media_id}\n"
                f"Comment ID: {comment_id}"
            )

            # -----------------------------------------
            # FILTRA POST
            # -----------------------------------------

            if str(media_id) != str(TARGET_MEDIA_ID):
                print("Ignorado: outro post.")
                continue

            # -----------------------------------------
            # FILTRA PALAVRA
            # -----------------------------------------

            if comment_text.strip().casefold() != "stl":
                print("Ignorado: não é STL.")
                continue

            if not comment_id:
                continue

            # -----------------------------------------
            # EVITA DUPLICIDADE
            # -----------------------------------------

            if not claim_comment(comment_id):
                print(
                    f"Comentário {comment_id} "
                    "já foi processado."
                )
                continue

            # -----------------------------------------
            # ENVIA O DIRECT
            # -----------------------------------------

            try:

                result = send_private_reply(
                    comment_id
                )

                print(
                    f"✅ Direct enviado para "
                    f"@{username}"
                )

                print(result)

            except Exception as error:

                # Permite tentar novamente
                release_comment(comment_id)

                print(
                    f"❌ Erro enviando Direct: "
                    f"{error}"
                )

    # Meta precisa receber HTTP 200 rapidamente
    return {"status": "ok"}
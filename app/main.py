import asyncio
import os
import secrets
import sqlite3
import subprocess
import tempfile
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.getenv("CODEX_WORKSPACE", "/home/egemen/homelab")).resolve()
DB_PATH = Path(os.getenv("BOT_DB", str(Path(__file__).parent.parent / "data/bot.sqlite3")))
CODEX_BIN = os.getenv("CODEX_BIN", "codex")


def db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pending_writes (
                sender TEXT PRIMARY KEY,
                token TEXT NOT NULL,
                task TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def run_codex(task: str, sandbox: str) -> str:
    prompt = f"""Sen, Linux homelab yöneticisine yardım eden Codex aracısısın.
Çalışma alanın: {ROOT}
Docker path eşlemesi: host `/home/egemen` = container `/home/egemen`.
Kullanıcı host yolunu (`/home/egemen/...`) söylerse aynı container yolunu kullan.
Kullanıcı isteği: {task}

Kurallar:
- Sadece çalışma alanı içindeki dosya ve servislerle ilgilen.
- Secret, token, parola ve özel anahtarların içeriğini cevaba koyma.
- {sandbox} sandbox politikasına uy.
- İşlem yaptıysan ne yaptığını ve sonucu kısa, Türkçe özetle.
- İstek belirsizse değişiklik yapmak yerine soru sor.
"""
    with tempfile.NamedTemporaryFile(prefix="codex-answer-", suffix=".txt", delete=False) as answer:
        answer_path = Path(answer.name)
    try:
        command = [CODEX_BIN, "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox", sandbox,
                   "--cd", str(ROOT), "--output-last-message", str(answer_path), "-"]
        completed = subprocess.run(command, input=prompt, text=True, capture_output=True,
                                   cwd=ROOT, timeout=int(os.getenv("CODEX_TIMEOUT_SECONDS", "300")), check=False)
        result = answer_path.read_text(encoding="utf-8", errors="replace").strip()
        if not result:
            result = completed.stderr.strip() or completed.stdout.strip()
        if completed.returncode != 0:
            return f"Codex hata verdi (exit {completed.returncode}):\n{result[-3500:]}"
        return result[-3500:] or "Codex çıktı üretmedi."
    except subprocess.TimeoutExpired:
        return "Codex görevi zaman aşımına uğradı."
    except FileNotFoundError:
        return f"Codex bulunamadı: {CODEX_BIN}. CODEX_BIN ayarını kontrol edin."
    finally:
        answer_path.unlink(missing_ok=True)


def remember_message(message_id: str) -> bool:
    with db() as conn:
        try:
            conn.execute("INSERT INTO processed_messages(message_id, created_at) VALUES (?, ?)",
                         (message_id, datetime.now(timezone.utc).isoformat()))
            return True
        except sqlite3.IntegrityError:
            return False


async def handle_message(sender: str, text: str, reply: Callable[[str], Awaitable[None]]) -> None:
    text = text.strip()
    lowered = text.lower()
    if lowered in {"/help", "help", "yardım"}:
        await reply("Komutlar:\n/ask <soru> — salt-okunur Codex görevi\n/write <görev> — değişiklik için onay oluşturur\n/confirm <kod> — bekleyen değişikliği uygular\n/cancel — bekleyen görevi iptal eder")
        return
    if lowered == "/cancel":
        with db() as conn:
            conn.execute("DELETE FROM pending_writes WHERE sender = ?", (sender,))
        await reply("Bekleyen görev iptal edildi.")
        return
    if lowered.startswith("/confirm "):
        token = text.split(maxsplit=1)[1].strip()
        with db() as conn:
            row = conn.execute("SELECT task FROM pending_writes WHERE sender = ? AND token = ?", (sender, token)).fetchone()
            if row:
                conn.execute("DELETE FROM pending_writes WHERE sender = ?", (sender,))
        if not row:
            await reply("Geçersiz veya süresi geçmiş onay kodu.")
            return
        await reply("Görev uygulanıyor; tamamlanınca sonucu göndereceğim.")
        await reply(await asyncio.to_thread(run_codex, row["task"], "workspace-write"))
        return
    if lowered.startswith("/write "):
        task = text.split(maxsplit=1)[1].strip()
        token = secrets.token_hex(3).upper()
        with db() as conn:
            conn.execute("INSERT OR REPLACE INTO pending_writes(sender, token, task, created_at) VALUES (?, ?, ?, ?)",
                         (sender, token, task, datetime.now(timezone.utc).isoformat()))
        await reply(f"Bu görev homelab içinde değişiklik yapabilir:\n\n{task}\n\nUygulamak için /confirm {token} yazın. İptal: /cancel")
        return
    task = text.removeprefix("/ask ").strip() if lowered.startswith("/ask ") else text
    await reply(await asyncio.to_thread(run_codex, task, "read-only"))

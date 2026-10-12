import psycopg
from psycopg.rows import dict_row
import procrastinate
from app.config import DATABASE_URL

connector = procrastinate.PsycopgConnector(conninfo=DATABASE_URL)
procrastinate_app = procrastinate.App(connector=connector, import_paths=["app.tasks"])

SCHEMA_LOCK_ID = 727274

async def init_db():
    async with await psycopg.AsyncConnection.connect(DATABASE_URL, autocommit=True) as lock_conn:
        await lock_conn.execute("SELECT pg_advisory_lock(%s)", (SCHEMA_LOCK_ID,))
        try:
            await _create_schema()
        finally:
            await lock_conn.execute("SELECT pg_advisory_unlock(%s)", (SCHEMA_LOCK_ID,))

async def _create_schema():
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        cur = await conn.execute("SELECT to_regclass('procrastinate_jobs') IS NOT NULL")
        (schema_exists,) = await cur.fetchone()

    if not schema_exists:
        async with procrastinate_app.open_async():
            await procrastinate_app.schema_manager.apply_schema_async()

    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS task_results (
                    task_id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    completed_at TIMESTAMP WITH TIME ZONE
                );
            """)
            await conn.commit()

async def get_db_jobs(limit: int = 20):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT id, status, queue_name, task_name, args, attempts, scheduled_at
                FROM procrastinate_jobs
                ORDER BY id DESC
                LIMIT %s;
            """, (limit,))
            return await cur.fetchall()

async def get_task_result(task_id: str):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT task_id, prompt, task_type, status, result, created_at, completed_at
                FROM task_results
                WHERE task_id = %s;
            """, (task_id,))
            return await cur.fetchone()

async def save_task_result(task_id: str, prompt: str, task_type: str, status: str, result: str = None):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO task_results (task_id, prompt, task_type, status, result)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (task_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    result = EXCLUDED.result,
                    completed_at = CASE WHEN EXCLUDED.status IN ('completed', 'failed') THEN NOW() ELSE task_results.completed_at END;
            """, (task_id, prompt, task_type, status, result))
            await conn.commit()

async def get_system_stats():
    async with await psycopg.AsyncConnection.connect(DATABASE_URL, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) AS total_tasks FROM task_results;")
            total_tasks_row = await cur.fetchone()

            await cur.execute("SELECT status, COUNT(*) AS count FROM procrastinate_jobs GROUP BY status;")
            job_status_rows = await cur.fetchall()

            return {
                "total_tasks": total_tasks_row["total_tasks"] if total_tasks_row else 0,
                "job_statuses": {row["status"]: row["count"] for row in job_status_rows}
            }

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import logging

app = FastAPI(title="Zero-Trust Demo Backend - Base App")
DB_NAME = "vulnerable_app.db"

class QueryRequest(BaseModel):
    query: str

def execute_sql(query: str):
    try:
        # Deliberately insecure: direct execution of incoming string
        conn = sqlite3.connect(DB_NAME)
        # Configure to return dictionaries instead of tuples for clean JSON
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query)

        # If it's a SELECT, fetch rows. Otherwise, commit changes.
        if query.strip().upper().startswith("SELECT") or query.strip().upper().startswith("PRAGMA"):
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
        else:
            conn.commit()
            result = {"status": "success", "rows_affected": cursor.rowcount}

        conn.close()
        return result
    except Exception as e:
        logging.error(f"SQL Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/execute")
async def run_query(request: QueryRequest):
    data = execute_sql(request.query)
    return {"query": request.query, "data": data}
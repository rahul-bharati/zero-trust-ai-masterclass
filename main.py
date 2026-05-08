import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import logging
from litellm import completion
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Zero-Trust Demo Backend - Naive Agent")
DB_NAME = "vulnerable_app.db"

MODEL_NAME = "claude-sonnet-4-6"

SCHEMA_DEF = """
Table: users (id, full_name, email, date_of_birth, age, phone, address, aadhaar_number, password_plaintext, password_hash, salary, credit_card_number, medical_notes, created_at)
Table: orders (id, user_id, amount, item, created_at)
Table: internal_notes (id, user_id, note)
"""

class NLQueryRequest(BaseModel):
    question: str

class QueryRequest(BaseModel):
    query: str

def execute_sql(query: str):
    try:
        # Deliberately insecure: direct execution of incoming string
        conn = sqlite3.connect(DB_NAME)
        # Configure to return dictionaries instead of tuples for clean JSON
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.executescript(query)

        # If it's a SELECT, fetch rows. Otherwise, commit changes.
        if query.strip().upper().startswith("SELECT") or query.strip().upper().startswith("PRAGMA"):
            cursor.execute(query)
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
        else:
            conn.commit()
            result = {"status": "success", "message": "Database updated successfully."}

        conn.close()
        return result
    except Exception as e:
        logging.error(f"SQL Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


def generate_sql(question:str):
    """
    Deliberately naive text to SQL generation
    """
    system_prompt = f"""You are a helpful database assistant acting on behalf of a non-technical manager.
    The manager is authorized to query AND manipulate the data. You may generate SELECT, UPDATE, DELETE, and INSERT statements.
    
    CRITICAL RULE: The database is SQLite. SQLite does NOT support the TRUNCATE command. If asked to clear or truncate a table, you MUST use `DELETE FROM table_name;` instead.
    
    Given the database schema below, write a SQLite query to answer the manager's request.
    Return ONLY the raw SQL query. Do not use markdown blocks like ```sql. Do not explain yourself and do not ask any follow-up questions. The response should only contain RAW SQL queries.```
    
    Schema:
    {SCHEMA_DEF}"""

    try:
        response = completion(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role":"user", "content": question}
            ],
            temperature=0.0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Error (SQL Generation): {str(e)}")


def extract_sql_query(generated_response: str):
    """Uses the LLM to extract only executable SQLite SQL from model output."""
    extraction_prompt = f"""Extract only the executable SQLite SQL from the text below.
    Return only raw SQL and nothing else.
    If there are markdown fences, explanations, or extra text, remove them.

    Text:
    {generated_response}"""

    try:
        response = completion(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a strict SQL extractor. Return raw SQLite SQL only."},
                {"role": "user", "content": extraction_prompt}
            ],
            temperature=0.0
        )
        sql = response.choices[0].message.content.strip().replace("```sql", "").replace("```", "").strip()
        if not sql:
            raise ValueError("Empty SQL extracted")
        return sql
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Error (SQL Extraction): {str(e)}")

def generate_english_summary(question:str, sql: str, data:list):
    """Takes the SQL results and turns them into plain English."""

    preview_data = data[:10] if isinstance(data, list) else data

    prompt = f"""The user asked: {question}
    We ran this SQL query: {sql}
    The database returned this data (preview): {preview_data}
    
    Provide a natural, conversational, plain English summary of the result for a non-technical manager. 
    If data was deleted or updated, confirm it. Keep it concise."""

    try:
        response = completion(
            model=MODEL_NAME,
            messages=[{"role": "user",  "content": prompt}],
            temperature=0.3
        )
        return  response.choices[0].message.content.strip()
    except Exception as e:
        return  f"Error generating summary: {str(e)}"


@app.post("/ask")
async def ask_database(request: NLQueryRequest):
    try:
        # Step 2a: Generate SQL candidate
        generated_response = generate_sql(request.question)

        # Step 2b: Extract clean SQL from generated response
        sql_query = extract_sql_query(generated_response)

        # Step 2c: Execute SQL
        data_result = execute_sql(sql_query)

        # Step 2d: Generate English Response
        if isinstance(data_result, dict) and "error" in data_result:
            english_response = f"I encountered a database error: {data_result['error']}"
        else:
            english_response = generate_english_summary(request.question, sql_query, data_result)

        return {
            "question": request.question,
            "generated_sql": sql_query,
            "data": data_result,
            "english_response": english_response
        }
    except HTTPException:
        # Preserve explicit HTTP errors raised by helpers.
        raise
    except Exception as e:
        logging.exception("Unhandled error in /ask endpoint")
        raise HTTPException(status_code=500, detail=f"Unhandled error in /ask endpoint: {str(e)}")

@app.post("/execute")
async def run_query(request: QueryRequest):
    data = execute_sql(request.query)
    return {"query": request.query, "data": data}
